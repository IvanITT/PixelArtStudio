"""Sprite extraction (segmentation + connected components) and sheet packing."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .images import clamp_float, clamp_int, ensure_rgba, from_numpy, hamming, average_hash, trim_transparent


@dataclass
class ExtractedSprite:
    image: Image.Image
    bbox: tuple[int, int, int, int]
    area: int
    name: str
    ahash: str


@dataclass
class ExtractionResult:
    sprites: list[ExtractedSprite] = field(default_factory=list)
    cutout: Image.Image | None = None
    background: tuple[int, int, int] | None = None
    warnings: list[str] = field(default_factory=list)


def _corner_bg(arr: np.ndarray) -> tuple[int, int, int]:
    h, w = arr.shape[:2]
    corners = np.concatenate([arr[0, :4], arr[0, -4:], arr[-1, :4], arr[-1, -4:]], axis=0)
    med = np.median(corners[:, :3], axis=0)
    return int(med[0]), int(med[1]), int(med[2])


def build_mask(img: Image.Image, options: dict[str, Any]) -> tuple[np.ndarray, tuple[int, int, int] | None, list[str]]:
    """Return a boolean mask of foreground pixels."""
    warnings: list[str] = []
    method = str(options.get("method", "auto_alpha"))
    tolerance = clamp_float(options.get("tolerance"), 1, 180, 28)
    rgba = np.asarray(ensure_rgba(img), dtype=np.uint8)
    rgb = rgba[..., :3].astype(np.float32)
    alpha = rgba[..., 3]
    bg: tuple[int, int, int] | None = None
    h, w = alpha.shape

    if method == "manual_rect":
        mask = np.zeros((h, w), dtype=bool)
        for rect in options.get("rects") or []:
            x, y, rw, rh = [int(v) for v in rect[:4]]
            x0, y0 = max(0, min(x, x + rw)), max(0, min(y, y + rh))
            x1, y1 = min(w, max(x, x + rw)), min(h, max(y, y + rh))
            mask[y0:y1, x0:x1] = True
        return mask, None, warnings

    if method == "manual_polygon":
        mask_img = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask_img)
        for poly in options.get("polygons") or []:
            pts = [(int(p[0]), int(p[1])) for p in poly if len(p) >= 2]
            if len(pts) >= 3:
                draw.polygon(pts, fill=255)
        return np.asarray(mask_img) > 0, None, warnings

    if method == "auto_alpha":
        if alpha.min() < 250:
            mask = alpha > 10
        else:
            bg = _corner_bg(rgba)
            mask = np.sqrt(((rgb - np.array(bg)) ** 2).sum(axis=2)) > tolerance
            warnings.append("Source has no transparency; used automatic corner-color segmentation.")
    elif method == "bg_color":
        if options.get("bg_color"):
            from .pixelart import hex_to_rgb

            bg = hex_to_rgb(str(options["bg_color"]))
        else:
            bg = _corner_bg(rgba)
        dist = np.sqrt(((rgb - np.array(bg, dtype=np.float32)) ** 2).sum(axis=2))
        mask = dist > tolerance
    elif method == "threshold":
        gray = np.asarray(img.convert("L"), dtype=np.uint8)
        thresh = clamp_int(options.get("threshold"), 0, 255, 128)
        mask = gray < thresh if options.get("invert") else gray > thresh
    elif method == "color":
        from .pixelart import hex_to_rgb

        target = hex_to_rgb(str(options.get("target_color") or "#ff00ff"))
        dist = np.sqrt(((rgb - np.array(target, dtype=np.float32)) ** 2).sum(axis=2))
        mask = dist <= tolerance
        if options.get("color_mode") == "remove":
            mask = ~mask
    elif method == "regions":
        if alpha.min() < 250:
            mask = alpha > 10
        else:
            bg = _corner_bg(rgba)
            mask = np.sqrt(((rgb - np.array(bg, dtype=np.float32)) ** 2).sum(axis=2)) > tolerance
    else:
        mask = alpha > 10

    if options.get("remove_bg", True) and alpha.min() < 250:
        mask &= alpha > 10
    return mask, bg, warnings


def _sort_boxes(boxes: list[tuple[int, int, int, int, int]]) -> list[tuple[int, int, int, int, int]]:
    """Reading order with row grouping."""
    if not boxes:
        return []
    avg_h = sorted(b[3] for b in boxes)[len(boxes) // 2]
    tol = max(4, int(avg_h * 0.45))
    return sorted(boxes, key=lambda b: (round(b[1] / tol), b[0]))


def extract_sprites(
    img: Image.Image,
    options: dict[str, Any] | None = None,
    progress: Callable[[int, str], None] | None = None,
) -> ExtractionResult:
    o = options or {}
    result = ExtractionResult()
    if max(img.size) > 2600:
        ratio = 2600 / max(img.size)
        img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))), Image.Resampling.LANCZOS)
        result.warnings.append("Source was downscaled to 2600 px for extraction.")

    mask, bg, warns = build_mask(img, o)
    result.background = bg
    result.warnings.extend(warns)
    if progress:
        progress(25, "Segmenting")

    gap = clamp_int(o.get("merge_gap"), 0, 128, 0)
    groups = None
    group_count = 0
    if gap:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (gap * 2 + 1, gap * 2 + 1))
        grown = cv2.dilate(
            mask.astype(np.uint8), k, borderType=cv2.BORDER_CONSTANT, borderValue=0
        )
        group_count, groups = cv2.connectedComponents(grown, connectivity=8)

    min_area = clamp_int(o.get("min_area"), 1, 2_000_000, 24)
    max_sprites = clamp_int(o.get("max_sprites"), 1, 2000, 300)
    method = str(o.get("method", "auto_alpha"))
    padding = clamp_int(o.get("padding"), 0, 64, 0)
    normalize = bool(o.get("normalize", False))
    norm_size = clamp_int(o.get("normalize_size"), 4, 512, 0)
    trim = bool(o.get("trim", True))

    boxes: list[tuple[int, int, int, int, int]] = []
    glyph_only = method in {"manual_rect", "manual_polygon"}
    if glyph_only:
        if method == "manual_rect":
            for rect in o.get("rects") or []:
                x, y, rw, rh = [int(v) for v in rect[:4]]
                x0, y0 = max(0, min(x, x + rw)), max(0, min(y, y + rh))
                x1, y1 = min(img.width, max(x, x + rw)), min(img.height, max(y, y + rh))
                if x1 > x0 and y1 > y0:
                    boxes.append((x0, y0, x1 - x0, y1 - y0, (x1 - x0) * (y1 - y0)))
        else:
            ys, xs = np.where(mask)
            if len(xs):
                boxes.append((int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1), len(xs)))
    else:
        if groups is not None:
            # Merge nearby components into single sprites without distorting the
            # original mask: proximity is decided on a dilated copy, bounding
            # boxes come from the real foreground pixels of each group.
            for gid in range(1, group_count):
                sel = (groups == gid) & mask
                area = int(sel.sum())
                if area < min_area:
                    continue
                ys, xs = np.nonzero(sel)
                if not len(xs):
                    continue
                x0, y0 = int(xs.min()), int(ys.min())
                x1, y1 = int(xs.max()) + 1, int(ys.max()) + 1
                boxes.append((x0, y0, x1 - x0, y1 - y0, area))
            boxes = _sort_boxes(boxes)[:max_sprites]
        else:
            num, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
            for i in range(1, num):
                x, y, bw, bh, area = [int(v) for v in stats[i]]
                if area < min_area or bw < 2 or bh < 2:
                    continue
                boxes.append((x, y, bw, bh, area))
            boxes = _sort_boxes(boxes)[:max_sprites]

    rgba = ensure_rgba(img)
    rgb_arr = np.asarray(rgba.convert("RGB"), dtype=np.uint8)
    alpha_arr = np.asarray(rgba.getchannel("A"), dtype=np.uint8)
    selected_mask = np.zeros((alpha_arr.shape[0], alpha_arr.shape[1]), dtype=bool)
    allow_full_rect = method == "manual_rect" and not o.get("remove_bg", True)
    if allow_full_rect:
        for rect in o.get("rects") or []:
            x, y, rw, rh = [int(v) for v in rect[:4]]
            x0, y0 = max(0, min(x, x + rw)), max(0, min(y, y + rh))
            x1, y1 = min(rgba.width, max(x, x + rw)), min(rgba.height, max(y, y + rh))
            selected_mask[y0:y1, x0:x1] = True
    else:
        for (x, y, bw, bh, _area) in boxes:
            selected_mask[y:y + bh, x:x + bw] |= mask[y:y + bh, x:x + bw]

    for idx, (x, y, bw, bh, area) in enumerate(boxes, start=1):
        x0 = max(0, x - padding)
        y0 = max(0, y - padding)
        x1 = min(rgba.width, x + bw + padding)
        y1 = min(rgba.height, y + bh + padding)
        crop = rgba.crop((x0, y0, x1, y1))
        if allow_full_rect:
            crop_mask = np.ones((y1 - y0, x1 - x0), dtype=bool)
        else:
            crop_mask = selected_mask[y0:y1, x0:x1]
        a = np.asarray(crop.getchannel("A"), dtype=np.uint8).copy()
        a[~crop_mask] = 0
        crop.putalpha(Image.fromarray(a))
        if trim:
            crop = trim_transparent(crop, 0)
        if normalize:
            size = norm_size or max(crop.width, crop.height)
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            canvas.alpha_composite(crop, ((size - crop.width) // 2, (size - crop.height) // 2))
            crop = canvas
        result.sprites.append(
            ExtractedSprite(
                image=crop,
                bbox=(x, y, bw, bh),
                area=area,
                name=f"sprite_{idx:03d}",
                ahash=average_hash(crop),
            )
        )
        if progress and idx % 12 == 0:
            progress(30 + int(60 * idx / max(1, len(boxes))), f"Sprite {idx}/{len(boxes)}")

    cutout_alpha = np.minimum(alpha_arr, (selected_mask.astype(np.uint8) * 255))
    cutout_rgba = np.dstack([rgb_arr, cutout_alpha])
    result.cutout = Image.fromarray(cutout_rgba, "RGBA")
    if progress:
        progress(100, "Extraction complete")
    return result


def pack_spritesheet(
    images: list[Image.Image],
    names: list[str] | None = None,
    options: dict[str, Any] | None = None,
) -> tuple[Image.Image, dict[str, Any]]:
    o = options or {}
    if not images:
        raise ValueError("No sprites selected")
    padding = clamp_int(o.get("padding"), 0, 128, 0)
    spacing = clamp_int(o.get("spacing"), 0, 64, 0)
    cell_w = clamp_int(o.get("cell_width"), 1, 2048, 0)
    cell_h = clamp_int(o.get("cell_height"), 1, 2048, 0)
    max_dim = clamp_int(o.get("max_dim"), 256, 16384, 8192)
    columns = clamp_int(o.get("columns"), 1, 64, 0)
    n = len(images)
    if cell_w <= 0:
        cell_w = max(im.width for im in images)
    if cell_h <= 0:
        cell_h = max(im.height for im in images)
    if columns <= 0:
        columns = max(1, math.ceil(math.sqrt(n)))
        while columns * (cell_w + spacing) > max_dim and columns > 1:
            columns -= 1
    rows = math.ceil(n / columns)
    while rows * (cell_h + spacing) + padding * 2 - spacing > max_dim and rows > 1:
        columns += 1
        rows = math.ceil(n / columns)
    sheet_w = padding * 2 + columns * cell_w + max(0, columns - 1) * spacing
    sheet_h = padding * 2 + rows * cell_h + max(0, rows - 1) * spacing
    if sheet_w > max_dim or sheet_h > max_dim:
        raise ValueError(f"Sheet would exceed max dimensions ({sheet_w}x{sheet_h} > {max_dim})")
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
    frames: dict[str, Any] = {}
    for i, im in enumerate(images):
        col, row = i % columns, i // columns
        x = padding + col * (cell_w + spacing)
        y = padding + row * (cell_h + spacing)
        sw, sh = im.size
        ox = (cell_w - sw) // 2
        oy = (cell_h - sh) // 2
        sheet.alpha_composite(ensure_rgba(im), (x + ox, y + oy))
        name = (names[i] if names and i < len(names) else f"sprite_{i + 1:03d}")
        frames[name] = {
            "frame": {"x": x + ox, "y": y + oy, "w": sw, "h": sh},
            "rotated": False,
            "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": sw, "h": sh},
            "sourceSize": {"w": sw, "h": sh},
        }
    meta = {
        "app": "Pixel Art & Game Asset Studio",
        "version": "1.0",
        "image": "spritesheet.png",
        "format": "RGBA8888",
        "size": {"w": sheet_w, "h": sheet_h},
        "scale": "1",
        "columns": columns,
        "rows": rows,
        "cell": {"w": cell_w, "h": cell_h},
        "padding": padding,
        "spacing": spacing,
        "frames": frames,
    }
    return sheet, meta


def tile_image(img: Image.Image, count: int = 1, spacing: int = 0, background: str = "transparent") -> Image.Image:
    """Utility used by tests/previews to preview repeats."""
    w, h = img.size
    out = Image.new("RGBA", (w * count + spacing * (count - 1), h), (0, 0, 0, 0))
    for i in range(count):
        out.alpha_composite(ensure_rgba(img), (i * (w + spacing), 0))
    return out
