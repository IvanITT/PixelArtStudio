from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel, Field

from ..config import safe_join
from ..db import get_settings
from ..jobs import job_manager
from ..services.images import image_to_bytes
from ..services.pixelart import process_pixel_art
from ..services.storage import create_asset, project_paths
from .common import load_asset_image, require_asset, require_project

router = APIRouter()


class PreviewBody(BaseModel):
    project_id: str
    asset_id: str
    options: dict[str, Any] = Field(default_factory=dict)


class ExportBody(BaseModel):
    project_id: str
    asset_id: str
    options: dict[str, Any] = Field(default_factory=dict)
    name: str = "Pixel art"


class WorkspaceLayer(BaseModel):
    asset_id: str
    x: float = 0
    y: float = 0
    scale: float = 1
    rotation: float = 0
    opacity: float = 1
    visible: bool = True


class WorkspaceExport(BaseModel):
    project_id: str
    width: int = 512
    height: int = 512
    layers: list[WorkspaceLayer] = Field(default_factory=list)
    background: str = "transparent"
    name: str = "Workspace composite"


def _preview_cache(domain: str, key: str) -> str:
    return f"{domain}:{hashlib.sha256(key.encode()).hexdigest()[:32]}"


def _render_preview(
    body: PreviewBody,
    progress: Any = None,
    *,
    use_cache: bool = True,
) -> dict[str, Any]:
    require_project(body.project_id)
    asset = require_asset(body.asset_id, body.project_id)
    settings = get_settings()
    max_preview = int(settings.get("preview_max_dim", 1200))
    opts = dict(body.options)
    for k in ("width", "height"):
        try:
            if int(opts.get(k, 0)) > max_preview:
                opts[k] = max_preview
        except Exception:
            pass
    key_payload = json.dumps(opts, sort_keys=True) + asset.get("sha256", "")
    key = _preview_cache("pixelart", key_payload)
    paths = project_paths(body.project_id)
    name = hashlib.sha256(key.encode()).hexdigest()[:24]
    png = safe_join(paths["previews"], name + ".png")
    meta_file = safe_join(paths["previews"], name + ".json")

    if use_cache and png.exists() and meta_file.exists():
        try:
            info = json.loads(meta_file.read_text(encoding="utf-8"))
            if progress:
                progress(100, "Cached preview")
            return {
                "url": f"/api/files/{body.project_id}/previews/{name}.png?v={int(png.stat().st_mtime)}",
                "info": info,
                "source_url": asset["url"],
                "cached": True,
                "asset_id": asset["id"],
            }
        except Exception:
            pass

    img = load_asset_image(asset, max_dim=2400)
    result = process_pixel_art(img, opts, progress=progress)
    png.write_bytes(image_to_bytes(result.image, "PNG"))
    meta_file.write_text(json.dumps(result.info), encoding="utf-8")
    # Cached previews are cleaned by the global cleanup endpoint; avoid deleting
    # unrelated previews (tiles/sprite thumbnails) on cache misses.
    return {
        "url": f"/api/files/{body.project_id}/previews/{name}.png?v={int(png.stat().st_mtime)}",
        "info": result.info,
        "source_url": asset["url"],
        "cached": False,
        "asset_id": asset["id"],
    }


@router.post("/pixelart/preview")
def preview(body: PreviewBody) -> dict[str, Any]:
    return _render_preview(body)


@router.post("/pixelart/job")
def preview_job(body: PreviewBody) -> dict[str, Any]:
    """Run a pixel-art preview as a background job with progress events."""
    require_project(body.project_id)
    settings = get_settings()
    job_id = job_manager().submit(
        "pixelart_preview",
        lambda ctx: _render_preview(body, ctx.progress),
        project_id=body.project_id,
        workers=int(settings.get("worker_threads", 4)),
    )
    return {"job_id": job_id}


@router.post("/pixelart/export")
def export_pixelart(body: ExportBody) -> dict[str, Any]:
    require_project(body.project_id)
    asset = require_asset(body.asset_id, body.project_id)
    max_out = int(get_settings().get("max_output_dim", 1024))
    opts = dict(body.options)
    for k in ("width", "height"):
        try:
            if int(opts.get(k, 0)) > max_out:
                opts[k] = max_out
        except Exception:
            pass
    img = load_asset_image(asset)
    result = process_pixel_art(img, opts)
    created = create_asset(
        body.project_id,
        body.name or "Pixel art",
        "pixelart",
        result.image,
        meta={"options": opts, "info": result.info, "source_asset_id": asset["id"]},
        tags="pixelart",
    )
    return {"asset": created, "info": result.info}


@router.post("/workspace/export")
def export_workspace(body: WorkspaceExport) -> dict[str, Any]:
    require_project(body.project_id)
    w = max(8, min(int(body.width), 4096))
    h = max(8, min(int(body.height), 4096))
    bg = body.background or "transparent"
    if bg == "transparent":
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    else:
        from ..services.pixelart import hex_to_rgb

        canvas = Image.new("RGBA", (w, h), hex_to_rgb(bg) + (255,))
    if len(body.layers) > 64:
        raise HTTPException(400, "Workspace layer limit is 64")
    canvas_w, canvas_h = canvas.size
    for layer in body.layers:
        if not layer.visible or layer.opacity <= 0:
            continue
        asset = require_asset(layer.asset_id, body.project_id)
        img = load_asset_image(asset).convert("RGBA")
        scale = max(0.01, min(float(layer.scale), 16.0))
        if scale != 1.0:
            img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.Resampling.NEAREST)
        if abs(layer.rotation) > 0.01:
            img = img.rotate(-layer.rotation, resample=Image.Resampling.NEAREST, expand=True)
        if layer.opacity < 1.0:
            alpha = img.getchannel("A").point(lambda v: int(v * max(0.0, min(1.0, layer.opacity))))
            img.putalpha(alpha)
        canvas.alpha_composite(img, (int(round(layer.x)), int(round(layer.y))))
    created = create_asset(
        body.project_id, body.name, "workspace", canvas,
        meta={"workspace": {"width": w, "height": h, "layers": [l.model_dump() for l in body.layers]}},
        tags="workspace,composite",
    )
    return {"asset": created}


@router.get("/workspace/preview/{asset_id}")
def workspace_preview(asset_id: str) -> dict[str, Any]:
    asset = require_asset(asset_id)
    return {"asset": asset}
