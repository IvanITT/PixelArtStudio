from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import time
from typing import Any, AsyncIterator

import psutil
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image
from pydantic import BaseModel, Field

from ..config import DATA_DIR, FRONTEND_DIST, now
from ..db import db, get_settings, set_settings
from ..jobs import job_manager
from ..services import benchmarks as bench_service
from ..services.palettes import delete_palette, list_palettes, save_palette
from ..services.storage import asset_file, cleanup_temp, data_usage, list_projects

router = APIRouter()


class SettingsPatch(BaseModel):
    max_upload_mb: int | None = None
    max_image_pixels: int | None = None
    preview_max_dim: int | None = None
    max_output_dim: int | None = None
    worker_threads: int | None = None
    max_tiles: int | None = None
    cache_limit_mb: int | None = None
    autosave_seconds: int | None = None
    accent: str | None = None
    reduce_motion: bool | None = None
    max_sheet_dim: int | None = None


class PaletteIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    colors: list[str] = Field(min_length=1, max_length=256)
    project_id: str | None = None
    note: str = ""


def _memory() -> dict[str, Any]:
    vm = psutil.virtual_memory()
    proc = psutil.Process(os.getpid())
    try:
        rss = proc.memory_info().rss
    except Exception:
        rss = 0
    return {
        "total_mb": round(vm.total / 1024 / 1024),
        "available_mb": round(vm.available / 1024 / 1024),
        "used_mb": round(vm.used / 1024 / 1024),
        "app_rss_mb": round(rss / 1024 / 1024, 1),
        "percent": vm.percent,
    }


@router.get("/health")
def health() -> dict[str, Any]:
    import cv2
    import numpy
    import PIL
    import scipy

    return {
        "status": "ok",
        "app": "Pixel Art & Game Asset Studio",
        "version": "1.0.0",
        "offline": True,
        "time": now(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "versions": {
            "Pillow": PIL.__version__,
            "NumPy": numpy.__version__,
            "OpenCV": cv2.__version__,
            "SciPy": scipy.__version__,
        },
        "cpu_count": os.cpu_count(),
        "memory": _memory(),
        "data_dir": str(DATA_DIR),
        "frontend_built": (FRONTEND_DIST / "index.html").exists(),
    }


@router.get("/settings")
def read_settings() -> dict[str, Any]:
    return get_settings()


@router.patch("/settings")
def write_settings(patch: SettingsPatch) -> dict[str, Any]:
    values = {k: v for k, v in patch.model_dump().items() if v is not None}
    updated = set_settings(values)
    if "worker_threads" in values:
        job_manager().configure(int(updated["worker_threads"]))
    return updated


@router.get("/system/stats")
def system_stats() -> dict[str, Any]:
    projects = list_projects()
    asset_count = 0
    for p in projects:
        asset_count += p.get("asset_count", 0)
    with db() as conn:
        job_cols = [c[0] for c in conn.execute("SELECT * FROM jobs LIMIT 0").description]
        job_rows = conn.execute(
            "SELECT id,kind,status,progress,message,created_at FROM jobs WHERE status IN ('queued','running') ORDER BY created_at DESC"
        ).fetchall()
        recent = conn.execute(
            "SELECT id,kind,status,progress,message,error,created_at,updated_at FROM jobs ORDER BY created_at DESC LIMIT 12"
        ).fetchall()
    latest = bench_service.latest_benchmarks(1)
    return {
        "memory": _memory(),
        "cpu": {"count": os.cpu_count(), "percent": psutil.cpu_percent(interval=None)},
        "data": data_usage(),
        "projects": len(projects),
        "assets": asset_count,
        "active_jobs": [dict(zip(job_cols, r)) for r in job_rows],
        "recent_jobs": [dict(zip(job_cols, r)) for r in recent],
        "benchmark": latest[0] if latest else None,
        "workers": get_settings().get("worker_threads"),
        "frontend_built": (FRONTEND_DIST / "index.html").exists(),
    }


@router.post("/system/cleanup")
def cleanup() -> dict[str, Any]:
    removed = cleanup_temp(0)
    size = data_usage()
    return {"removed": removed, "data": size}


@router.get("/palettes")
def palettes(project_id: str | None = None) -> list[dict[str, Any]]:
    return list_palettes(project_id)


@router.post("/palettes")
def create_palette(body: PaletteIn) -> dict[str, Any]:
    try:
        return save_palette(body.name, body.colors, body.project_id, body.note)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/palettes/{palette_id}")
def remove_palette(palette_id: str) -> dict[str, Any]:
    if not delete_palette(palette_id):
        raise HTTPException(404, "Palette not found or built-in")
    return {"deleted": True}


@router.get("/files/{project_id}/{bucket}/{filename}")
def serve_file(project_id: str, bucket: str, filename: str) -> FileResponse:
    try:
        path = asset_file(project_id, bucket, filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    media = "image/png"
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        media = "image/jpeg"
    elif suffix == ".webp":
        media = "image/webp"
    elif suffix == ".gif":
        media = "image/gif"
    elif suffix == ".json":
        media = "application/json"
    elif suffix == ".zip":
        media = "application/zip"
    return FileResponse(path, media_type=media, headers={"Cache-Control": "public, max-age=31536000"})


@router.get("/jobs")
def jobs() -> dict[str, Any]:
    return {"active": job_manager().list_active(), "recent": job_manager().recent(30)}


@router.get("/jobs/{job_id}")
def job_detail(job_id: str) -> dict[str, Any]:
    job = job_manager().get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    if not job_manager().cancel(job_id):
        raise HTTPException(404, "Job not found")
    return {"cancelled": True}


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str) -> StreamingResponse:
    if not job_manager().get(job_id):
        raise HTTPException(404, "Job not found")

    async def stream() -> AsyncIterator[str]:
        index = 0
        idle = 0
        yield ": connected\n\n"
        while True:
            events, new_index = job_manager().events_since(job_id, index)
            index = new_index
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"
            job = job_manager().get(job_id)
            if not job:
                yield "event: error\ndata: {\"error\":\"Job not found\"}\n\n"
                break
            if job["status"] in {"done", "error", "cancelled"} and not events:
                idle += 1
                if idle > 2:
                    yield f"event: end\ndata: {json.dumps({'status': job['status']})}\n\n"
                    break
            await asyncio.sleep(0.25)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })


@router.get("/benchmarks")
def benchmarks(limit: int = 10) -> list[dict[str, Any]]:
    return bench_service.latest_benchmarks(max(1, min(limit, 50)))


@router.post("/benchmarks/run")
def run_benchmarks() -> dict[str, Any]:
    settings = get_settings()
    job_id = job_manager().submit(
        "benchmark",
        lambda ctx: bench_service.run_benchmarks(ctx.progress),
        workers=int(settings.get("worker_threads", 4)),
    )
    return {"job_id": job_id}
