from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from ..config import valid_id
from ..db import db
from ..services import projectio
from ..services.exporter import convert_image
from ..services.images import decode_image
from ..services.storage import (
    backup_project,
    create_asset,
    create_project,
    delete_asset,
    delete_project,
    duplicate_project,
    get_asset,
    get_project,
    list_assets,
    list_backups,
    list_projects,
    project_paths,
    restore_backup,
    serialize_asset,
    update_asset,
    update_project,
    asset_file,
)
from .common import require_asset, require_project

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    category: str = "General"


class ProjectPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    favorite: bool | None = None
    state: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None
    replace_state: bool = False


class SaveBody(BaseModel):
    note: str = "manual"
    state: dict[str, Any] | None = None


class AssetPatch(BaseModel):
    name: str | None = None
    tags: list[str] | str | None = None
    favorite: bool | None = None
    meta: dict[str, Any] | None = None


class BatchBody(BaseModel):
    ids: list[str]
    action: str
    value: str | bool | None = None


def _should_backup(pid: str, note: str) -> bool:
    if note != "autosave":
        return True
    with db() as conn:
        row = conn.execute(
            "SELECT created_at FROM backups WHERE project_id=? ORDER BY created_at DESC LIMIT 1", (pid,)
        ).fetchone()
    if not row:
        return True
    try:
        last = datetime.strptime(row["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - last).total_seconds() > 300
    except Exception:
        return True


@router.get("/projects")
def projects(search: str = "", category: str = "", favorite: bool = False) -> list[dict[str, Any]]:
    return list_projects(search=search, category=category, favorite=favorite or None)


@router.post("/projects")
def post_project(body: ProjectCreate) -> dict[str, Any]:
    return create_project(body.name, body.description, body.category)


@router.get("/projects/{pid}")
def project_detail(pid: str) -> dict[str, Any]:
    return require_project(pid)


@router.patch("/projects/{pid}")
def patch_project(pid: str, body: ProjectPatch) -> dict[str, Any]:
    require_project(pid)
    data = body.model_dump(exclude_none=True)
    try:
        return update_project(pid, data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/projects/{pid}")
def remove_project(pid: str, confirm: bool = Query(False)) -> dict[str, Any]:
    require_project(pid)
    if not confirm:
        raise HTTPException(400, "Deletion requires confirm=true")
    return {"deleted": delete_project(pid)}


@router.post("/projects/{pid}/duplicate")
def copy_project(pid: str) -> dict[str, Any]:
    require_project(pid)
    try:
        return duplicate_project(pid)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/projects/{pid}/save")
def save_project(pid: str, body: SaveBody) -> dict[str, Any]:
    require_project(pid)
    if body.state is not None:
        update_project(pid, {"state": body.state})
    backup = None
    if _should_backup(pid, body.note):
        backup = backup_project(pid, body.note)
    else:
        project_paths(pid)
        from ..services.storage import write_project_json

        write_project_json(pid)
    return {"saved": True, "backup": backup, "project": get_project(pid)}


@router.get("/projects/{pid}/backups")
def backups(pid: str) -> list[dict[str, Any]]:
    require_project(pid)
    return list_backups(pid)


@router.post("/projects/{pid}/backups/{backup_id}/restore")
def restore(pid: str, backup_id: str) -> dict[str, Any]:
    require_project(pid)
    try:
        return restore_backup(pid, backup_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/projects/{pid}/export")
def export_project(pid: str) -> Response:
    project = require_project(pid)
    data = projectio.export_project_zip(pid)
    fname = "".join(c for c in project["name"] if c.isalnum() or c in " -_").strip() or "project"
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{fname}.pasproject.zip"'},
    )


@router.post("/projects/import")
async def import_project(file: UploadFile = File(...)) -> dict[str, Any]:
    data = await file.read()
    try:
        return projectio.import_project_zip(data, file.filename or "project.zip")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/projects/{pid}/assets")
def assets(
    pid: str,
    kind: str = "all",
    search: str = "",
    favorite: bool = False,
    tag: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    require_project(pid)
    return list_assets(pid, kind=kind, search=search, favorite=favorite or None, tag=tag, limit=limit)


@router.post("/projects/{pid}/assets/upload")
async def upload_asset(
    pid: str,
    file: UploadFile = File(...),
    name: str = Form(""),
    kind: str = Form("source"),
) -> dict[str, Any]:
    require_project(pid)
    if kind not in {"source", "sprite"}:
        raise HTTPException(400, "Uploads may only create source or sprite assets")
    data = await file.read()
    try:
        image = decode_image(data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    display = (name or (file.filename or "Imported image")).rsplit(".", 1)[0][:120]
    asset = create_asset(
        pid, display, kind, image=image, meta={"upload": True},
        original_bytes=data, original_filename=file.filename,
    )
    return asset


@router.get("/projects/{pid}/tags")
def tags(pid: str) -> list[str]:
    require_project(pid)
    with db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT tag FROM library_tags WHERE project_id=? ORDER BY tag", (pid,)
        ).fetchall()
    return [r["tag"] for r in rows]


@router.get("/assets/{aid}")
def asset_detail(aid: str) -> dict[str, Any]:
    asset = get_asset(aid)
    if not asset:
        raise HTTPException(404, "Asset not found")
    return asset


@router.patch("/assets/{aid}")
def patch_asset(aid: str, body: AssetPatch) -> dict[str, Any]:
    updated = update_asset(aid, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(404, "Asset not found")
    return updated


@router.delete("/assets/{aid}")
def remove_asset(aid: str) -> dict[str, Any]:
    if not delete_asset(aid):
        raise HTTPException(404, "Asset not found")
    return {"deleted": True}


@router.get("/assets/{aid}/download")
def download_asset(aid: str, format: str = "original", name: str | None = None) -> Response:
    asset = get_asset(aid)
    if not asset:
        raise HTTPException(404, "Asset not found")
    if format == "original":
        path = asset_file(asset["project_id"], "assets", asset["filename"])
        return FileResponse(path, filename=f"{name or asset['name']}{path.suffix}", media_type="application/octet-stream")
    from .common import load_asset_image

    img = load_asset_image(asset)
    try:
        data = convert_image(img, format)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    ext = "jpg" if format.lower() in {"jpg", "jpeg"} else format.lower()
    fname = "".join(c for c in (name or asset["name"]) if c.isalnum() or c in " -_").strip() or "asset"
    return Response(content=data, media_type=f"image/{ext}", headers={
        "Content-Disposition": f'attachment; filename="{fname}.{ext}"'
    })


@router.post("/assets/batch")
def batch_assets(body: BatchBody) -> dict[str, Any]:
    if body.action not in {"delete", "favorite", "tags"}:
        raise HTTPException(400, "Unknown batch action")
    if len(body.ids) > 500:
        raise HTTPException(400, "Batch limit is 500 assets")
    affected = 0
    for aid in body.ids:
        if body.action == "delete":
            affected += 1 if delete_asset(aid) else 0
        elif body.action == "favorite":
            if update_asset(aid, {"favorite": bool(body.value)}):
                affected += 1
        else:
            tags = body.value if isinstance(body.value, str) else ""
            if update_asset(aid, {"tags": tags}):
                affected += 1
    return {"affected": affected}
