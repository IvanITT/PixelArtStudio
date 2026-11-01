"""Deterministic image → pixel-art pipeline.

All processing is CPU based. The pipeline is intentionally stateless so the
same input and options always produce the same output (K-Means is seeded).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

import cv2
import numpy as np
from PIL import Image, ImageEnhance

from .images import clamp_float, clamp_int, ensure_rgba, fit_within, from_numpy, resize
from .palettes import palette_by_id

BAYER8 = np.array(
    [
        [0, 32, 8, 40, 2, 34, 10, 42],
        [48, 16, 56, 24, 50, 18, 58, 26],
        [12, 44, 4, 36, 14, 46, 6, 38],
        [60, 28, 52, 20, 62, 30, 54, 22],
        [3, 35, 11, 43, 1, 33, 9, 41],
        [51, 19, 59, 27, 49, 17, 57, 25],
        [15, 47, 7, 39, 13, 45, 5, 37],
        [63, 31, 55, 23, 61, 29, 53, 21],
    ],
    dtype=np.float32,
)

FS_KERNEL = [(1, 0, 7 / 16), (-1, 1, 3 / 16), (0, 1, 5 / 16), (1, 1, 1 / 16)]
ATKINSON = [(1, 0, 1 / 8), (2, 0, 1 / 8), (-1, 1, 1 / 8), (0, 1, 1 / 8), (1, 1, 1 / 8), (0, 2, 1 / 8)]
JJN = [
    (1, 0, 7 / 48), (2, 0, 5 / 48),
    (-2, 1, 3 / 48), (-1, 1, 5 / 48), (0, 1, 7 / 48), (1, 1, 5 / 48), (2, 1, 3 / 48),
    (-2, 2, 1 / 48), (-1, 2, 3 / 48), (0, 2, 5 / 48), (1, 2, 3 / 48), (2, 2, 1 / 48),
]
DITHER_KERNELS = {"floyd": FS_KERNEL, "atkinson": ATKINSON, "jjn": JJN}


@dataclass
class PixelArtResult:
    image: Image.Image
    info: dict[str, Any] = field(default_factory=dict)


def _hex(c: np.ndarray | tuple[int, int, int]) -> str:
    r, g, b = [int(v) for v in c[:3]]
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    if len(v) == 3:
        v = "".join(ch * 2 for ch in v)
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def nearest_palette_map(arr: np.ndarray, palette: np.ndarray) -> np.ndarray:
    """Map HxWx3 uint8 array to palette indices using a 6-bit lookup table."""
    lut = _palette_lut(palette)
    q = (arr >> 2).astype(np.int32)
    idx = q[..., 0] * 4096 + q[..., 1] * 64 + q[..., 2]
    return lut[idx]


_LUT_CACHE: dict[bytes, np.ndarray] = {}


def _palette_lut(palette: np.ndarray) -> np.ndarray:
    key = palette.astype(np.uint8).tobytes()
    cached = _LUT_CACHE.get(key)
    if cached is not None:
        return cached
    levels = np.arange(64, dtype=np.float32) * 4 + 2
    grid = np.stack(np.meshgrid(levels, levels, levels, indexing="ij"), axis=-1).reshape(-1, 3)
    pal = palette.astype(np.float32)
    # Chunked distance computation keeps peak memory small.
    out = np.empty(grid.shape[0], dtype=np.int16)
    step = 8192
    for start in range(0, grid.shape[0], step):
        chunk = grid[start : start + step]
        d = ((chunk[:, None, :] - pal[None, :, :]) ** 2).sum(axis=2)
        out[start : start + step] = d.argmin(axis=1).astype(np.int16)
    if len(_LUT_CACHE) > 24:
        _LUT_CACHE.clear()
    _LUT_CACHE[key] = out
    return out


def _pil_palette(img: Image.Image, colors: int, method: str) -> tuple[np.ndarray, np.ndarray]:
    pil_method = {
        "median_cut": Image.Quantize.MEDIANCUT,
        "octree": Image.Quantize.FASTOCTREE,
        "adaptive": Image.Quantize.MAXCOVERAGE,
    }.get(method, Image.Quantize.MEDIANCUT)
    q = img.convert("RGB").quantize(colors=max(2, min(256, colors)), method=pil_method, dither=Image.Dither.NONE)
    used = np.array(sorted(q.getcolors(maxcolors=257) or []), dtype=np.int64)
    if len(used) == 0:
        return np.asarray(img.convert("RGB")), np.zeros((1, 3), np.uint8)
    indices = used[:, 1].astype(np.uint8)
    ind_arr = np.asarray(q, dtype=np.uint8)
    pal_full = np.array(q.getpalette()[:768], dtype=np.uint8).reshape(-1, 3)
    palette = pal_full[indices]
    remap = {int(v): i for i, v in enumerate(indices)}
    lut = np.zeros(256, dtype=np.uint8)
    for old, new in remap.items():
        lut[old] = new
    idx_arr = lut[ind_arr]
    rgb = palette[idx_arr]
    return rgb.astype(np.uint8), palette.astype(np.uint8)


def _kmeans_palette(img: Image.Image, colors: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    arr = np.asarray(img.convert("RGB"), dtype=np.uint8).reshape(-1, 3)
    total = arr.shape[0]
    if total > 60000:
        step = max(1, total // 60000)
        sample = arr[::step][:60000]
    else:
        sample = arr
    k = max(2, min(int(colors), 256, sample.shape[0]))
    cv2.setRNGSeed(int(seed) & 0x7FFFFFFF)
    data = np.float32(sample.reshape(-1, 3))
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 24, 1.0)
    _, labels, centers = cv2.kmeans(data, k, None, criteria, 2, cv2.KMEANS_PP_CENTERS)
    palette = np.clip(centers, 0, 255).astype(np.uint8)
    # Order by luminance for stable, aesthetically pleasing ramps.
    order = np.argsort(0.2126 * palette[:, 0] + 0.7152 * palette[:, 1] + 0.0722 * palette[:, 2])
    palette = palette[order]
    src = np.asarray(img.convert("RGB"), dtype=np.uint8)
    idx_arr = nearest_palette_map(src, palette)
    rgb = palette[idx_arr]
    return rgb, palette


def _custom_palette(img: Image.Image, palette: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    src = np.asarray(img.convert("RGB"), dtype=np.uint8)
    idx_arr = nearest_palette_map(src, palette)
    return palette[idx_arr], palette


def _background_mask(rgba: np.ndarray, bg: tuple[int, int, int], tolerance: float) -> np.ndarray:
    rgb = rgba[..., :3].astype(np.float32)
    dist = np.sqrt(((rgb - np.array(bg, dtype=np.float32)) ** 2).sum(axis=2))
    mask = dist <= tolerance
    if rgba.shape[2] == 4:
        mask |= rgba[..., 3] < 12
    return mask


def _dither(arr: np.ndarray, palette: np.ndarray, method: str, strength: float, mask: np.ndarray | None) -> np.ndarray:
    h, w = arr.shape[:2]
    if method == "bayer":
        matrix = (BAYER8 / 64.0 - 0.5) * (255.0 / max(2, len(palette)) ** 0.55) * strength * 2.0
        tile = np.tile(matrix, (h // 8 + 1, w // 8 + 1))[:h, :w]
        shifted = np.clip(arr.astype(np.float32) + tile[..., None], 0, 255)
        idx = nearest_palette_map(shifted.astype(np.uint8), palette)
        return palette[idx]

    kernel = DITHER_KERNELS.get(method, FS_KERNEL)
    work = arr.astype(np.float32).copy()
    lut = _palette_lut(palette)
    pal = palette.astype(np.int16)
    out = np.empty_like(arr)
    for y in range(h):
        row = work[y]
        q = (np.clip(row, 0, 255).astype(np.int16) >> 2)
        idx = lut[q[:, 0] * 4096 + q[:, 1] * 64 + q[:, 2]]
        chosen = pal[idx]
        out[y] = chosen
        err = (row - chosen) * strength
        for dx, dy, weight in kernel:
            ty = y + dy
            if ty >= h:
                continue
            xs = slice(max(0, dx), w + min(0, dx))
            xd = slice(max(0, -dx), w + min(0, -dx))
            work[ty, xd] += err[xs] * weight
            if mask is not None:
                work[ty, xd][mask[ty, xd]] = 0
    if mask is not None:
        out[mask] = 0
    return out


def process_pixel_art(
    image: Image.Image,
    options: dict[str, Any] | None = None,
    progress: Callable[[int, str], None] | None = None,
) -> PixelArtResult:
    t0 = time.perf_counter()
    o = options or {}
    max_out = 1024
    out_w = clamp_int(o.get("width"), 8, max_out, 0)
    out_h = clamp_int(o.get("height"), 8, max_out, 0)
    block = clamp_int(o.get("block_size"), 1, 16, 1)
    method = str(o.get("resize_method", "lanczos")).lower()
    if out_w <= 0 or out_h <= 0:
        scale = 256.0 / max(image.size)
        out_w = max(8, int(image.width * scale))
        out_h = max(8, int(image.height * scale))
    if o.get("pixel_grid"):
        out_w = max(block, (out_w // block) * block)
        out_h = max(block, (out_h // block) * block)
    work_w = max(1, int(round(out_w / block)))
    work_h = max(1, int(round(out_h / block)))

    src = image
    if src.mode not in {"RGBA", "RGB"}:
        src = ensure_rgba(src) if "transparency" in src.info else src.convert("RGB")
    has_alpha = src.mode == "RGBA"
    src_cap = 2400
    if max(src.size) > src_cap:
        src = fit_within(src, src_cap)
    if progress:
        progress(10, "Adjusting")

    rgb = src.convert("RGB")
    brightness = clamp_float(o.get("brightness"), 0.2, 2.0, 1.0)
    contrast = clamp_float(o.get("contrast"), 0.2, 2.0, 1.0)
    saturation = clamp_float(o.get("saturation"), 0.0, 2.0, 1.0)
    if abs(brightness - 1) > 1e-3:
        rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
    if abs(contrast - 1) > 1e-3:
        rgb = ImageEnhance.Contrast(rgb).enhance(contrast)
    if abs(saturation - 1) > 1e-3:
        rgb = ImageEnhance.Color(rgb).enhance(saturation)

    arr = np.asarray(rgb, dtype=np.uint8)
    alpha_src = np.asarray(src.getchannel("A"), dtype=np.uint8) if has_alpha else None

    denoise = clamp_int(o.get("denoise"), 0, 3, 0)
    if denoise:
        arr = cv2.medianBlur(arr, 3 + (denoise - 1) * 2)
    edge_preserve = clamp_int(o.get("edge_preserve"), 0, 100, 0)
    if edge_preserve:
        d = 5 if edge_preserve < 50 else 7
        arr = cv2.bilateralFilter(arr, d, 15 + edge_preserve * 0.9, 15 + edge_preserve * 0.9)

    if progress:
        progress(25, "Resizing")
    interp = {
        "nearest": cv2.INTER_NEAREST,
        "bilinear": cv2.INTER_LINEAR,
        "bicubic": cv2.INTER_CUBIC,
        "lanczos": cv2.INTER_LANCZOS4,
    }.get(method, cv2.INTER_LANCZOS4)
    small = cv2.resize(arr, (work_w, work_h), interpolation=interp)
    small_alpha = None
    if alpha_src is not None:
        small_alpha = cv2.resize(alpha_src, (work_w, work_h), interpolation=cv2.INTER_AREA)

    if o.get("edge_enhance", 0):
        amount = clamp_float(o.get("edge_enhance"), 0, 100, 0) / 100.0
        blur = cv2.GaussianBlur(small, (0, 0), 1.0)
        small = cv2.addWeighted(small, 1 + amount * 1.4, blur, -amount * 1.4, 0)

    # Transparency mask computed on the resized image before quantization.
    transparent = bool(o.get("transparent", False))
    bg_mask = None
    bg_hex = o.get("bg_color") or "#ffffff"
    tolerance = clamp_float(o.get("bg_tolerance"), 0, 200, 24)
    if transparent:
        if o.get("bg_color"):
            bg = hex_to_rgb(str(bg_hex))
        else:
            corners = np.concatenate(
                [small[0, :4], small[0, -4:], small[-1, :4], small[-1, -4:]], axis=0
            ).astype(np.float32)
            bg = tuple(int(v) for v in np.median(corners, axis=0))
        bg_mask = _background_mask(small, bg, tolerance)  # type: ignore[arg-type]
        if small_alpha is not None:
            bg_mask |= small_alpha < 12
        small = small.copy()
        small[bg_mask] = bg
    elif small_alpha is not None:
        bg_mask = small_alpha < 12

    if progress:
        progress(45, "Quantizing")
    quantizer = str(o.get("quantizer", "median_cut")).lower()
    colors = clamp_int(o.get("colors"), 2, 256, 16)
    custom = o.get("palette_colors")
    pid = o.get("palette_id")
    palette_hex = palette_by_id(pid) if pid else None
    if custom:
        palette_hex = [str(c) for c in custom]
    if palette_hex:
        pal = np.array([hex_to_rgb(c) for c in palette_hex], dtype=np.uint8)
        pal = pal[:256]
        if len(pal) < 2:
            pal = np.array([[0, 0, 0], [255, 255, 255]], dtype=np.uint8)
        rgb_small, palette = _custom_palette(Image.fromarray(small), pal)
        quantizer = "palette"
    elif quantizer == "kmeans":
        rgb_small, palette = _kmeans_palette(Image.fromarray(small), colors, int(o.get("seed", 1337)))
    else:
        rgb_small, palette = _pil_palette(Image.fromarray(small), colors, quantizer)
        if quantizer not in {"median_cut", "octree", "adaptive"}:
            quantizer = "median_cut"

    dither = str(o.get("dither", "none")).lower()
    strength = clamp_float(o.get("dither_strength"), 0.05, 1.0, 0.75)
    if dither in {"floyd", "atkinson", "jjn", "bayer"} and len(palette) > 1:
        if progress:
            progress(65, "Dithering")
        rgb_small = _dither(rgb_small, palette, dither, strength, bg_mask)

    out = Image.fromarray(np.asarray(rgb_small, dtype=np.uint8), "RGB")
    if (work_w, work_h) != (out_w, out_h):
        out = out.resize((out_w, out_h), Image.Resampling.NEAREST)
    if bg_mask is not None:
        mask_img = Image.fromarray((~bg_mask).astype(np.uint8) * 255, "L")
        if mask_img.size != (out_w, out_h):
            mask_img = mask_img.resize((out_w, out_h), Image.Resampling.NEAREST)
        out = out.convert("RGBA")
        out.putalpha(mask_img)
    else:
        out = out.convert("RGBA")

    used = np.unique(np.asarray(out.convert("RGB")).reshape(-1, 3), axis=0)
    used_hex = [_hex(c) for c in used]
    # Preserve palette order when restricting to a palette.
    if palette is not None and len(palette) <= 256:
        ordered = [_hex(c) for c in palette if _hex(c) in set(used_hex)]
        if ordered:
            used_hex = ordered

    elapsed = (time.perf_counter() - t0) * 1000
    if progress:
        progress(100, "Done")
    return PixelArtResult(
        image=out,
        info={
            "width": out_w,
            "height": out_h,
            "source_width": image.width,
            "source_height": image.height,
            "work_width": work_w,
            "work_height": work_h,
            "block_size": block,
            "resize_method": method,
            "quantizer": quantizer,
            "dither": dither,
            "palette": used_hex,
            "colors_used": len(used_hex),
            "duration_ms": round(elapsed, 2),
            "background_removed": transparent and bg_mask is not None,
        },
    )
