from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import safe_join
from ..services.images import image_to_bytes
from ..services.storage import create_asset, project_paths, update_project
from ..services.style import (
    DEFAULT_PROFILE,
    aggregate_report,
    analyze_image,
    apply_style,
    normalize_profile,
    profile_from_project,
)
from .common import load_asset_image, require_asset, require_project

router = APIRouter()


class ProfilePatch(BaseModel):
    profile: dict[str, Any] = Field(default_factory=dict)


class ApplyBody(BaseModel):
    project_id: str
    asset_ids: list[str] = Field(default_factory=list, max_length=120)
    profile: dict[str, Any] | None = None
    save: bool = True
    name_suffix: str = " styled"


class ReportBody(BaseModel):
    project_id: str
    asset_ids: list[str] = Field(default_factory=list, max_length=200)
    profile: dict[str, Any] | None = None
    limit: int = 60


SAVED_KINDS = {"pixelart", "sprite", "spritesheet", "tile", "tileset", "procedural", "false3d", "frame", "workspace"}


def _profile(project: dict[str, Any], raw: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_profile(raw) if raw is not None else profile_from_project(project)


def _store_profile(pid: str, profile: dict[str, Any]) -> None:
    update_project(pid, {"settings": {"style": profile}})


def _preview(pid: str, img, profile: dict[str, Any], asset: dict[str, Any]) -> str:
    paths = project_paths(pid)
    key = hashlib.sha256(
        (json.dumps(profile, sort_keys=True) + str(asset.get("sha256", ""))).encode("utf-8")
    ).hexdigest()[:24]
    target = safe_join(paths["previews"], f"style-{key}.png")
    target.write_bytes(image_to_bytes(img, "PNG"))
    return f"/api/files/{pid}/previews/{target.name}"


@router.get("/style/{pid}")
def get_style(pid: str) -> dict[str, Any]:
    project = require_project(pid)
    return {"profile": profile_from_project(project), "defaults": DEFAULT_PROFILE}


@router.patch("/style/{pid}")
def patch_style(pid: str, body: ProfilePatch) -> dict[str, Any]:
    project = require_project(pid)
    current = profile_from_project(project)
    merged = dict(current)
    merged.update(body.profile or {})
    profile = normalize_profile(merged)
    _store_profile(pid, profile)
    return {"profile": profile}


@router.post("/style/apply")
def apply(body: ApplyBody) -> dict[str, Any]:
    project = require_project(body.project_id)
    profile = _profile(project, body.profile)
    if not body.asset_ids:
        raise HTTPException(400, "Select at least one asset")
    _store_profile(body.project_id, profile)
    results: list[dict[str, Any]] = []
    for aid in body.asset_ids:
        asset = require_asset(aid, body.project_id)
        image = load_asset_image(asset, max_dim=2048)
        styled, info = apply_style(image, profile)
        payload: dict[str, Any] = {"source": asset, "info": info}
        if body.save:
            kind = asset["kind"] if asset["kind"] in SAVED_KINDS else "pixelart"
            suffix = body.name_suffix if body.name_suffix.strip() else " styled"
            tags = ",".join([*asset.get("tags", []), "styled"])
            created = create_asset(
                body.project_id,
                f"{asset['name']}{suffix}"[:120],
                kind,
                styled,
                meta={
                    "styled": True,
                    "style_profile": profile,
                    "style_info": info,
                    "source_asset_id": asset["id"],
                },
                tags=tags,
            )
            payload["asset"] = created
            payload["url"] = created["url"]
        else:
            payload["url"] = _preview(body.project_id, styled, profile, asset)
        results.append(payload)
    return {"profile": profile, "results": results, "count": len(results), "saved": body.save}


@router.post("/style/report")
def report(body: ReportBody) -> dict[str, Any]:
    project = require_project(body.project_id)
    profile = _profile(project, body.profile)
    limit = max(1, min(int(body.limit), 200))
    ids = body.asset_ids[:limit]
    assets: list[dict[str, Any]] = []
    if ids:
        for aid in ids:
            asset = require_asset(aid, body.project_id)
            if asset["kind"] in {"animation", "export"}:
                continue
            assets.append(asset)
    else:
        from ..services.storage import list_assets

        assets = [
            a
            for a in list_assets(body.project_id, limit=limit)
            if a["kind"] not in {"animation", "export", "source"} and a.get("width") and a.get("height")
        ][:limit]

    rows: list[dict[str, Any]] = []
    for asset in assets:
        try:
            image = load_asset_image(asset, max_dim=1024)
            metrics = analyze_image(image, profile)
        except Exception as exc:  # noqa: BLE001 - report should survive one broken asset
            rows.append(
                {
                    "asset_id": asset["id"],
                    "name": asset["name"],
                    "kind": asset["kind"],
                    "width": asset.get("width"),
                    "height": asset.get("height"),
                    "colors": 0,
                    "score": 0,
                    "error": str(exc),
                    "notes": ["Could not read this asset."],
                }
            )
            continue
        style_info = (asset.get("meta") or {}).get("style_info") or {}
        applied_scale = style_info.get("pixel_scale_after")
        if isinstance(applied_scale, (int, float)) and applied_scale > metrics["pixel_scale"]:
            metrics["pixel_scale"] = int(applied_scale)
        rows.append(
            {
                "asset_id": asset["id"],
                "name": asset["name"],
                "kind": asset["kind"],
                "width": asset.get("width"),
                "height": asset.get("height"),
                **metrics,
            }
        )
    return {"profile": profile, "rows": rows, "aggregate": aggregate_report(rows)}
