from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.procedural import GENERATORS, catalog, generate_variations
from ..services.storage import create_asset, save_preview
from .common import require_project

router = APIRouter()


class GenerateBody(BaseModel):
    project_id: str
    generator: str
    params: dict[str, Any] = Field(default_factory=dict)
    seed: int = 1337
    count: int = 4
    save: bool = True
    name: str | None = None


@router.get("/procedural/catalog")
def get_catalog() -> list[dict[str, Any]]:
    return catalog()


@router.post("/procedural/generate")
def generate(body: GenerateBody) -> dict[str, Any]:
    require_project(body.project_id)
    if body.generator not in GENERATORS:
        raise HTTPException(404, "Unknown generator")
    count = max(1, min(body.count, 12))
    seed = int(body.seed)
    try:
        results = generate_variations(body.generator, body.params, seed, count)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Generator failed: {exc}") from exc
    items = []
    for i, (img, info) in enumerate(results):
        if body.save:
            asset = create_asset(
                body.project_id,
                body.name or f"{info['name']} {seed + i}",
                "procedural",
                img,
                meta={**info, "seed": seed + i},
                tags=f"procedural,{info['group']},{body.generator}",
            )
            items.append({"asset": asset, "info": info, "url": asset["url"], "seed": seed + i})
        else:
            url = save_preview(body.project_id, img, f"proc-{body.generator}-{seed + i}-{body.params}")
            items.append({"asset": None, "info": info, "url": url, "seed": seed + i})
    return {"generator": body.generator, "items": items, "count": len(items), "seed_family": [seed + i for i in range(count)]}


@router.get("/procedural/{generator}")
def generator_detail(generator: str) -> dict[str, Any]:
    for item in catalog():
        if item["id"] == generator:
            return item
    raise HTTPException(404, "Unknown generator")
