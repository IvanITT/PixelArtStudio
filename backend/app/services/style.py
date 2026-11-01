"""Asset style consistency: shared profiles, style transfer and reports.

A style profile is a small, deterministic description of how every generated
asset in a project should look: palette, colour budget, pixel scale, outline,
shading and basic colour grading. Applying a profile is a pure CPU operation,
so the same input and profile always produce identical output on this machine.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from scipy import ndimage

from .images import ensure_rgba
from .palettes import normalize_hex, palette_by_id
from .pixelart import hex_to_rgb, nearest_palette_map

DEFAULT_PROFILE: dict[str, Any] = {
    "palette_id": None,
    "colors": [],
    "max_colors": 0,
    "pixel_scale": 1,
    "outline": "none",
    "outline_width": 1,
    "outline_color": "#0b0b12",
    "brightness": 100,
    "contrast": 100,
    "saturation": 100,
    "shading_steps": 0,
    "dither": "none",
}

OUTLINES = {"none", "dark", "light", "custom"}
DITHERS = {"none", "bayer"}

_BAYER = np.array(
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
_BAYER = (_BAYER + 0.5) / 64.0 - 0.5


def _clamp(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return max(lo, min(hi, number))


def _colors(value: Any) -> list[str]:
    if isinstance(value, str):
        value = value.replace(";", ",").split(",")
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value:
        normalized = normalize_hex(str(raw))
        if normalized and normalized not in out:
            out.append(normalized)
    return out[:128]


def normalize_profile(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Validate a profile and resolve its palette into an explicit colour list."""
    data = dict(DEFAULT_PROFILE)
    if isinstance(raw, dict):
        for key in data:
            if key in raw:
                data[key] = raw[key]
    palette_id = data.get("palette_id")
    colors = _colors(data.get("colors"))
    if palette_id:
        resolved = palette_by_id(str(palette_id))
        if resolved:
            colors = _colors(resolved)
        else:
            palette_id = None
    data["palette_id"] = str(palette_id) if palette_id else None
    data["colors"] = colors
    data["max_colors"] = int(_clamp(data.get("max_colors"), 0, 64, 0))
    data["pixel_scale"] = int(_clamp(data.get("pixel_scale"), 1, 8, 1))
    outline = str(data.get("outline") or "none").lower()
    data["outline"] = outline if outline in OUTLINES else "none"
    data["outline_width"] = int(_clamp(data.get("outline_width"), 1, 4, 1))
    data["outline_color"] = normalize_hex(str(data.get("outline_color") or DEFAULT_PROFILE["outline_color"])) or "#0b0b12"
    data["brightness"] = int(_clamp(data.get("brightness"), 20, 200, 100))
    data["contrast"] = int(_clamp(data.get("contrast"), 20, 200, 100))
    data["saturation"] = int(_clamp(data.get("saturation"), 0, 200, 100))
    data["shading_steps"] = int(_clamp(data.get("shading_steps"), 0, 8, 0))
    dither = str(data.get("dither") or "none").lower()
    data["dither"] = dither if dither in DITHERS else "none"
    return data


def profile_from_project(project: dict[str, Any] | None) -> dict[str, Any]:
    settings = (project or {}).get("settings") or {}
    return normalize_profile(settings.get("style") if isinstance(settings, dict) else None)


def _outline_rgb(profile: dict[str, Any]) -> tuple[int, int, int] | None:
    mode = profile["outline"]
    if mode == "none":
        return None
    if mode == "dark":
        return hex_to_rgb("#0b0b12")
    if mode == "light":
        return hex_to_rgb("#f4ecd8")
    return hex_to_rgb(profile["outline_color"])


def _unique_colors(rgb: np.ndarray, mask: np.ndarray) -> int:
    if not mask.any():
        return 0
    pixels = rgb[mask]
    if pixels.size == 0:
        return 0
    return int(np.unique(pixels.reshape(-1, 3), axis=0).shape[0])


def _palette_coverage(rgb: np.ndarray, mask: np.ndarray, colors: list[str], tolerance: float = 38.0) -> float | None:
    if not colors or not mask.any():
        return None
    palette = np.array([hex_to_rgb(c) for c in colors], dtype=np.uint8)
    pixels = rgb[mask].reshape(-1, 3)
    if pixels.size == 0:
        return 0.0
    # Quantize in chunks to keep memory bounded for large assets.
    mapped = np.empty_like(pixels)
    for start in range(0, len(pixels), 200_000):
        chunk = pixels[start : start + 200_000]
        idx = nearest_palette_map(chunk.reshape(1, -1, 3), palette).reshape(-1)
        mapped[start : start + 200_000] = palette[idx]
    distance = np.sqrt(((pixels.astype(np.float32) - mapped.astype(np.float32)) ** 2).sum(axis=1))
    return float((distance <= tolerance).mean())


def _estimate_pixel_scale(rgb: np.ndarray, mask: np.ndarray) -> int:
    """Infer the pixel block size from the alignment of colour boundaries.

    For an image produced by nearest-neighbour upscaling every colour boundary
    lands on a multiple of the block size, so the GCD of boundary coordinates is
    the block size. Flat images have no boundaries and stay at scale 1.
    """
    if rgb.shape[0] < 4 or rgb.shape[1] < 4 or not mask.any():
        return 1
    values = rgb.astype(np.int16)
    horizontal = np.abs(values[:, 1:] - values[:, :-1]).max(axis=2)
    vertical = np.abs(values[1:, :] - values[:-1, :]).max(axis=2)
    hm = mask[:, 1:] & mask[:, :-1]
    vm = mask[1:, :] & mask[:-1, :]

    coords: list[int] = []
    xs, ys = np.nonzero((horizontal > 14) & hm)
    coords.extend((ys[:12000] + 1).tolist())
    xs, ys = np.nonzero((vertical > 14) & vm)
    coords.extend((xs[:12000] + 1).tolist())
    if len(coords) < 6:
        return 1
    divisor = 0
    for value in coords:
        divisor = math.gcd(divisor, int(value))
        if divisor == 1:
            return 1
    if divisor <= 1:
        return 1
    # Very large common divisors usually mean a small icon upscaled a lot.
    while divisor > 8:
        divisor //= 2
    return max(1, divisor)


def _boundary(mask: np.ndarray) -> np.ndarray:
    if not mask.any():
        return mask
    eroded = ndimage.binary_erosion(mask, iterations=1, border_value=0)
    return mask & ~eroded


def _outline_score(rgb: np.ndarray, mask: np.ndarray, profile: dict[str, Any]) -> float | None:
    target = _outline_rgb(profile)
    if target is None:
        return None
    ring = _boundary(mask)
    if not ring.any():
        return 0.0
    pixels = rgb[ring].astype(np.int16)
    target_arr = np.array(target, dtype=np.int16)
    if profile["outline"] == "dark":
        luminance = pixels @ np.array([0.299, 0.587, 0.114])
        hits = luminance < 82
    elif profile["outline"] == "light":
        luminance = pixels @ np.array([0.299, 0.587, 0.114])
        hits = luminance > 176
    else:
        hits = (np.abs(pixels - target_arr).max(axis=1) <= 34)
    return float(hits.mean())


def analyze_image(img: Image.Image, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = normalize_profile(profile)
    rgba = np.array(ensure_rgba(img), dtype=np.uint8)
    rgb = rgba[..., :3]
    mask = rgba[..., 3] > 12
    colors = _unique_colors(rgb, mask)
    coverage = _palette_coverage(rgb, mask, profile["colors"])
    outline = _outline_score(rgb, mask, profile)
    scale = _estimate_pixel_scale(rgb, mask) if mask.any() else 1
    palette: list[str] = []
    if mask.any():
        pixels = rgb[mask].reshape(-1, 3)
        unique, counts = np.unique(pixels, axis=0, return_counts=True)
        order = np.argsort(-counts)[:32]
        palette = [f"#{int(c[0]):02x}{int(c[1]):02x}{int(c[2]):02x}" for c in unique[order]]

    parts: list[tuple[float, float]] = []
    if coverage is not None:
        parts.append((coverage, 45))
    if profile["max_colors"] > 0:
        target = profile["max_colors"]
        parts.append((1.0 if colors <= target else target / max(colors, 1), 20))
    if outline is not None:
        parts.append((outline, 20))
    if profile["pixel_scale"] > 1:
        parts.append((1.0 if scale >= profile["pixel_scale"] else scale / profile["pixel_scale"], 15))

    if parts:
        weight = sum(w for _, w in parts)
        score = sum(v * w for v, w in parts) / weight
    else:
        score = 1.0
    notes: list[str] = []
    if coverage is not None and coverage < 0.9:
        notes.append("Some colours fall outside the project palette.")
    if profile["max_colors"] and colors > profile["max_colors"]:
        notes.append(f"{colors} colours exceeds the {profile['max_colors']}-colour budget.")
    if outline is not None and outline < 0.6:
        notes.append("Outline coverage is below the profile.")
    if profile["pixel_scale"] > 1 and scale < profile["pixel_scale"]:
        notes.append("Pixel blocks are smaller than the profile scale.")

    return {
        "colors": colors,
        "palette_coverage": round(float(coverage), 4) if coverage is not None else None,
        "outline_ratio": round(float(outline), 4) if outline is not None else None,
        "pixel_scale": int(scale),
        "score": round(float(score) * 100, 1),
        "palette": palette,
        "notes": notes,
    }


def _grade(img: Image.Image, profile: dict[str, Any]) -> Image.Image:
    rgb = img.convert("RGB")
    if profile["brightness"] != 100:
        rgb = ImageEnhance.Brightness(rgb).enhance(profile["brightness"] / 100.0)
    if profile["contrast"] != 100:
        rgb = ImageEnhance.Contrast(rgb).enhance(profile["contrast"] / 100.0)
    if profile["saturation"] != 100:
        rgb = ImageEnhance.Color(rgb).enhance(profile["saturation"] / 100.0)
    return rgb


def apply_style(img: Image.Image, profile: dict[str, Any] | None = None) -> tuple[Image.Image, dict[str, Any]]:
    """Apply a style profile. Returns the styled RGBA image and an audit record."""
    profile = normalize_profile(profile)
    original = ensure_rgba(img)
    rgba = np.array(original, dtype=np.uint8).copy()
    before = analyze_image(original, profile)
    applied: list[str] = []

    # 1. Pixel scale: downsample then snap back with nearest-neighbour so blocks
    #    stay aligned to the same canvas size.
    if profile["pixel_scale"] > 1:
        scale = profile["pixel_scale"]
        small_w = max(1, math.ceil(original.width / scale))
        small_h = max(1, math.ceil(original.height / scale))
        small = original.resize((small_w, small_h), Image.Resampling.LANCZOS)
        snapped = small.resize((small_w * scale, small_h * scale), Image.Resampling.NEAREST)
        if snapped.size != original.size:
            snapped = snapped.crop((0, 0, original.width, original.height))
        original = snapped
        rgba = np.array(original, dtype=np.uint8).copy()
        applied.append(f"pixel_scale_{scale}")

    # 2. Colour grading happens before quantization so the palette stays exact.
    if profile["brightness"] != 100 or profile["contrast"] != 100 or profile["saturation"] != 100:
        alpha = rgba[..., 3].copy()
        graded = _grade(Image.fromarray(rgba[..., :3], "RGB"), profile)
        rgba[..., :3] = np.array(graded, dtype=np.uint8)
        rgba[..., 3] = alpha
        applied.append("grading")

    # 3. Shading bands (posterize) before palette mapping.
    if profile["shading_steps"] >= 2:
        bits = max(1, min(8, int(round(math.log2(profile["shading_steps"])))))
        alpha = rgba[..., 3].copy()
        posterized = ImageOps.posterize(Image.fromarray(rgba[..., :3], "RGB"), bits)
        rgba[..., :3] = np.array(posterized, dtype=np.uint8)
        rgba[..., 3] = alpha
        applied.append(f"shading_{profile['shading_steps']}")

    rgb = rgba[..., :3]
    mask = rgba[..., 3] > 12

    # 4. Colour budget when no explicit palette is supplied.
    if not profile["colors"] and profile["max_colors"] > 0 and mask.any():
        alpha = rgba[..., 3].copy()
        quantized = Image.fromarray(rgb, "RGB").quantize(
            colors=max(2, min(256, profile["max_colors"])),
            method=Image.Quantize.MEDIANCUT,
            dither=Image.Dither.NONE,
        ).convert("RGB")
        rgba[..., :3] = np.array(quantized, dtype=np.uint8)
        rgba[..., 3] = alpha
        applied.append(f"colors_{profile['max_colors']}")

    # 5. Explicit palette with optional ordered dithering.
    if profile["colors"] and mask.any():
        palette = np.array([hex_to_rgb(c) for c in profile["colors"]], dtype=np.uint8)
        source = rgb.astype(np.float32)
        if profile["dither"] == "bayer":
            h, w = source.shape[:2]
            tile = np.tile(_BAYER, (h // 8 + 1, w // 8 + 1))[:h, :w]
            source = np.clip(source + tile[..., None] * 24.0, 0, 255)
        index = nearest_palette_map(np.clip(source, 0, 255).astype(np.uint8), palette)
        mapped = palette[index]
        rgba[..., :3] = mapped
        applied.append("palette")
        if profile["dither"] == "bayer":
            applied.append("bayer")

    # 6. Inside outline keeps canvas dimensions stable.
    target = _outline_rgb(profile)
    outline_pixels = 0
    scale_before_outline = _estimate_pixel_scale(rgba[..., :3], rgba[..., 3] > 12) if rgba.shape[0] >= 4 else 1
    if target is not None:
        mask = rgba[..., 3] > 12
        coverage = float(mask.mean()) if mask.size else 0.0
        if coverage > 0.98:
            applied.append("outline_skipped_opaque")
        elif mask.any():
            eroded = ndimage.binary_erosion(mask, iterations=profile["outline_width"], border_value=0)
            ring = mask & ~eroded
            outline_pixels = int(ring.sum())
            rgba[ring, :3] = np.array(target, dtype=np.uint8)
            rgba[ring, 3] = 255
            applied.append("outline")

    result = Image.fromarray(rgba, "RGBA")
    after = analyze_image(result, profile)
    if "outline" in applied:
        after["pixel_scale"] = scale_before_outline
    info = {
        "applied": applied,
        "colors_before": before["colors"],
        "colors_after": after["colors"],
        "pixel_scale_before": before["pixel_scale"],
        "pixel_scale_after": after["pixel_scale"],
        "palette_coverage_before": before["palette_coverage"],
        "palette_coverage_after": after["palette_coverage"],
        "outline_pixels": outline_pixels,
        "score_before": before["score"],
        "score_after": after["score"],
        "profile": profile,
        "width": result.width,
        "height": result.height,
    }
    return result, info


def aggregate_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine per-asset metrics and measure palette overlap between assets."""
    if not rows:
        return {
            "assets": 0,
            "score": None,
            "mean_asset_score": None,
            "palette_coverage": None,
            "average_colors": None,
            "pairwise_palette_overlap": None,
            "consistent": None,
            "recommendations": ["Select assets to build a style report."],
        }
    scores = [r["score"] for r in rows if r.get("score") is not None]
    coverages = [r["palette_coverage"] for r in rows if r.get("palette_coverage") is not None]
    color_counts = [r["colors"] for r in rows]
    palettes = [set(r.get("palette") or []) for r in rows if r.get("palette")]
    overlaps: list[float] = []
    for i in range(len(palettes)):
        for j in range(i + 1, len(palettes)):
            union = palettes[i] | palettes[j]
            if union:
                overlaps.append(len(palettes[i] & palettes[j]) / len(union))

    mean_score = float(np.mean(scores)) if scores else 100.0
    overlap = float(np.mean(overlaps)) if overlaps else None
    consistency = mean_score if overlap is None else mean_score * 0.7 + overlap * 100 * 0.3
    recommendations: list[str] = []
    if coverages and min(coverages) < 0.9:
        recommendations.append("Apply the project palette to assets that fall outside it.")
    if color_counts and (max(color_counts) - min(color_counts)) > 8:
        recommendations.append("Colour budgets vary widely; run Apply style on the noisiest assets.")
    if overlap is not None and overlap < 0.6:
        recommendations.append("Palettes overlap little between assets; unify them with a shared palette.")
    if not recommendations:
        recommendations.append("Style looks consistent. Keep generating with the saved profile.")
    return {
        "assets": len(rows),
        "score": round(float(consistency), 1),
        "mean_asset_score": round(mean_score, 1),
        "palette_coverage": round(float(np.mean(coverages)) * 100, 1) if coverages else None,
        "average_colors": round(float(np.mean(color_counts)), 1) if color_counts else None,
        "pairwise_palette_overlap": round(overlap * 100, 1) if overlap is not None else None,
        "consistent": consistency >= 80,
        "recommendations": recommendations,
    }
