"""Frame-based animation: template transforms, playback data and exports."""
from __future__ import annotations

import io
import math
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance

from .images import ensure_rgba, fit_within
from .sprites import pack_spritesheet

TEMPLATES = {
    "idle": {"name": "Idle", "frames": 6, "fps": 6, "description": "Soft vertical breathing loop."},
    "walk": {"name": "Walk", "frames": 8, "fps": 10, "description": "Alternating lean and bob."},
    "run": {"name": "Run", "frames": 8, "fps": 14, "description": "Faster, stronger lean and bob."},
    "jump": {"name": "Jump", "frames": 6, "fps": 12, "description": "Crouch, launch, apex, land."},
    "fall": {"name": "Fall", "frames": 4, "fps": 8, "description": "Downward drift with stretch."},
    "attack": {"name": "Attack", "frames": 6, "fps": 14, "description": "Wind-up, lunge and recovery."},
    "hurt": {"name": "Hurt", "frames": 4, "fps": 10, "description": "Impact shake with tint."},
    "death": {"name": "Death", "frames": 8, "fps": 8, "description": "Collapse, rotate and fade."},
}


def _transform(
    img: Image.Image,
    sx: float = 1.0,
    sy: float = 1.0,
    angle: float = 0.0,
    dx: int = 0,
    dy: int = 0,
    brightness: float = 1.0,
    tint: tuple[float, float, float] | None = None,
    opacity: float = 1.0,
) -> Image.Image:
    rgba = ensure_rgba(img)
    w, h = rgba.size
    scaled = rgba.resize((max(1, int(w * sx)), max(1, int(h * sy))), Image.Resampling.BICUBIC)
    if abs(angle) > 0.01:
        scaled = scaled.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    pad = int(max(scaled.size) * 0.5) + 8
    canvas = Image.new("RGBA", (scaled.width + pad * 2, scaled.height + pad * 2), (0, 0, 0, 0))
    canvas.alpha_composite(scaled, (pad, pad))
    if tint or brightness != 1.0 or opacity != 1.0:
        arr = np.asarray(canvas, dtype=np.float32)
        arr[..., :3] *= brightness
        if tint:
            arr[..., 0] *= tint[0]
            arr[..., 1] *= tint[1]
            arr[..., 2] *= tint[2]
        arr[..., 3] *= max(0.0, min(1.0, opacity))
        canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    # Convert dx/dy to final canvas shift.
    shifted = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shifted.alpha_composite(canvas, (int(dx), int(dy)))
    return shifted


def _normalize(frames: list[Image.Image], align_bottom: bool = True) -> list[Image.Image]:
    if not frames:
        return []
    max_w = max(f.width for f in frames)
    max_h = max(f.height for f in frames)
    out = []
    for f in frames:
        canvas = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
        x = (max_w - f.width) // 2
        y = max_h - f.height if align_bottom else (max_h - f.height) // 2
        canvas.alpha_composite(ensure_rgba(f), (x, y))
        out.append(canvas)
    return out


def template_frames(img: Image.Image, template: str, frames: int | None = None) -> list[Image.Image]:
    if template not in TEMPLATES:
        raise ValueError(f"Unknown animation template: {template}")
    n = max(2, min(int(frames or TEMPLATES[template]["frames"]), 24))
    out: list[Image.Image] = []
    for i in range(n):
        t = i / n
        phase = 2 * math.pi * t
        if template == "idle":
            bob = round(math.sin(phase) * 1.5)
            out.append(_transform(img, 1.0, 1.0 + 0.02 * math.sin(phase), 0, 0, bob))
        elif template == "walk":
            bob = round(abs(math.sin(phase)) * -2)
            lean = math.sin(phase) * 4.5
            out.append(_transform(img, 1.0, 1.0, lean, 0, bob))
        elif template == "run":
            bob = round(abs(math.sin(phase)) * -4)
            lean = math.sin(phase) * 8
            out.append(_transform(img, 1.0 + 0.02 * math.cos(phase), 1.0, lean, round(math.sin(phase) * 2), bob))
        elif template == "jump":
            prog = [0.35, 0.15, 0.0, -0.3, -0.15, 0.25][i % 6]
            sx = 1.0 + (0.12 if prog > 0.2 else (-0.06 if prog < -0.1 else 0.0))
            out.append(_transform(img, sx, 1 / sx, 0, 0, round(prog * 10)))
        elif template == "fall":
            out.append(_transform(img, 0.96, 1.06, math.sin(phase) * 3, 0, round(t * 6)))
        elif template == "attack":
            prog = [0, -3, -5, 8, 5, 1][i % 6]
            out.append(_transform(img, 1.0, 1.0, prog * 0.6, prog * 1.5, 0, brightness=1.18 if i == 3 else 1.0))
        elif template == "hurt":
            shake = [0, -4, 4, -2][i % 4]
            out.append(_transform(img, 1.0, 1.0, shake, shake, 0, tint=(1.3, 0.8, 0.8)))
        elif template == "death":
            prog = i / (n - 1)
            out.append(_transform(img, 1.0 - 0.1 * prog, 1.0 - 0.2 * prog, 90 * prog, round(prog * 4), round(prog * 10), opacity=1.0 - 0.75 * prog))
        else:
            out.append(img.copy())
    return _normalize(out)


def resize_frames(frames: list[Image.Image], width: int, height: int, anchor: str = "bottom") -> list[Image.Image]:
    out = []
    for f in frames:
        fw, fh = f.size
        scale = min(width / fw, height / fh, 999)
        scaled = f.resize((max(1, int(fw * scale)), max(1, int(fh * scale))), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        x = (width - scaled.width) // 2
        y = height - scaled.height if anchor == "bottom" else (height - scaled.height) // 2
        canvas.alpha_composite(scaled, (x, y))
        out.append(canvas)
    return out


def crop_frames(frames: list[Image.Image], box: tuple[int, int, int, int]) -> list[Image.Image]:
    return [f.crop(box) for f in frames]


def pack_frames(
    frames: list[Image.Image],
    names: list[str] | None = None,
    columns: int = 0,
    cell_width: int = 0,
    cell_height: int = 0,
    padding: int = 0,
    spacing: int = 0,
) -> tuple[Image.Image, dict[str, Any]]:
    return pack_spritesheet(
        frames,
        names=names,
        options={
            "columns": columns,
            "cell_width": cell_width,
            "cell_height": cell_height,
            "padding": padding,
            "spacing": spacing,
            "max_dim": 8192,
        },
    )


def export_gif(frames: list[Image.Image], fps: int = 10, loop: bool = True) -> bytes:
    if not frames:
        raise ValueError("No frames")
    duration = max(20, int(1000 / max(1, fps)))
    prepared = []
    for f in frames:
        rgba = ensure_rgba(f)
        # Flatten onto a transparent GIF-friendly palette.
        p = rgba.convert("P", palette=Image.Palette.ADAPTIVE, colors=255)
        alpha = rgba.getchannel("A")
        mask = alpha.point(lambda v: 255 if v < 128 else 0)
        p.paste(255, mask=mask)
        p.info["transparency"] = 255
        prepared.append(p)
    buf = io.BytesIO()
    prepared[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=prepared[1:],
        duration=duration,
        loop=0 if loop else 1,
        disposal=2,
        transparency=255,
        optimize=False,
    )
    return buf.getvalue()


def export_webp(frames: list[Image.Image], fps: int = 10, loop: bool = True) -> bytes:
    if not frames:
        raise ValueError("No frames")
    duration = max(20, int(1000 / max(1, fps)))
    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0 if loop else 1,
        lossless=True,
        quality=90,
        method=4,
    )
    return buf.getvalue()


def frame_metadata(frames: list[Image.Image], names: list[str], fps: int, loop: bool) -> dict[str, Any]:
    duration = max(20, int(1000 / max(1, fps)))
    return {
        "app": "Pixel Art & Game Asset Studio",
        "format": "pas-animation",
        "fps": fps,
        "loop": loop,
        "frame_count": len(frames),
        "frames": [
            {
                "name": names[i] if i < len(names) else f"frame_{i:03d}",
                "index": i,
                "duration_ms": duration,
                "width": f.width,
                "height": f.height,
            }
            for i, f in enumerate(frames)
        ],
    }
