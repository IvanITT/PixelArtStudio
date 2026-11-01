from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..services.images import ensure_rgba
from ..services.storage import create_asset, get_asset, save_preview
from ..services.tileset import (
    TERRAINS,
    autotile_preview,
    extract_tiles,
    generate_terrain_tileset,
    make_seamless,
    recolor,
    tile_sort_key,
    tiles_to_sheet,
    variation,
)
from .common import load_asset_image, require_asset, require_project

router = APIRouter()


class ExtractBody(BaseModel):
    project_id: str
    asset_id: str
    options: dict[str, Any] = Field(default_factory=dict)


class SaveBody(ExtractBody):
    selected: list[int] | None = None
    columns: int = 8
    spacing: int = 0
    padding: int = 0
    name: str = "Tileset"
    recolor: dict[str, Any] | None = None
    variation: str | None = None


class TerrainBody(BaseModel):
    project_id: str
    terrain: str = "grass"
    tile_size: int = 16
    seed: int = 1337
    variations: int = 1
    name: str | None = None


class SeamlessBody(BaseModel):
    project_id: str
    asset_id: str
    band_ratio: float = 0.12
    save: bool = True
    name: str | None = None


class RecolorBody(BaseModel):
    project_id: str
    asset_id: str
    hue: float = 0
    saturation: float = 1
    brightness: float = 1
    palette: list[str] | None = None
    save: bool = False
    name: str | None = None


def _pipeline(tiles, options: dict[str, Any], rc: dict[str, Any] | None = None, variation_kind: str | None = None):
    sorted_tiles = sorted(tiles, key=lambda t: tile_sort_key(t, str(options.get("sort", "grid"))))
    out = []
    for i, t in enumerate(sorted_tiles):
        img = t.image
        if rc:
            img = recolor(
                img,
                float(rc.get("hue", 0) or 0),
                float(rc.get("saturation", 1) or 1),
                float(rc.get("brightness", 1) or 1),
                rc.get("palette"),
            )
        if variation_kind:
            img = variation(img, variation_kind, seed=1337 + i)
        out.append((t, img))
    return out


@router.get("/tileset/terrains")
def terrains() -> list[dict[str, Any]]:
    return [
        {"id": k, "name": k.capitalize(), "palette": v["ramp"], "edge": v["edge"]}
        for k, v in TERRAINS.items()
    ]


@router.post("/tileset/extract")
def extract(body: ExtractBody) -> dict[str, Any]:
    require_project(body.project_id)
    asset = require_asset(body.asset_id, body.project_id)
    img = load_asset_image(asset, max_dim=4096)
    try:
        tiles = extract_tiles(img, body.options)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    processed = _pipeline(tiles, body.options)
    max_preview = 400
    urls = []
    for i, (t, im) in enumerate(processed[:max_preview]):
        url = save_preview(body.project_id, im, f"tile-{asset['id']}-{t.index}-{t.sha[:8]}-{i}")
        urls.append({
            "index": t.index,
            "source_x": t.source_x,
            "source_y": t.source_y,
            "row": t.row,
            "col": t.col,
            "url": url,
            "duplicate_of": t.duplicate_of,
            "near_duplicate_of": t.near_duplicate_of,
            "empty": t.empty,
        })
    sheet_img, sheet_meta = tiles_to_sheet([t for t, _ in processed[:max_preview]], columns=min(16, max(1, int((max_preview) ** 0.5))), spacing=1, padding=1)
    sheet_url = save_preview(body.project_id, sheet_img, f"tilesheet-{asset['id']}-{len(processed)}-{body.options}")
    dupes = sum(1 for t in tiles if t.duplicate_of is not None)
    near = sum(1 for t in tiles if t.near_duplicate_of is not None)
    return {
        "tiles": urls,
        "total": len(tiles),
        "shown": len(urls),
        "duplicates": dupes,
        "near_duplicates": near,
        "tile_size": body.options.get("tile_size", 16),
        "sheet_url": sheet_url,
        "sheet": sheet_meta,
        "source_url": asset["url"],
        "truncated": len(tiles) > max_preview,
    }


@router.post("/tileset/save")
def save_tileset(body: SaveBody) -> dict[str, Any]:
    require_project(body.project_id)
    asset = require_asset(body.asset_id, body.project_id)
    img = load_asset_image(asset, max_dim=4096)
    try:
        tiles = extract_tiles(img, body.options)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    processed = _pipeline(tiles, body.options, body.recolor, body.variation)
    if body.selected is not None:
        selected = set(int(i) for i in body.selected)
        processed = [(t, im) for t, im in processed if t.index in selected]
    if not processed:
        raise HTTPException(400, "No tiles selected")
    sheet, meta = tiles_to_sheet(
        [type(t)(im, i, 0, i % max(1, body.columns), t.source_x, t.source_y, t.sha, t.ahash, t.duplicate_of, t.near_duplicate_of, t.empty) for i, (t, im) in enumerate(processed)],
        columns=body.columns,
        spacing=body.spacing,
        padding=body.padding,
    )
    meta.update({
        "format": "pas-tileset",
        "source_asset_id": asset["id"],
        "tile_size_px": int(body.options.get("tile_size", 16)),
        "extraction": body.options,
        "recolor": body.recolor,
        "variation": body.variation,
        "selected_source_indices": [t.index for t, _ in processed],
        "autotile": None,
    })
    created = create_asset(
        body.project_id, body.name, "tileset", sheet,
        meta=meta, tags="tileset,tiles",
    )
    return {"asset": created, "sheet": meta}


@router.post("/tileset/terrain")
def terrain(body: TerrainBody) -> dict[str, Any]:
    require_project(body.project_id)
    try:
        sheet, meta, preview = generate_terrain_tileset(body.terrain, body.tile_size, body.seed, body.variations)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    name = body.name or f"{body.terrain.capitalize()} autotile {body.tile_size}px"
    created = create_asset(
        body.project_id, name, "tileset", sheet,
        meta=meta, tags=f"tileset,autotile,{body.terrain}",
    )
    preview_url = save_preview(body.project_id, preview, f"autotile-{body.project_id}-{body.terrain}-{body.seed}-{body.tile_size}")
    tile_urls = []
    tile = body.tile_size
    variations = max(1, min(body.variations, 6))
    columns = meta.get("columns", 4 * variations)
    for mask in range(16):
        entry = next((e for e in meta["autotile"]["tiles"] if e["mask"] == mask and e["variation"] == 0), None)
        idx = entry["index"] if entry else mask * variations
        x = (idx % columns) * tile
        y = (idx // columns) * tile
        crop = sheet.crop((x, y, x + tile, y + tile))
        tile_urls.append({"mask": mask, "url": save_preview(body.project_id, crop, f"autotile-tile-{created['id']}-{mask}")})
    return {"asset": created, "sheet": meta, "preview_url": preview_url, "tiles": tile_urls, "terrain": body.terrain}


@router.post("/tileset/seamless")
def seamless(body: SeamlessBody) -> dict[str, Any]:
    require_project(body.project_id)
    asset = require_asset(body.asset_id, body.project_id)
    img = load_asset_image(asset)
    out, before, after = make_seamless(img, body.band_ratio)
    url = save_preview(body.project_id, out, f"seamless-{asset['id']}-{body.band_ratio}")
    saved = None
    if body.save:
        saved = create_asset(
            body.project_id, body.name or (asset["name"] + " seamless"), "tile", out,
            meta={"seamless_from": asset["id"], "seam_error_before": round(before, 2), "seam_error_after": round(after, 2)},
            tags="tile,seamless",
        )
    return {"url": url, "seam_error_before": round(before, 3), "seam_error_after": round(after, 3), "asset": saved}


@router.post("/tileset/recolor")
def recolor_asset(body: RecolorBody) -> dict[str, Any]:
    require_project(body.project_id)
    asset = require_asset(body.asset_id, body.project_id)
    img = load_asset_image(asset)
    out = recolor(img, body.hue, body.saturation, body.brightness, body.palette)
    url = save_preview(body.project_id, out, f"recolor-{asset['id']}-{body.hue}-{body.saturation}-{body.brightness}-{body.palette}")
    saved = None
    if body.save:
        saved = create_asset(
            body.project_id, body.name or (asset["name"] + " recolored"),
            "tile" if asset["kind"] in {"tile"} else asset["kind"], out,
            meta={"recolored_from": asset["id"], "recolor": body.model_dump(exclude={"project_id", "save", "name"})},
            tags="recolor",
        )
    return {"url": url, "asset": saved}


@router.get("/assets/{aid}/metadata")
def metadata(aid: str) -> Response:
    asset = get_asset(aid)
    if not asset:
        raise HTTPException(404, "Asset not found")
    payload = {
        "id": asset["id"],
        "name": asset["name"],
        "kind": asset["kind"],
        "width": asset["width"],
        "height": asset["height"],
        "meta": asset["meta"],
        "tags": asset["tags"],
        "created_at": asset["created_at"],
    }
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{asset["name"]}.json"'},
    )
