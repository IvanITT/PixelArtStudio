"""Project package export/import with zip-slip and zip-bomb protection."""
from __future__ import annotations

import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from ..config import DATA_DIR, new_id, now, project_dir, read_json, safe_join, write_json
from ..db import db
from .storage import create_project, get_project, project_paths, write_project_json

MAX_TOTAL_UNCOMPRESSED = 1_500_000_000
MAX_MEMBERS = 20_000


def export_project_zip(pid: str) -> bytes:
    project = get_project(pid)
    if not project:
        raise ValueError("Project not found")
    write_project_json(pid)
    base = project_dir(pid)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("manifest.json", json.dumps({
            "format": "pixel-art-studio-package",
            "version": 1,
            "project": project["name"],
            "exported_at": now(),
            "note": "Offline project package. Relative paths only.",
        }, indent=2))
        for rel in ("project.json",):
            p = safe_join(base, rel)
            if p.exists():
                zf.write(p, rel)
        for folder in ("assets", "sources"):
            root = safe_join(base, folder)
            if not root.exists():
                continue
            for p in sorted(root.rglob("*")):
                if p.is_file():
                    zf.write(p, p.relative_to(base).as_posix())
    return buf.getvalue()


def _validated_members(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    infos = zf.infolist()
    if len(infos) > MAX_MEMBERS:
        raise ValueError("Archive contains too many files")
    total = 0
    for info in infos:
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in name.split("/") or (len(name) > 1 and name[1] == ":"):
            raise ValueError("Archive contains an unsafe path")
        if info.is_dir():
            continue
        mode = (info.external_attr >> 16) & 0o170000
        if mode == 0o120000:
            raise ValueError("Archive contains a symbolic link")
        total += info.file_size
        if total > MAX_TOTAL_UNCOMPRESSED:
            raise ValueError("Archive expands beyond the allowed size")
    return infos


def import_project_zip(data: bytes, filename: str = "project.zip") -> dict[str, Any]:
    if len(data) > 800 * 1024 * 1024:
        raise ValueError("Project package is too large")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("Not a valid ZIP package") from exc
    with zf:
        infos = _validated_members(zf)
        names = {i.filename.replace("\\", "/") for i in infos}
        if "project.json" not in names:
            raise ValueError("Package does not contain project.json")
        raw = zf.read("project.json")
        try:
            payload = json.loads(raw)
        except Exception as exc:
            raise ValueError("project.json is not valid JSON") from exc
        if payload.get("format") != "pixel-art-studio-project":
            raise ValueError("Unrecognized project format")
        new_pid = new_id()
        dst = project_dir(new_pid)
        dst.mkdir(parents=True, exist_ok=True)
        try:
            for info in infos:
                rel = info.filename.replace("\\", "/")
                if info.is_dir() or rel in {"project.json", "manifest.json"}:
                    continue
                if not (rel.startswith("assets/") or rel.startswith("sources/")):
                    continue
                target = safe_join(dst, *rel.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out, length=1024 * 1024)
        except Exception:
            shutil.rmtree(dst, ignore_errors=True)
            raise
        for sub in ("assets", "thumbs", "sources", "previews", "exports", "backups"):
            (dst / sub).mkdir(parents=True, exist_ok=True)
        ts = now()
        name = str(payload.get("name") or "Imported project")[:100]
        with db() as conn:
            existing = conn.execute("SELECT name FROM projects WHERE name=?", (name,)).fetchone()
            if existing:
                name = (name + " (imported)")[:100]
            conn.execute(
                "INSERT INTO projects(id,name,description,category,favorite,state,settings,created_at,updated_at) VALUES(?,?,?,?,0,?,?,?,?)",
                (
                    new_pid, name, payload.get("description", ""), payload.get("category", "General"),
                    json.dumps(payload.get("state", {})), json.dumps(payload.get("settings", {})), ts, ts,
                ),
            )
            id_map: dict[str, str] = {}
            from PIL import Image as PILImage

            from .images import ensure_rgba, make_thumbnail_file

            thumb_dir = dst / "thumbs"
            thumb_dir.mkdir(parents=True, exist_ok=True)
            for a in payload.get("assets", []):
                old_id = a.get("id")
                new_id_asset = new_id()
                id_map[old_id] = new_id_asset
                fname = Path(str(a.get("filename", ""))).name
                if not fname or not (dst / "assets" / fname).exists():
                    continue
                thumb_name = f"{new_id_asset}.png"
                try:
                    with PILImage.open(dst / "assets" / fname) as im:
                        im.load()
                        make_thumbnail_file(ensure_rgba(im), str(thumb_dir / thumb_name), 320)
                except Exception:
                    thumb_name = None
                conn.execute(
                    "INSERT INTO assets(id,project_id,name,kind,filename,thumb,width,height,size_bytes,sha256,tags,favorite,meta,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        new_id_asset, new_pid, a.get("name", "Asset"), a.get("kind", "source"), fname,
                        thumb_name, a.get("width", 0), a.get("height", 0), a.get("size_bytes", 0),
                        a.get("sha256"), a.get("tags", ""), 1 if a.get("favorite") else 0,
                        json.dumps(a.get("meta", {})), a.get("created_at", ts), a.get("updated_at", ts),
                    ),
                )
            def remap(value: Any) -> Any:
                if isinstance(value, dict):
                    return {k: (id_map.get(v, v) if k in {"asset_id", "assetId", "frame_asset_id"} else remap(v)) for k, v in value.items()}
                if isinstance(value, list):
                    return [remap(v) for v in value]
                return value
            for an in payload.get("animations", []):
                frames = [id_map.get(f, f) for f in an.get("frames", [])]
                conn.execute(
                    "INSERT INTO animations(id,project_id,name,fps,loop,frames,meta,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (new_id(), new_pid, an.get("name", "Animation"), an.get("fps", 8), 1 if an.get("loop") else 0,
                     json.dumps(frames), json.dumps(an.get("meta", {})), ts, ts),
                )
            for pal in payload.get("palettes", []):
                conn.execute(
                    "INSERT INTO palettes(id,name,colors,builtin,project_id,note,created_at) VALUES(?,?,?,0,?,?,?)",
                    (new_id(), pal.get("name", "Palette"), pal.get("colors", ""), new_pid, pal.get("note", ""), ts),
                )
            state = remap(payload.get("state", {}))
            conn.execute("UPDATE projects SET state=? WHERE id=?", (json.dumps(state), new_pid))
        write_json(dst / "project.json", {**payload, "id": new_pid, "name": name, "state": state, "updated_at": ts})
        write_project_json(new_pid)
    return get_project(new_pid)  # type: ignore[return-value]


def import_from_path(path: str) -> dict[str, Any]:
    with open(path, "rb") as fh:
        return import_project_zip(fh.read(), Path(path).name)
