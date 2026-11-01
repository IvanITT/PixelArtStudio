from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.pseudo3d import TEMPLATES, heightmap, studio
from ..services.storage import create_asset, save_preview
from .common import load_asset_image, require_asset, require_project

router = APIRouter()


class StudioBody(BaseModel):
    project_id: str
    asset_id: str
    options: dict[str, Any] = Field(default_factory=dict)
    save: bool = False
    name: str | None = None


class HeightBody(BaseModel):
    project_id: str
    asset_id: str
    blur: float = 2.0
    invert: bool = False
    save: bool = False
    name: str | None = None


@router.get("/false3d/templates")
def templates() -> dict[str, Any]:
    return {
        "templates": [
            {"id": k, **{kk: vv for kk, vv in v.items()}}
            for k, v in TEMPLATES.items()
        ],
        "disclaimer": "False 3D is a 2.5D simulation. It cannot recover unseen geometry from a single photo.",
    }


@router.post("/false3d/preview")
def preview(body: StudioBody) -> dict[str, Any]:
    require_project(body.project_id)
    asset = require_asset(body.asset_id, body.project_id)
    img = load_asset_image(asset, max_dim=640)
    out, info = studio(img, body.options)
    url = save_preview(body.project_id, out, f"false3d-{asset['id']}-{body.options}")
    saved = None
    if body.save:
        saved = create_asset(
            body.project_id, body.name or (asset["name"] + " 2.5D"), "false3d", out,
            meta={**info, "source_asset_id": asset["id"], "options": body.options},
            tags="false3d,2.5d",
        )
    return {"url": url, "info": info, "asset": saved, "source_url": asset["url"]}


@router.post("/false3d/heightmap")
def height(body: HeightBody) -> dict[str, Any]:
    require_project(body.project_id)
    asset = require_asset(body.asset_id, body.project_id)
    img = load_asset_image(asset, max_dim=1024)
    out = heightmap(img, body.blur, body.invert)
    url = save_preview(body.project_id, out, f"height-{asset['id']}-{body.blur}-{body.invert}")
    saved = None
    if body.save:
        saved = create_asset(
            body.project_id, body.name or (asset["name"] + " heightmap"), "false3d", out,
            meta={"heightmap": True, "blur": body.blur, "invert": body.invert, "source_asset_id": asset["id"]},
            tags="heightmap,false3d",
        )
    return {"url": url, "asset": saved}
