"""Reproducible CPU benchmarks for every image-processing module."""
from __future__ import annotations

import gc
import time
import tracemalloc
from typing import Any, Callable

import numpy as np
from PIL import Image

from ..config import new_id, now
from ..db import db
from . import animation, exporter, pixelart, procedural, pseudo3d, sprites, tileset
from .images import ensure_rgba


def _synthetic_photo(width: int = 1024, height: int = 768, seed: int = 7) -> Image.Image:
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:height, 0:width]
    r = 110 + 70 * np.sin(x / 80) + 30 * np.cos(y / 50) + rng.normal(0, 9, (height, width))
    g = 90 + 60 * np.sin((x + y) / 120) + rng.normal(0, 9, (height, width))
    b = 140 + 50 * np.cos(y / 70) + 20 * np.sin(x / 40) + rng.normal(0, 9, (height, width))
    arr = np.dstack([r, g, b])
    # a few shapes so sprites/tiles have structure
    arr[120:340, 150:420] = [210, 170, 90]
    arr[380:640, 480:820] = [60, 130, 180]
    arr[500:700, 100:300] = [90, 160, 90]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _sprites_fixture() -> Image.Image:
    img = Image.new("RGBA", (512, 256), (0, 0, 0, 0))
    from PIL import ImageDraw

    d = ImageDraw.Draw(img)
    colors = [(200, 70, 70, 255), (70, 200, 120, 255), (90, 120, 230, 255), (240, 200, 80, 255)]
    for i in range(4):
        for j in range(2):
            x, y = 20 + i * 120, 20 + j * 120
            d.ellipse([x, y, x + 70, y + 70], fill=colors[(i + j) % 4])
            d.rectangle([x + 20, y + 20, x + 50, y + 50], fill=(20, 20, 30, 255))
    return img


def _measure(fn: Callable[[], Any], module: str) -> dict[str, Any]:
    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()
    try:
        result = fn()
        error = None
    except Exception as exc:  # noqa: BLE001
        result = None
        error = f"{type(exc).__name__}: {exc}"
    elapsed = (time.perf_counter() - t0) * 1000
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "module": module,
        "ms": round(elapsed, 2),
        "peak_mb": round(peak / (1024 * 1024), 2),
        "error": error,
        "output": _describe(result),
    }


def _describe(result: Any) -> dict[str, Any]:
    info: dict[str, Any] = {}
    if isinstance(result, Image.Image):
        info = {"width": result.width, "height": result.height}
    elif isinstance(result, tuple) and result and isinstance(result[0], Image.Image):
        info = {"width": result[0].width, "height": result[0].height}
    elif isinstance(result, bytes):
        info = {"bytes": len(result)}
    elif isinstance(result, list):
        info = {"items": len(result)}
    elif isinstance(result, dict):
        info = {k: result[k] for k in ("width", "height", "count", "bytes") if k in result}
    return info


def run_benchmarks(progress: Callable[[int, str], None] | None = None) -> dict[str, Any]:
    photo = _synthetic_photo()
    small = photo.resize((512, 384), Image.Resampling.LANCZOS)
    sprite_src = _sprites_fixture()
    results: list[dict[str, Any]] = []

    def step(name: str, fn: Callable[[], Any], pct: int) -> None:
        if progress:
            progress(pct, name)
        results.append(_measure(fn, name))

    step("pixelart_preview", lambda: pixelart.process_pixel_art(small, {
        "width": 384, "height": 288, "colors": 24, "resize_method": "lanczos",
        "quantizer": "median_cut", "dither": "floyd", "edge_preserve": 20,
    }).image, 8)
    step("pixelart_kmeans", lambda: pixelart.process_pixel_art(small, {
        "width": 256, "height": 192, "colors": 16, "resize_method": "bicubic",
        "quantizer": "kmeans", "dither": "none", "seed": 42,
    }).image, 20)
    step("sprite_extract", lambda: sprites.extract_sprites(sprite_src, {"method": "auto_alpha", "min_area": 100}).sprites, 32)
    step("tileset_extract", lambda: tileset.extract_tiles(photo.resize((512, 512)), {"tile_size": 32}), 44)
    step("tileset_terrain", lambda: tileset.generate_terrain_tileset("grass", 32, 7, 1)[0], 54)
    step("procedural_x6", lambda: [procedural.generate_asset(g, None, 100 + i)[0] for i, g in enumerate(["tree", "chest", "house", "robot", "crystal", "tower"])], 66)
    step("false3d", lambda: pseudo3d.studio(small.resize((256, 256)), {"template": "iso_object"})[0], 76)
    frames = animation.template_frames(sprite_src.crop((20, 20, 100, 100)), "walk")
    step("animation_sheet", lambda: animation.pack_frames(frames)[0], 84)
    step("animation_gif", lambda: animation.export_gif(frames, 10), 90)
    step("zip_export", lambda: exporter.build_zip("bench", [{"id": "a", "name": "tree", "kind": "procedural", "meta": {}, "tags": []}], {"a": procedural.generate_asset("tree", None, 5)[0]})[0], 96)
    total = round(sum(r["ms"] for r in results), 2)
    payload = {
        "id": new_id(),
        "created_at": now(),
        "source": {"width": photo.width, "height": photo.height, "fixture": "synthetic 1024x768"},
        "results": results,
        "total_ms": total,
        "modules_ok": sum(1 for r in results if not r["error"]),
        "modules": len(results),
    }
    with db() as conn:
        conn.execute(
            "INSERT INTO benchmarks(id,module,metrics,created_at) VALUES(?,?,?,?)",
            (payload["id"], "all", __import__("json").dumps(payload), payload["created_at"]),
        )
    if progress:
        progress(100, "Benchmarks complete")
    return payload


def latest_benchmarks(limit: int = 10) -> list[dict[str, Any]]:
    import json

    with db() as conn:
        rows = conn.execute("SELECT * FROM benchmarks ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        try:
            out.append(json.loads(r["metrics"]))
        except Exception:
            pass
    return out
