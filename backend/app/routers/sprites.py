from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.images import ensure_rgba
from ..services.sprites import extract_sprites, pack_spritesheet
from ..services.storage import create_asset, get_asset, project_paths, save_preview
from .common import load_asset_image, require_asset, require_project

router = APIRouter()


class ExtractBody(BaseModel):
    project_id: str
    asset_id: str
    options: dict[str, Any] = Field(default_factory=dict)
    save: bool = True
    name_prefix: str = "sprite"


class PackBody(BaseModel):
    project_id: str
    sprite_ids: list[str]
    options: dict[str, Any] = Field(default_factory=dict)
    name: str = "Spritesheet"


class AdjustBody(BaseModel):
    trim: bool = True
    padding: int = 0
    width: int = 0
    height: int = 0
    method: str = "nearest"
    name: str | None = None


@router.post("/sprites/extract")
def extract(body: ExtractBody) -> dict[str, Any]:
    require_project(body.project_id)
    source = require_asset(body.asset_id, body.project_id)
    img = load_asset_image(source, max_dim=2600)
    result = extract_sprites(img, body.options)
    group = hashlib.sha256(
        (source["id"] + str(sorted(body.options.items()))).encode()
    ).hexdigest()[:12]
    cutout_url = None
    if result.cutout is not None:
        cutout_url = save_preview(body.project_id, result.cutout, f"sprite-cutout-{group}")
    out_sprites: list[dict[str, Any]] = []
    seen_hashes: dict[str, str] = {}
    for i, sprite in enumerate(result.sprites):
        duplicate_of = seen_hashes.get(sprite.ahash)
        if not duplicate_of:
            seen_hashes[sprite.ahash] = f"preview_{i}"
        if body.save:
            asset = create_asset(
                body.project_id,
                f"{body.name_prefix}_{i + 1:03d}",
                "sprite",
                sprite.image,
                meta={
                    "bbox": list(sprite.bbox),
                    "area": sprite.area,
                    "ahash": sprite.ahash,
                    "extraction_group": group,
                    "source_asset_id": source["id"],
                    "method": body.options.get("method", "auto_alpha"),
                    "near_duplicate_of": duplicate_of,
                },
                tags="sprite,extracted",
            )
            out_sprites.append(asset)
        else:
            url = save_preview(body.project_id, sprite.image, f"sprite-{group}-{i}-{sprite.ahash}")
            out_sprites.append({
                "id": f"preview_{i}", "name": f"{body.name_prefix}_{i + 1:03d}",
                "url": url, "thumb_url": url, "width": sprite.image.width,
                "height": sprite.image.height, "kind": "sprite", "preview": True,
                "meta": {"bbox": list(sprite.bbox), "area": sprite.area, "ahash": sprite.ahash,
                         "near_duplicate_of": duplicate_of},
                "bbox": list(sprite.bbox),
            })
    return {
        "sprites": out_sprites,
        "count": len(out_sprites),
        "warnings": result.warnings,
        "cutout_url": cutout_url,
        "group": group,
        "background": result.background,
        "saved": body.save,
        "duplicates": sum(1 for s in out_sprites if (s.get("meta") or {}).get("near_duplicate_of")),
    }


@router.post("/sprites/pack")
def pack(body: PackBody) -> dict[str, Any]:
    require_project(body.project_id)
    if not body.sprite_ids:
        raise HTTPException(400, "Select at least one sprite")
    if len(body.sprite_ids) > 500:
        raise HTTPException(400, "Sprite sheet limit is 500 cells")
    images = []
    names = []
    for aid in body.sprite_ids:
        asset = require_asset(aid, body.project_id)
        images.append(load_asset_image(asset))
        names.append(asset["name"])
    try:
        sheet, meta = pack_spritesheet(images, names, body.options)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    asset = create_asset(
        body.project_id,
        body.name,
        "spritesheet",
        sheet,
        meta={"sheet": meta, "source_ids": body.sprite_ids, **{k: v for k, v in body.options.items() if k != "max_dim"}},
        tags="spritesheet",
    )
    return {"asset": asset, "sheet": meta, "url": asset["url"]}


@router.post("/sprites/{aid}/adjust")
def adjust(aid: str, body: AdjustBody) -> dict[str, Any]:
    asset = require_asset(aid)
    if asset["kind"] != "sprite":
        raise HTTPException(400, "Only sprite assets can be adjusted")
    img = load_asset_image(asset).convert("RGBA")
    from ..services.images import trim_transparent

    out = img
    if body.trim:
        out = trim_transparent(out, max(0, min(64, body.padding)))
    if body.width > 0 and body.height > 0:
        w = max(1, min(2048, body.width))
        h = max(1, min(2048, body.height))
        from PIL import Image

        resample = {
            "nearest": Image.Resampling.NEAREST,
            "bilinear": Image.Resampling.BILINEAR,
            "bicubic": Image.Resampling.BICUBIC,
            "lanczos": Image.Resampling.LANCZOS,
        }.get(body.method, Image.Resampling.NEAREST)
        out = out.resize((w, h), resample)
    created = create_asset(
        asset["project_id"], body.name or (asset["name"] + " adjusted"), "sprite", out,
        meta={**asset["meta"], "adjusted_from": asset["id"], "bbox": [0, 0, out.width, out.height]},
        tags="sprite,adjusted",
    )
    return {"asset": created}


@router.get("/sprites/{aid}/sheet")
def sprite_sheet_for(aid: str, columns: int = 0, padding: int = 0, spacing: int = 0) -> dict[str, Any]:
    asset = require_asset(aid)
    if asset["kind"] != "spritesheet":
        raise HTTPException(400, "Not a spritesheet asset")
    meta = asset["meta"].get("sheet") or {}
    return {"asset": asset, "sheet": meta}
