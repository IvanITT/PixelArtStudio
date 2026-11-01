from __future__ import annotations

import hashlib
import io
import math
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFile, ImageOps

from ..config import ALLOWED_FORMATS, IMAGE_EXT
from ..db import get_settings

ImageFile.LOAD_TRUNCATED_IMAGES = False


class ImageValidationError(ValueError):
    pass


def _limits() -> tuple[int, int]:
    s = get_settings()
    return int(s["max_upload_mb"]) * 1024 * 1024, int(s["max_image_pixels"])


def decode_image(data: bytes, *, enforce_limits: bool = True) -> Image.Image:
    """Safely decode an uploaded image, validating format and dimensions."""
    max_bytes, max_pixels = _limits()
    if not data:
        raise ImageValidationError("Empty file")
    if enforce_limits and len(data) > max_bytes:
        raise ImageValidationError(
            f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit"
        )
    try:
        probe = Image.open(io.BytesIO(data))
        fmt = (probe.format or "").upper()
        if fmt not in ALLOWED_FORMATS:
            raise ImageValidationError(f"Unsupported image format: {fmt or 'unknown'}")
        w, h = probe.size
        if w < 1 or h < 1:
            raise ImageValidationError("Invalid image dimensions")
        if enforce_limits and w * h > max_pixels:
            raise ImageValidationError(
                f"Image is too large ({w}x{h}); the configured pixel limit is {max_pixels:,}"
            )
        probe.load()
        img = ImageOps.exif_transpose(probe)
        img.load()
    except ImageValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ImageValidationError(f"Could not decode image: {exc}") from exc
    return normalize_mode(img)


def normalize_mode(img: Image.Image) -> Image.Image:
    if img.mode in {"RGBA", "LA"}:
        return img.convert("RGBA")
    if img.mode == "P" and "transparency" in img.info:
        return img.convert("RGBA")
    return img.convert("RGB")


def open_image(path: str) -> Image.Image:
    with open(path, "rb") as fh:
        data = fh.read()
    img = Image.open(io.BytesIO(data))
    img.load()
    return normalize_mode(img)


def image_to_bytes(img: Image.Image, fmt: str = "PNG", **kwargs: Any) -> bytes:
    fmt = fmt.upper()
    if fmt == "JPG":
        fmt = "JPEG"
    buf = io.BytesIO()
    if fmt in {"JPEG", "BMP"} and img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (0, 0, 0))
        bg.paste(img, mask=img.getchannel("A"))
        img = bg
    if fmt == "GIF":
        rgba = ensure_rgba(img)
        pal = rgba.convert("P", palette=Image.Palette.ADAPTIVE, colors=255)
        alpha = rgba.getchannel("A")
        mask = alpha.point(lambda v: 255 if v < 128 else 0)
        pal.paste(255, mask=mask)
        pal.info["transparency"] = 255
        pal.save(buf, format="GIF", transparency=255, **kwargs)
        return buf.getvalue()
    if fmt == "PNG":
        kwargs.setdefault("compress_level", 6)
    if fmt == "WEBP":
        kwargs.setdefault("quality", 92)
        kwargs.setdefault("method", 4)
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


def thumb(img: Image.Image, size: int = 320) -> Image.Image:
    copy = img.copy()
    copy.thumbnail((size, size), Image.Resampling.LANCZOS)
    if copy.mode == "RGBA":
        canvas = Image.new("RGBA", copy.size, (0, 0, 0, 0))
        canvas.alpha_composite(copy)
        return canvas
    return copy


def fit_within(img: Image.Image, max_dim: int) -> Image.Image:
    if max(img.size) <= max_dim:
        return img
    return _contain(img, max_dim)


def _contain(img: Image.Image, max_dim: int) -> Image.Image:
    w, h = img.size
    scale = max_dim / max(w, h)
    return img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)


RESAMPLE = {
    "nearest": Image.Resampling.NEAREST,
    "bilinear": Image.Resampling.BILINEAR,
    "bicubic": Image.Resampling.BICUBIC,
    "lanczos": Image.Resampling.LANCZOS,
}


def resize(img: Image.Image, width: int, height: int, method: str = "lanczos") -> Image.Image:
    return img.resize((max(1, int(width)), max(1, int(height))), RESAMPLE.get(method.lower(), Image.Resampling.LANCZOS))


def to_numpy(img: Image.Image) -> np.ndarray:
    return np.asarray(img, dtype=np.uint8)


def from_numpy(arr: np.ndarray) -> Image.Image:
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    if arr.ndim == 3 and arr.shape[2] == 4:
        return Image.fromarray(arr, "RGBA")
    return Image.fromarray(arr, "RGB")


def rgba_to_rgb_on_alpha(img: Image.Image) -> tuple[Image.Image, Image.Image]:
    img = img.convert("RGBA")
    alpha = img.getchannel("A")
    rgb = Image.new("RGB", img.size, (0, 0, 0))
    rgb.paste(img, mask=alpha)
    return rgb, alpha


def alpha_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    img = img.convert("RGBA")
    return img.getchannel("A").getbbox()


def trim_transparent(img: Image.Image, padding: int = 0) -> Image.Image:
    bbox = alpha_bbox(img)
    if not bbox:
        return img
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - padding)
    y0 = max(0, y0 - padding)
    x1 = min(img.width, x1 + padding)
    y1 = min(img.height, y1 + padding)
    return img.crop((x0, y0, x1, y1))


def make_thumbnail_file(img: Image.Image, path: str, size: int = 320) -> None:
    t = thumb(img, size)
    t.save(path, format="PNG", compress_level=6)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_image(img: Image.Image) -> str:
    return hashlib.sha256(img.tobytes()).hexdigest()


def average_hash(img: Image.Image, size: int = 8) -> str:
    gray = img.convert("L").resize((size, size), Image.Resampling.BILINEAR)
    arr = np.asarray(gray, dtype=np.float32)
    bits = (arr > arr.mean()).flatten()
    return "".join("1" if b else "0" for b in bits)


def hamming(a: str, b: str) -> int:
    return sum(1 for x, y in zip(a, b) if x != y)


def ensure_rgba(img: Image.Image) -> Image.Image:
    return img if img.mode == "RGBA" else img.convert("RGBA")


def checkerboard(width: int, height: int, cell: int = 8) -> Image.Image:
    canvas = Image.new("RGBA", (width, height), (34, 38, 48, 255))
    draw = ImageDraw.Draw(canvas)
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            if (x // cell + y // cell) % 2 == 0:
                draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(48, 53, 66, 255))
    return canvas


def compose_alpha(rgb: Image.Image, alpha: Image.Image) -> Image.Image:
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def clean_tmp(path: str) -> None:
    import os

    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def parse_ext(filename: str) -> str:
    lower = filename.lower().rsplit(".", 1)
    if len(lower) != 2:
        raise ImageValidationError("File has no extension")
    ext = "." + lower[1]
    if ext not in IMAGE_EXT:
        raise ImageValidationError(f"Unsupported extension {ext}")
    return ext


def clamp_int(v: Any, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except Exception:
        return default


def clamp_float(v: Any, lo: float, hi: float, default: float) -> float:
    try:
        f = float(v)
        if math.isnan(f):
            return default
        return max(lo, min(hi, f))
    except Exception:
        return default
