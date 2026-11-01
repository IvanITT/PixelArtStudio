from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..config import new_id, now, valid_id
from ..db import db, json_field
from ..services import animation as anim_service
from ..services.images import decode_image
from ..services.storage import (
    create_asset,
    get_animations,
    get_asset,
    save_bytes_asset,
)
from .common import load_asset_image, require_asset, require_project

router = APIRouter()


class AnimationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    fps: int = 8
    loop: bool = True
    frames: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class AnimationPatch(BaseModel):
    name: str | None = None
    fps: int | None = None
    loop: bool | None = None
    frames: list[str] | None = None
    meta: dict[str, Any] | None = None


class FrameBody(BaseModel):
    asset_id: str
    index: int | None = None


class ReorderBody(BaseModel):
    from_index: int
    to_index: int


class TemplateBody(BaseModel):
    asset_id: str
    template: str = "walk"
    frames: int | None = None
    replace: bool = False


class ExportBody(BaseModel):
    format: str = "sheet"
    columns: int = 0
    cell_width: int = 0
    cell_height: int = 0
    padding: int = 0
    spacing: int = 0
    name: str | None = None
    save_asset: bool = True


def _anim(aid: str) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute("SELECT * FROM animations WHERE id=?", (aid,)).fetchone()
    if not row:
        raise HTTPException(404, "Animation not found")
    data = dict(row)
    data["frames"] = json.loads(data.get("frames") or "[]")
    data["meta"] = json_field(data, "meta", {})
    data["loop"] = bool(data.get("loop"))
    return data


def _decorate(anim: dict[str, Any]) -> dict[str, Any]:
    frames = []
    for fid in anim["frames"]:
        asset = get_asset(fid)
        if asset:
            frames.append(asset)
    anim["frame_assets"] = frames
    anim["frame_count"] = len(frames)
    return anim


def _clean_fps(value: Any, default: int = 8) -> int:
    try:
        return max(1, min(60, int(value)))
    except Exception:
        return default


def _frames_images(anim: dict[str, Any]) -> list:
    images = []
    names = []
    for fid in anim["frames"]:
        asset = get_asset(fid)
        if not asset:
            continue
        images.append(load_asset_image(asset))
        names.append(asset["name"])
    return images, names


@router.get("/projects/{pid}/animations")
def list_animations(pid: str) -> list[dict[str, Any]]:
    require_project(pid)
    return [_decorate(a) for a in get_animations(pid)]


@router.post("/projects/{pid}/animations")
def create_animation(pid: str, body: AnimationCreate) -> dict[str, Any]:
    require_project(pid)
    frames = [f for f in body.frames if get_asset(f) and get_asset(f)["project_id"] == pid]
    aid = new_id()
    ts = now()
    with db() as conn:
        conn.execute(
            "INSERT INTO animations(id,project_id,name,fps,loop,frames,meta,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (aid, pid, body.name.strip()[:100], _clean_fps(body.fps), 1 if body.loop else 0,
             json.dumps(frames), json.dumps(body.meta), ts, ts),
        )
    return _decorate(_anim(aid))


@router.get("/animations/{aid}")
def animation_detail(aid: str) -> dict[str, Any]:
    return _decorate(_anim(aid))


@router.patch("/animations/{aid}")
def patch_animation(aid: str, body: AnimationPatch) -> dict[str, Any]:
    anim = _anim(aid)
    sets: list[str] = []
    params: list[Any] = []
    if body.name is not None:
        sets.append("name=?")
        params.append(body.name.strip()[:100] or anim["name"])
    if body.fps is not None:
        sets.append("fps=?")
        params.append(_clean_fps(body.fps))
    if body.loop is not None:
        sets.append("loop=?")
        params.append(1 if body.loop else 0)
    if body.frames is not None:
        valid = [f for f in body.frames if get_asset(f) and get_asset(f)["project_id"] == anim["project_id"]]
        if len(valid) > 500:
            raise HTTPException(400, "Animation frame limit is 500")
        sets.append("frames=?")
        params.append(json.dumps(valid))
    if body.meta is not None:
        merged = {**anim["meta"], **body.meta}
        sets.append("meta=?")
        params.append(json.dumps(merged))
    if not sets:
        return _decorate(anim)
    sets.append("updated_at=?")
    params.append(now())
    params.append(aid)
    with db() as conn:
        conn.execute(f"UPDATE animations SET {', '.join(sets)} WHERE id=?", params)
    return _decorate(_anim(aid))


@router.delete("/animations/{aid}")
def delete_animation(aid: str) -> dict[str, Any]:
    _anim(aid)
    with db() as conn:
        conn.execute("DELETE FROM animations WHERE id=?", (aid,))
    return {"deleted": True}


@router.post("/animations/{aid}/frames")
def add_frame(aid: str, body: FrameBody) -> dict[str, Any]:
    anim = _anim(aid)
    asset = require_asset(body.asset_id, anim["project_id"])
    frames = list(anim["frames"])
    if body.index is None or body.index < 0 or body.index > len(frames):
        frames.append(asset["id"])
    else:
        frames.insert(body.index, asset["id"])
    return _save_frames(aid, frames)


def _save_frames(aid: str, frames: list[str]) -> dict[str, Any]:
    with db() as conn:
        conn.execute("UPDATE animations SET frames=?, updated_at=? WHERE id=?", (json.dumps(frames), now(), aid))
    return _decorate(_anim(aid))


@router.post("/projects/{pid}/animations/{aid}/frames/upload")
async def upload_frame(pid: str, aid: str, file: UploadFile = File(...), name: str = Form("")) -> dict[str, Any]:
    anim = _anim(aid)
    if anim["project_id"] != pid:
        raise HTTPException(400, "Animation belongs to another project")
    data = await file.read()
    try:
        image = decode_image(data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    asset = create_asset(pid, name or (file.filename or "Frame"), "frame", image, meta={"upload": True}, tags="frame")
    frames = anim["frames"] + [asset["id"]]
    return {"animation": _save_frames(aid, frames), "frame": asset}


@router.delete("/animations/{aid}/frames/{index}")
def delete_frame(aid: str, index: int) -> dict[str, Any]:
    anim = _anim(aid)
    if index < 0 or index >= len(anim["frames"]):
        raise HTTPException(400, "Frame index out of range")
    frames = anim["frames"][:]
    frames.pop(index)
    return _save_frames(aid, frames)


@router.post("/animations/{aid}/duplicate-frame")
def duplicate_frame(aid: str, body: ReorderBody) -> dict[str, Any]:
    anim = _anim(aid)
    i = body.from_index
    if i < 0 or i >= len(anim["frames"]):
        raise HTTPException(400, "Frame index out of range")
    frames = anim["frames"][:]
    frames.insert(min(len(frames), i + 1), frames[i])
    return _save_frames(aid, frames)


@router.post("/animations/{aid}/reorder")
def reorder(aid: str, body: ReorderBody) -> dict[str, Any]:
    anim = _anim(aid)
    frames = anim["frames"][:]
    if not (0 <= body.from_index < len(frames) and 0 <= body.to_index < len(frames)):
        raise HTTPException(400, "Frame index out of range")
    item = frames.pop(body.from_index)
    frames.insert(body.to_index, item)
    return _save_frames(aid, frames)


@router.post("/animations/{aid}/template")
def apply_template(aid: str, body: TemplateBody) -> dict[str, Any]:
    anim = _anim(aid)
    asset = require_asset(body.asset_id, anim["project_id"])
    if body.template not in anim_service.TEMPLATES:
        raise HTTPException(400, "Unknown animation template")
    img = load_asset_image(asset, max_dim=512)
    frames_img = anim_service.template_frames(img, body.template, body.frames)
    created_ids = []
    for i, f in enumerate(frames_img):
        created = create_asset(
            anim["project_id"], f"{asset['name']} {body.template} {i + 1:02d}", "frame", f,
            meta={"template": body.template, "source_asset_id": asset["id"], "frame_index": i},
            tags=f"frame,animation,{body.template}",
        )
        created_ids.append(created["id"])
    frames = created_ids if body.replace or not anim["frames"] else anim["frames"] + created_ids
    updated = _save_frames(aid, frames)
    with db() as conn:
        conn.execute(
            "UPDATE animations SET fps=?, updated_at=? WHERE id=?",
            (anim_service.TEMPLATES[body.template]["fps"], now(), aid),
        )
    return _decorate(_anim(aid))


@router.post("/animations/{aid}/export")
def export_animation(aid: str, body: ExportBody) -> dict[str, Any]:
    anim = _anim(aid)
    images, names = _frames_images(anim)
    if not images:
        raise HTTPException(400, "Animation has no valid frames")
    fmt = body.format.lower()
    if fmt not in {"sheet", "gif", "webp", "json"}:
        raise HTTPException(400, "Format must be sheet, gif, webp or json")
    base_name = body.name or anim["name"]
    if fmt == "sheet":
        sheet, meta = anim_service.pack_frames(
            images, names, body.columns, body.cell_width, body.cell_height, body.padding, body.spacing,
        )
        meta["animation"] = {"id": aid, "name": anim["name"], "fps": anim["fps"], "loop": anim["loop"]}
        meta["fps"] = anim["fps"]
        meta["frames_meta"] = anim_service.frame_metadata(images, names, anim["fps"], anim["loop"])
        asset = create_asset(
            anim["project_id"], base_name + " sheet", "spritesheet", sheet,
            meta={"sheet": meta, "fps": anim["fps"], "loop": anim["loop"], "animation_id": aid, "frame_count": len(images)},
            tags="spritesheet,animation",
        )
        return {"asset": asset, "metadata": meta, "format": fmt}
    if fmt in {"gif", "webp"}:
        data = anim_service.export_gif(images, anim["fps"], anim["loop"]) if fmt == "gif" else anim_service.export_webp(images, anim["fps"], anim["loop"])
        asset = save_bytes_asset(
            anim["project_id"], base_name + f".{fmt}", "animation", data, fmt,
            meta={"animation_id": aid, "fps": anim["fps"], "loop": anim["loop"], "frame_count": len(images)},
            tags=f"animation,{fmt}",
        )
        return {"asset": asset, "format": fmt}
    metadata = anim_service.frame_metadata(images, names, anim["fps"], anim["loop"])
    metadata["animation_id"] = aid
    data = json.dumps(metadata, indent=2).encode("utf-8")
    asset = save_bytes_asset(
        anim["project_id"], base_name + " metadata.json", "export", data, "json",
        meta={"animation_id": aid}, tags="metadata,animation",
    )
    return {"asset": asset, "metadata": metadata, "format": fmt}
