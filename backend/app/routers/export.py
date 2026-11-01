from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import project_dir, safe_join, valid_id
from ..db import get_settings
from ..jobs import job_manager
from ..services.exporter import PRESETS, build_zip
from ..services.storage import get_asset, project_paths
from .common import load_asset_image, require_project

router = APIRouter()


class PackageBody(BaseModel):
    project_id: str
    asset_ids: list[str] = Field(default_factory=list)
    preset: str = "generic"
    format: str = "png"
    naming: str | None = None
    name: str | None = None


@router.get("/export/presets")
def presets() -> dict[str, Any]:
    return {"presets": [{"id": k, **v} for k, v in PRESETS.items()], "formats": ["png", "webp", "jpeg", "bmp", "gif"]}


@router.post("/export/package")
def package(body: PackageBody) -> dict[str, Any]:
    project = require_project(body.project_id)
    if not body.asset_ids:
        raise HTTPException(400, "Select assets to export")
    if len(body.asset_ids) > 1000:
        raise HTTPException(400, "Export limit is 1000 assets")
    if body.preset not in PRESETS:
        raise HTTPException(400, "Unknown preset")
    settings = get_settings()

    def task(ctx) -> dict[str, Any]:
        assets = []
        images = {}
        total = len(body.asset_ids)
        for i, aid in enumerate(body.asset_ids):
            ctx.check_cancel()
            asset = get_asset(aid)
            if not asset or asset["project_id"] != body.project_id:
                continue
            try:
                img = load_asset_image(asset)
            except Exception:
                continue
            assets.append(asset)
            images[aid] = img
            ctx.progress(int(70 * (i + 1) / max(1, total)), f"Loading {i + 1}/{total}")
        data, info = build_zip(
            project["name"], assets, images, body.preset, body.format, body.naming
        )
        ctx.progress(88, "Writing package")
        paths = project_paths(body.project_id)
        filename = (body.name or f"{project['name']}-{body.preset}").replace(" ", "_")
        filename = "".join(c for c in filename if c.isalnum() or c in "-_")[:60] or "export"
        filename = f"{filename}.zip"
        target = safe_join(paths["exports"], filename)
        target.write_bytes(data)
        for old in sorted(paths["exports"].glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)[20:]:
            try:
                old.unlink()
            except OSError:
                pass
        info.update({
            "filename": filename,
            "download_url": f"/api/files/{body.project_id}/exports/{filename}",
            "bytes": len(data),
        })
        return info

    job_id = job_manager().submit("export", task, project_id=body.project_id, workers=int(settings.get("worker_threads", 4)))
    return {"job_id": job_id}


@router.get("/projects/{pid}/exports")
def list_exports(pid: str) -> list[dict[str, Any]]:
    require_project(pid)
    paths = project_paths(pid)
    out = []
    for p in sorted(paths["exports"].glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if p.is_file():
            out.append({
                "filename": p.name,
                "bytes": p.stat().st_size,
                "created_at": p.stat().st_mtime,
                "download_url": f"/api/files/{pid}/exports/{p.name}",
            })
    return out
