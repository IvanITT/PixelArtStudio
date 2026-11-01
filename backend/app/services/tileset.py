"""Tileset extraction, autotile metadata, procedural terrain tiles and helpers."""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Callable

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .images import average_hash, clamp_float, clamp_int, ensure_rgba, hamming
from .noise import cellular, fbm_spectral, ramp_color
from .pixelart import hex_to_rgb, nearest_palette_map

TERRAINS: dict[str, dict[str, Any]] = {
    "grass": {"ramp": ["#1f3a22", "#2f5a2d", "#3f7a38", "#57963f", "#7cbf52"], "edge": "#162a18", "accent": "#a6e06a"},
    "dirt": {"ramp": ["#3a2718", "#553a22", "#74512f", "#8f6a3e", "#b08a56"], "edge": "#24170e", "accent": "#c9a36a"},
    "stone": {"ramp": ["#34383e", "#4a4f57", "#616872", "#7d858f", "#9aa3ad"], "edge": "#202329", "accent": "#c3ccd6"},
    "water": {"ramp": ["#0b2a4a", "#0f4270", "#17679b", "#2a8fc4", "#63c4e8"], "edge": "#071c33", "accent": "#b3ecff"},
    "sand": {"ramp": ["#7a5f34", "#a4864c", "#c7a965", "#e0c987", "#f2e3ad"], "edge": "#5b4526", "accent": "#fff3c4"},
    "snow": {"ramp": ["#7a8ba3", "#a7b8cb", "#cddae7", "#e8f1f8", "#ffffff"], "edge": "#5a6b82", "accent": "#ffffff"},
    "wall": {"ramp": ["#2c2723", "#433b34", "#5d5148", "#786a5d", "#938476"], "edge": "#191512", "accent": "#b3a291"},
    "floor": {"ramp": ["#2a2d33", "#3b4048", "#4e555f", "#636c78", "#7d8794"], "edge": "#1b1e22", "accent": "#aab4c0"},
    "platform": {"ramp": ["#3a2a1c", "#5a4028", "#7d5b37", "#a17949", "#c49a63"], "edge": "#24180f", "accent": "#e0bd88"},
}

BITS = {"north": 1, "east": 2, "south": 4, "west": 8}


@dataclass
class Tile:
    image: Image.Image
    index: int
    row: int
    col: int
    source_x: int
    source_y: int
    sha: str
    ahash: str
    duplicate_of: int | None = None
    near_duplicate_of: int | None = None
    empty: bool = False
    tags: list[str] = field(default_factory=list)

    @property
    def width(self) -> int:
        return self.image.width

    @property
    def height(self) -> int:
        return self.image.height


def extract_tiles(
    img: Image.Image,
    options: dict[str, Any] | None = None,
    progress: Callable[[int, str], None] | None = None,
) -> list[Tile]:
    o = options or {}
    tile = clamp_int(o.get("tile_size"), 4, 256, 16)
    offset_x = clamp_int(o.get("offset_x"), 0, 512, 0)
    offset_y = clamp_int(o.get("offset_y"), 0, 512, 0)
    margin = clamp_int(o.get("margin"), 0, 256, 0)
    spacing = clamp_int(o.get("spacing"), 0, 64, 0)
    max_tiles = clamp_int(o.get("max_tiles"), 1, 16384, 4096)
    remove_empty = bool(o.get("remove_empty", True))
    detect_dups = bool(o.get("detect_duplicates", True))
    rgba = ensure_rgba(img)
    width, height = rgba.size
    usable_w = width - margin * 2 - offset_x
    usable_h = height - margin * 2 - offset_y
    step = tile + spacing
    cols = max(0, (usable_w + spacing) // step)
    rows = max(0, (usable_h + spacing) // step)
    if cols == 0 or rows == 0:
        raise ValueError("Image is smaller than the selected tile grid")
    tiles: list[Tile] = []
    hashes: dict[str, int] = {}
    ahash_list: list[str] = []
    index = 0
    for r in range(rows):
        for c in range(cols):
            if index >= max_tiles:
                return tiles
            x = margin + offset_x + c * step
            y = margin + offset_y + r * step
            if x + tile > width or y + tile > height:
                continue
            crop = rgba.crop((x, y, x + tile, y + tile))
            arr = np.asarray(crop, dtype=np.uint8)
            empty = bool(arr[..., 3].max() == 0) if arr.shape[2] == 4 else False
            sha = hashlib.sha256(arr.tobytes()).hexdigest()
            ah = average_hash(crop, 8)
            if remove_empty and empty:
                continue
            dup = None
            near = None
            if detect_dups:
                if sha in hashes:
                    dup = hashes[sha]
                else:
                    for i, prev in enumerate(ahash_list):
                        if hamming(prev, ah) <= 3:
                            near = i
                            break
            t = Tile(crop, index, r, c, x, y, sha, ah, dup, near, empty)
            tiles.append(t)
            hashes.setdefault(sha, index)
            ahash_list.append(ah)
            index += 1
        if progress:
            progress(10 + int(85 * (r + 1) / rows), f"Row {r + 1}/{rows}")
    if progress:
        progress(100, "Tiles extracted")
    return tiles


def tile_sort_key(tile: Tile, mode: str = "grid") -> Any:
    if mode == "grid":
        return (tile.row, tile.col)
    arr = np.asarray(tile.image.convert("RGB"), dtype=np.float32)
    if mode == "brightness":
        return float(arr.mean())
    if mode == "hue":
        hsv = cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_RGB2HSV)
        visible = hsv[..., 1] > 12
        return float(hsv[..., 0][visible].mean()) if visible.any() else -1
    if mode == "density":
        return -int((np.asarray(tile.image.getchannel("A")) > 8).sum())
    return tile.index


def tiles_to_sheet(tiles: list[Tile], columns: int = 8, spacing: int = 0, padding: int = 0) -> tuple[Image.Image, dict[str, Any]]:
    if not tiles:
        raise ValueError("No tiles to export")
    tile_size_w = max(t.width for t in tiles)
    tile_size_h = max(t.height for t in tiles)
    columns = max(1, min(columns, len(tiles)))
    rows = math.ceil(len(tiles) / columns)
    w = padding * 2 + columns * tile_size_w + (columns - 1) * spacing
    h = padding * 2 + rows * tile_size_h + (rows - 1) * spacing
    sheet = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    frames = []
    for i, t in enumerate(tiles):
        c, r = i % columns, i // columns
        x = padding + c * (tile_size_w + spacing)
        y = padding + r * (tile_size_h + spacing)
        sheet.alpha_composite(ensure_rgba(t.image), (x, y))
        frames.append({
            "index": i, "source_index": t.index, "x": x, "y": y,
            "w": t.width, "h": t.height, "duplicate_of": t.duplicate_of,
            "near_duplicate_of": t.near_duplicate_of,
        })
    meta = {
        "app": "Pixel Art & Game Asset Studio",
        "format": "RGBA8888",
        "image": "tileset.png",
        "size": {"w": w, "h": h},
        "columns": columns,
        "rows": rows,
        "tile_size": {"w": tile_size_w, "h": tile_size_h},
        "spacing": spacing,
        "padding": padding,
        "tiles": frames,
    }
    return sheet, meta


def recolor(img: Image.Image, hue_shift: float = 0, saturation: float = 1, brightness: float = 1, palette: list[str] | None = None) -> Image.Image:
    rgba = ensure_rgba(img)
    arr = np.asarray(rgba, dtype=np.uint8)
    rgb = arr[..., :3]
    alpha = arr[..., 3]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[..., 0] = (hsv[..., 0] + hue_shift / 2.0) % 180
    hsv[..., 1] = np.clip(hsv[..., 1] * saturation, 0, 255)
    hsv[..., 2] = np.clip(hsv[..., 2] * brightness, 0, 255)
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    if palette:
        pal = np.array([hex_to_rgb(c) for c in palette], dtype=np.uint8)
        idx = nearest_palette_map(out, pal)
        out = pal[idx]
    return Image.fromarray(np.dstack([out, alpha]), "RGBA")


def variation(img: Image.Image, kind: str, seed: int = 0) -> Image.Image:
    rng = np.random.default_rng(seed)
    out = ensure_rgba(img)
    if kind == "flip_h":
        out = out.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    elif kind == "flip_v":
        out = out.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    elif kind == "rotate_90":
        out = out.transpose(Image.Transpose.ROTATE_90)
    elif kind == "rotate_180":
        out = out.transpose(Image.Transpose.ROTATE_180)
    elif kind == "palette_shift":
        out = recolor(out, float(rng.uniform(-40, 40)), float(rng.uniform(0.85, 1.2)), float(rng.uniform(0.9, 1.1)))
    elif kind == "cracked":
        out = _add_cracks(out, seed)
    return out


def _add_cracks(img: Image.Image, seed: int) -> Image.Image:
    rgba = ensure_rgba(img).copy()
    draw = ImageDraw.Draw(rgba)
    rng = np.random.default_rng(seed)
    w, h = rgba.size
    for _ in range(max(1, w // 12)):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        for _ in range(int(rng.integers(2, 5))):
            nx = int(np.clip(x + rng.integers(-w // 6, w // 6), 0, w - 1))
            ny = int(np.clip(y + rng.integers(-h // 6, h // 6), 0, h - 1))
            draw.line([(x, y), (nx, ny)], fill=(20, 18, 22, 150), width=1)
            x, y = nx, ny
    return rgba


def make_seamless(img: Image.Image, band_ratio: float = 0.12) -> tuple[Image.Image, float, float]:
    """Approximate seamless texture via edge averaging and cosine blending.

    Returns (image, seam_error_before, seam_error_after). Seam error measures the
    mean absolute difference between wrapped border pixels.
    """
    rgba = ensure_rgba(img)
    arr = np.asarray(rgba, dtype=np.float32)
    h, w = arr.shape[:2]

    def seam_error(a: np.ndarray) -> float:
        if h < 2 or w < 2:
            return 0.0
        vert = np.abs(a[0, :, :3] - a[-1, :, :3]).mean()
        horiz = np.abs(a[:, 0, :3] - a[:, -1, :3]).mean()
        return float((vert + horiz) / 2)

    before = seam_error(arr)
    b = max(2, int(round(min(h, w) * np.clip(band_ratio, 0.02, 0.4))))
    b = min(b, w // 2, h // 2)
    if b < 1:
        return rgba, before, before
    top_target = (arr[0] + arr[-1]) / 2
    left_target = (arr[:, 0] + arr[:, -1]) / 2
    for i in range(b):
        weight = 0.5 * (1 + math.cos(math.pi * i / b))  # 1 at edge, 0 inside
        arr[i] = arr[i] * (1 - weight) + top_target * weight
        arr[h - 1 - i] = arr[h - 1 - i] * (1 - weight) + top_target * weight
        arr[:, i] = arr[:, i] * (1 - weight) + left_target * weight
        arr[:, w - 1 - i] = arr[:, w - 1 - i] * (1 - weight) + left_target * weight
    arr[0] = arr[-1] = top_target
    arr[:, 0] = arr[:, -1] = left_target
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    return out, before, seam_error(np.asarray(out, dtype=np.float32))


def _terrain_base(kind: str, size: int, seed: int) -> np.ndarray:
    cfg = TERRAINS.get(kind, TERRAINS["stone"])
    freq = fbm_spectral(size, size, seed=seed, beta=2.6)
    masks = fbm_spectral(size, size, seed=seed + 77, beta=3.4)
    t = np.clip(freq * 0.72 + masks * 0.28, 0, 1)
    t = np.round(t * 15) / 15  # quantize to 16 levels for pixel-art feel
    rgb = ramp_color(t, cfg["ramp"])
    if kind == "water":
        ripple = (np.sin(np.linspace(0, math.pi * 4, size))[None, :] * 0.06 + 0.94)
        rgb = np.clip(rgb.astype(np.float32) * ripple[..., None], 0, 255).astype(np.uint8)
    return rgb


def _autotile_image(base: np.ndarray, mask: int, kind: str, size: int) -> Image.Image:
    cfg = TERRAINS.get(kind, TERRAINS["stone"])
    arr = base.astype(np.float32).copy()
    edge = np.array(hex_to_rgb(cfg["edge"]), dtype=np.float32)
    accent = np.array(hex_to_rgb(cfg["accent"]), dtype=np.float32)
    thick = max(1, size // 16)
    missing = {
        "north": not (mask & BITS["north"]),
        "east": not (mask & BITS["east"]),
        "south": not (mask & BITS["south"]),
        "west": not (mask & BITS["west"]),
    }
    shade = 0.35
    # Outer dark edge where there is no neighbor.
    for side, absent in missing.items():
        if not absent:
            continue
        if side in {"north", "south"}:
            rows = slice(0, thick) if side == "north" else slice(size - thick, size)
            arr[rows, :] = arr[rows, :] * (1 - shade) + edge * shade
        else:
            cols = slice(0, thick) if side == "west" else slice(size - thick, size)
            arr[:, cols] = arr[:, cols] * (1 - shade) + edge * shade
    # Inner highlight just inside the edge.
    hi = np.clip(accent * 0.5 + arr * 0.5, 0, 255)
    if missing["north"]:
        arr[thick:thick + max(1, thick // 2), :] = arr[thick:thick + max(1, thick // 2), :] * 0.55 + hi[thick:thick + max(1, thick // 2), :] * 0.45
    if missing["west"]:
        arr[:, thick:thick + max(1, thick // 2)] = arr[:, thick:thick + max(1, thick // 2)] * 0.55 + hi[:, thick:thick + max(1, thick // 2)] * 0.45
    # Corner rounding where two adjacent sides are missing.
    corners = [
        (missing["north"] and missing["west"], 0, 0),
        (missing["north"] and missing["east"], size - thick * 2, 0),
        (missing["south"] and missing["west"], 0, size - thick * 2),
        (missing["south"] and missing["east"], size - thick * 2, size - thick * 2),
    ]
    for active, x, y in corners:
        if active and x >= 0 and y >= 0:
            arr[y:y + thick * 2, x:x + thick * 2] *= 0.82
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def generate_terrain_tileset(
    terrain: str,
    tile_size: int = 16,
    seed: int = 1337,
    variations: int = 1,
    progress: Callable[[int, str], None] | None = None,
) -> tuple[Image.Image, dict[str, Any], Image.Image]:
    if terrain not in TERRAINS:
        raise ValueError(f"Unknown terrain: {terrain}")
    tile_size = clamp_int(tile_size, 8, 64, 16)
    base = _terrain_base(terrain, tile_size, seed)
    tiles: list[Image.Image] = []
    entries: list[dict[str, Any]] = []
    for mask in range(16):
        img = _autotile_image(base, mask, terrain, tile_size)
        for v in range(max(1, min(variations, 6))):
            variant = img if v == 0 else _autotile_image(
                np.roll(base, (v * 3, v * 5), axis=(0, 1)), mask, terrain, tile_size
            )
            tiles.append(variant)
            entries.append({"mask": mask, "variation": v, "index": len(tiles) - 1})
        if progress:
            progress(5 + int(70 * (mask + 1) / 16), f"Mask {mask + 1}/16")
    columns = 4 * max(1, variations)
    sheet, meta = tiles_to_sheet(
        [Tile(t, i, i // columns, i % columns, 0, 0, "", "") for i, t in enumerate(tiles)],
        columns=columns,
    )
    cfg = TERRAINS[terrain]
    meta.update({
        "format": "pas-tileset",
        "terrain": terrain,
        "tile_size_px": tile_size,
        "seed": seed,
        "variations": max(1, min(variations, 6)),
        "autotile": {
            "type": "4-bit",
            "bits": BITS,
            "tiles": entries,
            "note": "mask = N|E*2|S*4|W*8 where a set bit means a connected neighbour exists.",
        },
        "palette": cfg["ramp"],
        "godot": {
            "tile_size": tile_size,
            "terrain_set": 0,
            "peering_bits": {"top_side": 1, "right_side": 2, "bottom_side": 4, "left_side": 8},
        },
    })
    preview = autotile_preview(terrain, tiles, tile_size, seed)
    if progress:
        progress(100, "Tileset ready")
    return sheet, meta, preview


def autotile_preview(
    terrain: str,
    tiles: list[Image.Image],
    tile_size: int,
    seed: int,
    grid_w: int = 14,
    grid_h: int = 8,
) -> Image.Image:
    rng = np.random.default_rng(seed + 991)
    solid = cellular(grid_w + 2, grid_h + 2, seed=seed + 5, fill=0.55, iterations=3, birth=5, survive=4).astype(bool)
    solid[:, 0] = solid[:, -1] = False
    solid[0, :] = solid[-1, :] = False
    sheet = Image.new("RGBA", (grid_w * tile_size, grid_h * tile_size), (0, 0, 0, 0))
    for y in range(grid_h):
        for x in range(grid_w):
            if not solid[y + 1, x + 1]:
                continue
            mask = 0
            if solid[y, x + 1]:
                mask |= BITS["north"]
            if solid[y + 1, x + 2]:
                mask |= BITS["east"]
            if solid[y + 2, x + 1]:
                mask |= BITS["south"]
            if solid[y + 1, x]:
                mask |= BITS["west"]
            base_index = mask * (len(tiles) // 16)
            idx = base_index % len(tiles)
            sheet.alpha_composite(tiles[idx].convert("RGBA"), (x * tile_size, y * tile_size))
    return sheet


def tileset_metadata_godot(meta: dict[str, Any]) -> str:
    """Emit a minimal Godot 4 TileSet resource referencing the PNG atlas."""
    tile = int(meta.get("tile_size_px") or meta.get("tile_size", {}).get("w", 16))
    cols = int(meta.get("columns", 1))
    rows = int(meta.get("rows", 1))
    return f"""[gd_resource type="TileSet" load_steps=2 format=3]

[ext_resource type="Texture2D" path="res://tileset.png" id="1_tex"]

[sub_resource type="TileSetAtlasSource" id="TileSetAtlasSource_1"]
texture = ExtResource("1_tex")
texture_region_size = Vector2i({tile}, {tile})
0:0/0 = 0

[resource]
tile_size = Vector2i({tile}, {tile})
sources/0 = SubResource("TileSetAtlasSource_1")
"""
