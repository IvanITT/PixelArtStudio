"""False-3D / 2.5D studio.

This module fakes depth from flat art using projection, extrusion, relief
lighting and shadows. It does NOT reconstruct unseen 3D geometry and the UI
says so explicitly.
"""
from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np
from PIL import Image

from .images import clamp_float, clamp_int, ensure_rgba, fit_within

TEMPLATES = {
    "iso_object": {
        "name": "Isometric object",
        "description": "45° floor projection with downward extrusion and contact shadow.",
        "defaults": {"projection": "isometric", "extrude": 0.28, "shadow": True, "relief": 0.25, "floors": 1, "perspective": 0.0},
    },
    "iso_building": {
        "name": "Isometric building",
        "description": "Stacked facade floors with depth and cast shadow.",
        "defaults": {"projection": "isometric", "extrude": 0.45, "shadow": True, "relief": 0.3, "floors": 2, "perspective": 0.0},
    },
    "topdown_rpg": {
        "name": "Top-down RPG prop",
        "description": "Gentle perspective with a short vertical extrusion.",
        "defaults": {"projection": "topdown", "extrude": 0.16, "shadow": True, "relief": 0.2, "floors": 1, "perspective": 0.08},
    },
    "side_platformer": {
        "name": "Side-view platformer prop",
        "description": "Billboard with horizontal depth slices and drop shadow.",
        "defaults": {"projection": "side", "extrude": 0.2, "shadow": True, "relief": 0.18, "floors": 1, "perspective": 0.0},
    },
    "iso_environment": {
        "name": "Fake 3D environment",
        "description": "Isometric strip with a procedural ground check and stacked relief.",
        "defaults": {"projection": "isometric", "extrude": 0.3, "shadow": True, "relief": 0.35, "floors": 1, "perspective": 0.0, "backdrop": "grid"},
    },
}


def _rotate_iso(img: Image.Image, angle: float, scale: float) -> Image.Image:
    rgba = ensure_rgba(img)
    rotated = rgba.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    w, h = rotated.size
    new_h = max(1, int(h * 0.5))
    return rotated.resize((max(1, int(w * scale)), max(1, int(new_h * scale))), Image.Resampling.LANCZOS)


def project(img: Image.Image, projection: str, angle: float, scale: float) -> Image.Image:
    rgba = ensure_rgba(img)
    if projection == "isometric":
        return _rotate_iso(rgba, angle if angle else 45.0, scale)
    if projection == "orthographic":
        arr = np.asarray(rgba)
        h, w = arr.shape[:2]
        shear = np.tan(np.radians(max(-60, min(60, angle)))) * 0.35
        new_w = int(w + abs(shear) * h) + 2
        M = np.array([[1, shear, (new_w - w) / 2 if shear < 0 else 0], [0, 1, 0]], dtype=np.float32)
        warped = cv2.warpAffine(arr, M, (new_w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
        out = Image.fromarray(warped, "RGBA")
        if scale != 1.0:
            out = out.resize((max(1, int(out.width * scale)), max(1, int(out.height * scale))), Image.Resampling.LANCZOS)
        return out
    if projection == "topdown":
        if scale == 1.0:
            return rgba
        return rgba.resize((max(1, int(rgba.width * scale)), max(1, int(rgba.height * scale))), Image.Resampling.LANCZOS)
    return rgba if scale == 1.0 else rgba.resize((max(1, int(rgba.width * scale)), max(1, int(rgba.height * scale))), Image.Resampling.LANCZOS)


def extrude(img: Image.Image, depth_ratio: float, direction: str = "down", shade: float = 0.55) -> Image.Image:
    rgba = ensure_rgba(img)
    w, h = rgba.size
    depth = int(max(1, round(max(w, h) * np.clip(depth_ratio, 0.02, 1.0))))
    vec = {
        "down": (0, 1), "up": (0, -1), "left": (-1, 0), "right": (1, 0),
        "down-right": (1, 1), "down-left": (-1, 1), "up-right": (1, -1), "up-left": (-1, -1),
    }.get(direction, (0, 1))
    pad_x = abs(vec[0]) * depth
    pad_y = abs(vec[1]) * depth
    ox = pad_x if vec[0] < 0 else 0
    oy = pad_y if vec[1] < 0 else 0
    canvas_w = w + pad_x
    canvas_h = h + pad_y
    base = np.asarray(rgba, dtype=np.float32)
    alpha = base[..., 3:4] / 255.0
    out = np.zeros((canvas_h, canvas_w, 4), dtype=np.float32)
    # Draw far slices first; darken with distance.
    for i in range(depth, 0, -1):
        sx = ox + vec[0] * i
        sy = oy + vec[1] * i
        if sx < 0 or sy < 0 or sx + w > canvas_w or sy + h > canvas_h:
            continue
        t = i / depth
        color = base[..., :3] * (1 - shade * (0.35 + 0.65 * t))
        region = out[sy:sy + h, sx:sx + w]
        src_alpha = alpha * (0.92 - 0.25 * t)
        region[..., :3] = region[..., :3] * (1 - src_alpha) + color * src_alpha
        region[..., 3:4] = np.maximum(region[..., 3:4], src_alpha * 255)
    # Front layer.
    fx, fy = ox, oy
    front_a = alpha
    region = out[fy:fy + h, fx:fx + w]
    region[..., :3] = region[..., :3] * (1 - front_a) + base[..., :3] * front_a
    region[..., 3:4] = np.maximum(region[..., 3:4], base[..., 3:4])
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def add_shadow(img: Image.Image, dx: int = 6, dy: int = 8, blur: int = 5, opacity: float = 0.45) -> Image.Image:
    rgba = ensure_rgba(img)
    alpha = np.asarray(rgba.getchannel("A"), dtype=np.uint8)
    h, w = alpha.shape
    pad = max(abs(dx), abs(dy)) + blur * 3 + 4
    canvas = np.zeros((h + pad * 2, w + pad * 2), dtype=np.uint8)
    canvas[pad:pad + h, pad:pad + w] = alpha
    shift = np.zeros_like(canvas)
    sx, sy = pad + dx, pad + dy
    shift[sy:sy + h, sx:sx + w] = alpha
    shadow = cv2.GaussianBlur(shift, (0, 0), max(1, blur))
    shadow = (shadow.astype(np.float32) * np.clip(opacity, 0, 1)).astype(np.uint8)
    out = np.zeros((canvas.shape[0], canvas.shape[1], 4), dtype=np.uint8)
    out[..., :3] = 8
    out[..., 3] = shadow
    layer = Image.fromarray(out, "RGBA")
    result = Image.new("RGBA", (canvas.shape[1], canvas.shape[0]), (0, 0, 0, 0))
    result.alpha_composite(layer)
    result.alpha_composite(rgba, (pad, pad))
    return result


def relief_light(img: Image.Image, strength: float = 0.35, light_angle: float = 315.0, height_blur: float = 2.0) -> Image.Image:
    rgba = ensure_rgba(img)
    arr = np.asarray(rgba, dtype=np.uint8)
    rgb = arr[..., :3].astype(np.float32)
    alpha = arr[..., 3:4].astype(np.float32) / 255.0
    lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    lum = cv2.GaussianBlur(lum, (0, 0), max(0.5, height_blur))
    dx = cv2.Sobel(lum, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    dy = cv2.Sobel(lum, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    ang = np.radians(light_angle)
    lx, ly = np.cos(ang), -np.sin(ang)
    light = (dx * lx + dy * ly) * (strength * 2.0)
    light = np.clip(1.0 + light, 0.45, 1.55)
    shaded = np.clip(rgb * light[..., None], 0, 255)
    # Rim light on the side facing the light.
    rim = np.clip(light - 1.0, 0, 1) * 90
    shaded = np.clip(shaded + rim[..., None] * alpha, 0, 255)
    out = np.dstack([shaded, arr[..., 3]]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def fake_perspective(img: Image.Image, amount: float = 0.12) -> Image.Image:
    rgba = ensure_rgba(img)
    w, h = rgba.size
    if abs(amount) < 1e-3 or h < 4:
        return rgba
    pad = int(w * abs(amount) * 0.6) + 2
    arr = np.asarray(rgba)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    top_inset = pad
    bottom_inset = max(0, int(w * 0.02))
    dst = np.float32([
        [top_inset, 0], [w - top_inset, 0],
        [w - bottom_inset, h], [bottom_inset, h],
    ])
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(arr, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    return Image.fromarray(warped, "RGBA")


def add_ground_grid(img: Image.Image, spacing: int = 16, color: str = "#2a2f3a") -> Image.Image:
    rgba = ensure_rgba(img)
    floor = Image.new("RGBA", (rgba.width + 40, rgba.height + 60), (0, 0, 0, 0))
    overlay = Image.new("RGBA", floor.size, (0, 0, 0, 0))
    from PIL import ImageDraw

    d = ImageDraw.Draw(overlay)
    c = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) + (70,)
    cx, cy = floor.width // 2, floor.height - 24
    for i in range(-8, 9):
        d.line([(cx + i * spacing, cy - 2), (cx + i * spacing + rgba.width, cy - 2 + rgba.height // 3)], fill=c)
    floor.alpha_composite(overlay)
    floor.alpha_composite(rgba, (20, 10))
    return floor


def studio(img: Image.Image, options: dict[str, Any] | None = None) -> tuple[Image.Image, dict[str, Any]]:
    t0 = time.perf_counter()
    o = options or {}
    template = str(o.get("template", "iso_object"))
    preset = TEMPLATES.get(template, TEMPLATES["iso_object"])["defaults"]
    merged = {**preset, **{k: v for k, v in o.items() if v is not None}}
    max_dim = 768
    src = fit_within(ensure_rgba(img), 640)
    projection = str(merged.get("projection", "isometric"))
    angle = clamp_float(merged.get("angle"), -180, 180, 45.0)
    scale = clamp_float(merged.get("scale"), 0.2, 2.0, 1.0)
    projected = project(src, projection, angle, scale)
    floors = clamp_int(merged.get("floors"), 1, 4, 1)
    if floors > 1 and projection == "isometric":
        tile_w = projected.width
        tile_h = max(1, int(projected.height * 0.72))
        stack = Image.new("RGBA", (tile_w, tile_h * floors + projected.height), (0, 0, 0, 0))
        for i in range(floors):
            layer = projected.copy()
            shade = 1.0 - i * 0.06
            arr = np.asarray(layer, dtype=np.float32)
            arr[..., :3] *= shade
            layer = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
            stack.alpha_composite(layer, (0, (floors - 1 - i) * tile_h))
        projected = stack
    depth = clamp_float(merged.get("extrude"), 0.02, 1.0, 0.28)
    direction = str(merged.get("extrude_direction", "down"))
    extruded = extrude(projected, depth, direction, 0.5)
    perspective = clamp_float(merged.get("perspective"), -1.0, 1.0, 0.0)
    if abs(perspective) > 0.01:
        extruded = fake_perspective(extruded, perspective)
    relief = clamp_float(merged.get("relief"), 0, 1.5, 0.25)
    if relief > 0.01:
        extruded = relief_light(extruded, relief, clamp_float(merged.get("light_angle"), 0, 360, 315), 2.0)
    if merged.get("shadow", True):
        extruded = add_shadow(
            extruded,
            clamp_int(merged.get("shadow_dx"), -40, 40, 6),
            clamp_int(merged.get("shadow_dy"), -40, 40, 8),
            clamp_int(merged.get("shadow_blur"), 1, 20, 5),
            clamp_float(merged.get("shadow_opacity"), 0, 1, 0.45),
        )
    backdrop = str(merged.get("backdrop", "none"))
    if backdrop == "grid":
        extruded = add_ground_grid(extruded)
    if max(extruded.size) > max_dim:
        extruded.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    info = {
        "template": template,
        "projection": projection,
        "angle": angle,
        "scale": scale,
        "floors": floors,
        "extrude": depth,
        "extrude_direction": direction,
        "perspective": perspective,
        "relief": relief,
        "shadow": bool(merged.get("shadow", True)),
        "backdrop": backdrop,
        "width": extruded.width,
        "height": extruded.height,
        "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
        "disclaimer": "Depth is simulated from the 2D image. Unseen geometry is not reconstructed.",
    }
    return extruded, info


def heightmap(img: Image.Image, blur: float = 2.0, invert: bool = False) -> Image.Image:
    rgba = ensure_rgba(img)
    arr = np.asarray(rgba, dtype=np.float32)
    lum = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    lum = cv2.GaussianBlur(lum, (0, 0), max(0.5, blur))
    if invert:
        lum = 255 - lum
    lum = np.clip(lum, 0, 255).astype(np.uint8)
    alpha = np.asarray(rgba.getchannel("A"), dtype=np.uint8)
    out = np.dstack([lum, lum, lum, alpha])
    return Image.fromarray(out, "RGBA")
