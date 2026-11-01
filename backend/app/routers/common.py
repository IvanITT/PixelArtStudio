from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image

from ..services.images import decode_image, ensure_rgba
from ..services.storage import asset_file, get_asset, get_project, project_paths


def require_project(pid: str) -> dict[str, Any]:
    project = get_project(pid)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def require_asset(aid: str, project_id: str | None = None, kinds: set[str] | None = None) -> dict[str, Any]:
    asset = get_asset(aid)
    if not asset:
        raise HTTPException(404, "Asset not found")
    if project_id and asset["project_id"] != project_id:
        raise HTTPException(400, "Asset belongs to a different project")
    if kinds and asset["kind"] not in kinds:
        raise HTTPException(400, f"Asset kind '{asset['kind']}' is not valid here")
    return asset


def load_asset_image(asset: dict[str, Any], max_dim: int | None = None) -> Image.Image:
    paths = project_paths(asset["project_id"])
    path = asset_file(asset["project_id"], "assets", asset["filename"])
    try:
        img = Image.open(path)
        img.load()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Could not read asset image: {exc}") from exc
    if img.mode not in {"RGB", "RGBA"}:
        img = ensure_rgba(img)
    if max_dim and max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))), Image.Resampling.LANCZOS)
    return img


def read_upload(data: bytes) -> Image.Image:
    try:
        return decode_image(data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
