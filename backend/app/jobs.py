from __future__ import annotations

import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from .config import new_id, now
from .db import db


class JobCancelled(Exception):
    pass


@dataclass
class JobContext:
    job_id: str
    cancel_event: threading.Event
    _progress: int = 0
    _message: str = ""

    def progress(self, pct: int, message: str | None = None) -> None:
        self._progress = max(0, min(100, int(pct)))
        if message is not None:
            self._message = message
        _manager._update(self.job_id, self._progress, self._message)

    def check_cancel(self) -> None:
        if self.cancel_event.is_set():
            raise JobCancelled("Task cancelled by user")


@dataclass
class JobRecord:
    id: str
    kind: str
    status: str = "queued"
    progress: int = 0
    message: str = ""
    result: Any = None
    error: str | None = None
    project_id: str | None = None
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)
    events: list[dict[str, Any]] = field(default_factory=list)
    cancel_event: threading.Event = field(default_factory=threading.Event)


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()
        self._executor: ThreadPoolExecutor | None = None
        self._workers = 0

    def configure(self, workers: int) -> None:
        if self._executor is None or workers != self._workers:
            if self._executor is not None:
                self._executor.shutdown(wait=False, cancel_futures=False)
            self._workers = max(1, min(int(workers), 8))
            self._executor = ThreadPoolExecutor(
                max_workers=self._workers, thread_name_prefix="pas-job"
            )

    def _record(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _push_event(self, rec: JobRecord, status: str | None = None) -> None:
        event = {
            "id": rec.id,
            "status": status or rec.status,
            "progress": rec.progress,
            "message": rec.message,
            "result": rec.result,
            "error": rec.error,
        }
        rec.events.append(event)
        if len(rec.events) > 200:
            rec.events = rec.events[-100:]

    def _update(self, job_id: str, progress: int, message: str) -> None:
        rec = self._record(job_id)
        if not rec:
            return
        with self._lock:
            rec.progress = progress
            if message:
                rec.message = message
            rec.updated_at = now()
            if progress != getattr(rec, "_last_pushed", -1):
                rec._last_pushed = progress  # type: ignore[attr-defined]
                self._push_event(rec)
        try:
            with db() as conn:
                conn.execute(
                    "UPDATE jobs SET progress=?, message=?, updated_at=? WHERE id=?",
                    (progress, message, now(), job_id),
                )
        except Exception:
            pass

    def submit(
        self,
        kind: str,
        fn: Callable[[JobContext], Any],
        project_id: str | None = None,
        workers: int | None = None,
    ) -> str:
        if workers:
            self.configure(workers)
        if self._executor is None:
            self.configure(4)
        job_id = new_id()
        rec = JobRecord(id=job_id, kind=kind, project_id=project_id)
        with self._lock:
            self._jobs[job_id] = rec
            self._push_event(rec)
        with db() as conn:
            conn.execute(
                "INSERT INTO jobs(id,kind,status,progress,message,project_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (job_id, kind, "queued", 0, "", project_id, rec.created_at, rec.updated_at),
            )
        assert self._executor is not None
        self._executor.submit(self._run, rec, fn)
        return job_id

    def _run(self, rec: JobRecord, fn: Callable[[JobContext], Any]) -> None:
        ctx = JobContext(job_id=rec.id, cancel_event=rec.cancel_event)
        with self._lock:
            rec.status = "running"
            rec.message = "Starting"
            rec.updated_at = now()
            self._push_event(rec)
        try:
            with db() as conn:
                conn.execute(
                    "UPDATE jobs SET status='running', message='Starting', updated_at=? WHERE id=?",
                    (now(), rec.id),
                )
            result = fn(ctx)
            if rec.cancel_event.is_set():
                raise JobCancelled("Task cancelled by user")
            with self._lock:
                rec.status = "done"
                rec.progress = 100
                rec.result = result
                rec.message = "Completed"
                rec.updated_at = now()
                self._push_event(rec)
            with db() as conn:
                conn.execute(
                    "UPDATE jobs SET status='done', progress=100, message='Completed', result=?, updated_at=? WHERE id=?",
                    (_json(result), now(), rec.id),
                )
        except JobCancelled:
            with self._lock:
                rec.status = "cancelled"
                rec.message = "Cancelled"
                rec.error = "Cancelled by user"
                rec.updated_at = now()
                self._push_event(rec)
            with db() as conn:
                conn.execute(
                    "UPDATE jobs SET status='cancelled', message='Cancelled', error=?, updated_at=? WHERE id=?",
                    ("Cancelled by user", now(), rec.id),
                )
        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc(limit=4)
            with self._lock:
                rec.status = "error"
                rec.error = f"{type(exc).__name__}: {exc}"
                rec.message = "Failed"
                rec.updated_at = now()
                self._push_event(rec)
            with db() as conn:
                conn.execute(
                    "UPDATE jobs SET status='error', error=?, message='Failed', updated_at=? WHERE id=?",
                    (f"{rec.error}\n{tb}", now(), rec.id),
                )

    def cancel(self, job_id: str) -> bool:
        rec = self._record(job_id)
        if not rec:
            return False
        rec.cancel_event.set()
        return True

    def get(self, job_id: str) -> dict[str, Any] | None:
        rec = self._record(job_id)
        if not rec:
            with db() as conn:
                row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
                if not row:
                    return None
                out = dict(row)
                try:
                    out["result"] = _loads(out.get("result"))
                except Exception:
                    pass
                return out
        return {
            "id": rec.id,
            "kind": rec.kind,
            "status": rec.status,
            "progress": rec.progress,
            "message": rec.message,
            "result": rec.result,
            "error": rec.error,
            "project_id": rec.project_id,
            "created_at": rec.created_at,
            "updated_at": rec.updated_at,
        }

    def list_active(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "id": r.id,
                    "kind": r.kind,
                    "status": r.status,
                    "progress": r.progress,
                    "message": r.message,
                    "created_at": r.created_at,
                }
                for r in self._jobs.values()
                if r.status in {"queued", "running"}
            ]

    def recent(self, limit: int = 30) -> list[dict[str, Any]]:
        with db() as conn:
            rows = conn.execute(
                "SELECT id,kind,status,progress,message,error,created_at,updated_at FROM jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def events_since(self, job_id: str, index: int) -> tuple[list[dict[str, Any]], int]:
        rec = self._record(job_id)
        if not rec:
            return [], index
        with self._lock:
            events = rec.events[index:]
            return events, len(rec.events)


def _json(value: Any) -> str:
    import json

    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return "null"


def _loads(value: Any) -> Any:
    import json

    if not value:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return value


_manager = JobManager()


def job_manager() -> JobManager:
    return _manager
