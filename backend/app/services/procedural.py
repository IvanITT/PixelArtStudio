"""Deterministic procedural 2D game-asset generators.

No neural networks are involved: every asset is drawn from seeded randomness,
mathematical ramps, layered shapes and rule-based composition. The same
generator + parameters + seed always yields the same pixels.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Callable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .images import clamp_float, clamp_int, ensure_rgba
from .palettes import palette_by_id

RAMPS: dict[str, list[str]] = {
    "leaf": ["#15281a", "#1f3d24", "#2f5c33", "#4a8145", "#74ad5c", "#a3d17a"],
    "wood": ["#2a180f", "#452717", "#623a20", "#84532d", "#a97442", "#cf9a63"],
    "bark": ["#24150e", "#3d2416", "#56341d", "#714727", "#8d5c36", "#ab7748"],
    "stone": ["#23262b", "#363a41", "#4b515a", "#646c77", "#828b98", "#a6b0bd"],
    "metal": ["#1e2329", "#303842", "#46515e", "#5f6d7c", "#7c8c9d", "#a5b5c5"],
    "gold": ["#3a2508", "#6b440d", "#9a6a17", "#c9972a", "#eac451", "#fff0a0"],
    "water": ["#08243d", "#0c3b61", "#12588b", "#1f7cb3", "#42a9d6", "#8fd9f0"],
    "fire": ["#3d0d06", "#7a1e0a", "#b53c0e", "#e8731a", "#ffa63d", "#ffe08a"],
    "magic": ["#1b0f33", "#33205c", "#51348c", "#7a4fc4", "#ac7ef0", "#e2c9ff"],
    "skin": ["#3d2418", "#6b4229", "#95603a", "#bd8355", "#dba97a", "#f2ceaa"],
    "sand": ["#4a3a21", "#6e5630", "#947443", "#b89457", "#d8b877", "#f0dba8"],
    "snow": ["#6d7d92", "#8fa2b8", "#b4c6d8", "#d7e5f0", "#f2f8fd", "#ffffff"],
    "ice": ["#173a52", "#245a78", "#357fa3", "#57a8c9", "#8fd5e8", "#d4f5ff"],
    "neon_pink": ["#2b0716", "#5c0f2c", "#941a4a", "#d42b70", "#ff5c9e", "#ffb3d1"],
    "neon_blue": ["#061426", "#0a2a4d", "#0f4a80", "#1778c4", "#36b3f0", "#a6ecff"],
    "cloth": ["#2a1a2e", "#452a49", "#643e68", "#87588a", "#ac7cab", "#d3afd0"],
    "poison": ["#142a10", "#23501c", "#377a27", "#55a63a", "#84d45c", "#c3f59a"],
}

THEMES = {
    "classic": {"sat": 1.0, "bright": 1.0, "hue": 0.0},
    "pastel": {"sat": 0.62, "bright": 1.22, "hue": 0.0},
    "neon": {"sat": 1.45, "bright": 1.08, "hue": 0.0},
    "mono": {"sat": 0.0, "bright": 1.0, "hue": 0.0},
}


def _hex_rgb(c: str) -> tuple[int, int, int]:
    v = c.lstrip("#")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def _to_hex(rgb: np.ndarray | tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*[max(0, min(255, int(v))) for v in rgb])


def style_ramp(ramp: list[str], theme: str) -> list[str]:
    cfg = THEMES.get(theme, THEMES["classic"])
    arr = np.array([_hex_rgb(c) for c in ramp], dtype=np.uint8).reshape(1, -1, 3)
    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[..., 0] = (hsv[..., 0] + cfg["hue"] / 2) % 180
    hsv[..., 1] = np.clip(hsv[..., 1] * cfg["sat"], 0, 255)
    hsv[..., 2] = np.clip(hsv[..., 2] * cfg["bright"], 0, 255)
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    return [_to_hex(c) for c in out.reshape(-1, 3)]


class Art:
    """Small drawing surface with ramps, shading and dithering helpers."""

    def __init__(self, size: int, seed: int, theme: str = "classic", outline: bool = True):
        self.w = self.h = size
        self.rng = random.Random(seed)
        self.theme = theme
        self.outline = outline
        self.img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.used: set[str] = set()

    def ramp(self, name: str) -> list[str]:
        return style_ramp(RAMPS.get(name, RAMPS["stone"]), self.theme)

    def c(self, name: str, idx: int) -> str:
        r = self.ramp(name)
        c = r[max(0, min(len(r) - 1, idx))]
        self.used.add(c)
        return c

    def box(self, x0: float, y0: float, x1: float, y1: float, color: str) -> None:
        self.d.rectangle([min(int(x0), int(x1)), min(int(y0), int(y1)),
                          max(int(x0), int(x1)), max(int(y0), int(y1))], fill=color)
        self.used.add(color)

    def ellipse(self, x0: float, y0: float, x1: float, y1: float, color: str) -> None:
        self.d.ellipse([min(int(x0), int(x1)), min(int(y0), int(y1)),
                        max(int(x0), int(x1)), max(int(y0), int(y1))], fill=color)
        self.used.add(color)

    def poly(self, pts: list[tuple[float, float]], color: str) -> None:
        self.d.polygon([(int(x), int(y)) for x, y in pts], fill=color)
        self.used.add(color)

    def line(self, pts: list[tuple[float, float]], color: str, width: int = 1) -> None:
        self.d.line([(int(x), int(y)) for x, y in pts], fill=color, width=max(1, width))
        self.used.add(color)

    def dot(self, x: int, y: int, color: str) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.img.putpixel((int(x), int(y)), _hex_rgb(color) + (255,))
            self.used.add(color)

    def dither(self, x0: int, y0: int, x1: int, y1: int, c1: str, c2: str, density: float = 0.5) -> None:
        for y in range(int(y0), int(y1)):
            for x in range(int(x0), int(x1)):
                if 0 <= x < self.w and 0 <= y < self.h and ((x + y) % 2 == 0) and self.rng.random() < density:
                    self.dot(x, y, c1 if ((x // 2 + y // 2) % 2 == 0) else c2)

    def speckle(self, x0: int, y0: int, x1: int, y1: int, colors: list[str], count: int) -> None:
        for _ in range(count):
            self.dot(self.rng.randint(int(x0), int(x1) - 1), self.rng.randint(int(y0), int(y1) - 1), self.rng.choice(colors))

    def brick_pattern(self, x0: int, y0: int, x1: int, y1: int, base: list[str], mortar: str, bh: int = 4, bw: int = 8) -> None:
        self.box(x0, y0, x1, y1, base[2])
        row = 0
        y = y0
        while y < y1:
            off = (row % 2) * bw // 2
            x = x0 - off
            while x < x1:
                self.box(max(x0, x), y, min(x1, x + bw - 1), min(y1, y + bh - 1), self.rng.choice(base[1:4]))
                x += bw
            y += bh
            row += 1
        for y in range(y0, y1, bh):
            self.line([(x0, y), (x1 - 1, y)], mortar)
        for i, y in enumerate(range(y0, y1, bh)):
            off = (i % 2) * bw // 2
            for x in range(x0 + off, x1, bw):
                self.line([(x, y), (x, min(y1 - 1, y + bh - 1))], mortar)

    def plank_pattern(self, x0: int, y0: int, x1: int, y1: int, base: list[str], ph: int = 4) -> None:
        for y in range(y0, y1, ph):
            self.box(x0, y, x1 - 1, min(y1 - 1, y + ph - 1), self.rng.choice(base[1:5]))
            self.line([(x0, y), (x1 - 1, y)], base[0])
            if self.rng.random() < 0.6:
                gx = self.rng.randint(x0 + 2, max(x0 + 3, x1 - 2))
                self.line([(gx, y + 1), (gx, min(y1 - 1, y + ph - 2))], base[2] if self.rng.random() < 0.5 else base[0])

    def outline_silhouette(self, color: str = "#111319", width: int = 1) -> None:
        arr = np.array(self.img, dtype=np.uint8, copy=True)
        alpha = (arr[..., 3] > 24).astype(np.uint8)
        kernel = np.ones((width * 2 + 1, width * 2 + 1), np.uint8)
        grown = cv2.dilate(alpha, kernel, iterations=1)
        border = (grown > 0) & (alpha == 0)
        if border.any():
            arr[border] = (*_hex_rgb(color), 235)
        self.img = Image.fromarray(arr, "RGBA")
        self.d = ImageDraw.Draw(self.img)

    def glow(self, color: str, radius: int = 3, strength: float = 0.8) -> None:
        alpha = self.img.getchannel("A")
        glow_alpha = alpha.filter(ImageFilter.GaussianBlur(radius))
        glow_alpha = glow_alpha.point(lambda v: int(v * strength))
        layer = Image.new("RGBA", self.img.size, _hex_rgb(color) + (0,))
        layer.putalpha(glow_alpha)
        base = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        base.alpha_composite(layer)
        base.alpha_composite(self.img)
        self.img = base
        self.d = ImageDraw.Draw(self.img)

    def finish(self) -> Image.Image:
        if self.outline:
            self.outline_silhouette()
        return self.img


# ---------------------------------------------------------------- nature

def gen_tree(a: Art, p: dict[str, Any]) -> None:
    r = a.ramp("leaf")
    bark = a.ramp("bark")
    height = clamp_float(p.get("height"), 0.4, 0.95, 0.8)
    thick = max(2, int(a.w * clamp_float(p.get("trunk_width"), 0.05, 0.24, 0.1)))
    cx = a.w // 2
    ground = a.h - 2
    th = int(a.h * height)
    shape = str(p.get("canopy", "round"))
    trunk_top = ground - int(th * 0.55)
    # Tapered trunk with a slight bend.
    bend = a.rng.randint(-max(1, a.w // 20), max(1, a.w // 20))
    a.poly([
        (cx - thick // 2, ground), (cx + thick // 2, ground),
        (cx + thick // 2 + bend, trunk_top), (cx - thick // 2 + bend + 1, trunk_top),
    ], bark[2])
    a.line([(cx - thick // 2 + 1, ground - 1), (cx - thick // 2 + bend + 1, trunk_top)], bark[1])
    a.line([(cx + thick // 2 - 1, ground - 2), (cx + thick // 2 + bend, trunk_top + 2)], bark[4])
    for _ in range(clamp_int(p.get("bark_lines"), 0, 12, 3)):
        yy = a.rng.randint(trunk_top + 2, ground - 2)
        a.dot(cx + a.rng.randint(-thick // 2, thick // 2), yy, bark[1])

    top = ground - th
    canopy_w = int(a.w * clamp_float(p.get("width"), 0.4, 1.0, 0.72))
    left = cx - canopy_w // 2
    right = cx + canopy_w // 2
    if shape == "pine":
        layers = clamp_int(p.get("branches"), 2, 6, 3)
        for i in range(layers):
            yy0 = top + int((th * 0.55) * i / layers)
            yy1 = top + int((th * 0.65) * (i + 1) / layers)
            spread = int(canopy_w * (0.35 + 0.65 * i / max(1, layers - 1))) // 2
            a.poly([(cx, yy0), (cx - spread, yy1), (cx + spread, yy1)], r[min(len(r) - 1, 2 + i % 3)])
            a.poly([(cx, yy0 + 1), (cx - spread + 2, yy1), (cx, yy1)], r[min(len(r) - 1, 3 + i % 2)])
    elif shape == "palm":
        a.ellipse(cx - thick, top - 2, cx + thick, top + 3, bark[3])
        for i in range(6):
            ang = math.radians(-165 + i * 30)
            ex = cx + math.cos(ang) * canopy_w * 0.55
            ey = top + math.sin(ang) * canopy_w * 0.35
            a.line([(cx, top), (ex, ey)], r[3], 2)
            a.line([(ex, ey), (ex + math.cos(ang) * 5, ey + 3)], r[2], 1)
    else:
        blobs = clamp_int(p.get("branches"), 2, 9, 5)
        for i in range(blobs):
            bx = cx + a.rng.randint(-canopy_w // 3, canopy_w // 3)
            by = top + a.rng.randint(0, int(th * 0.22))
            rx = a.rng.randint(max(3, canopy_w // 5), max(4, canopy_w // 3))
            ry = a.rng.randint(max(3, canopy_w // 6), max(4, canopy_w // 3))
            a.ellipse(bx - rx, by - ry, bx + rx, by + ry, r[a.rng.choice([2, 3, 3, 4])])
        a.ellipse(left, top + int(th * 0.06), right, top + int(th * 0.34), r[3])
        # highlight and shade
        a.ellipse(left + 4, top + 4, left + canopy_w // 2, top + int(th * 0.2), r[4])
        a.dither(left + 2, top + int(th * 0.12), right - 2, top + int(th * 0.3), r[4], r[3], 0.45)
    density = clamp_float(p.get("leaf_density"), 0.1, 1.0, 0.6)
    a.speckle(left, top, right, top + int(th * 0.5), [r[1], r[2], r[5]], int(18 * density))


def gen_bush(a: Art, p: dict[str, Any]) -> None:
    r = a.ramp("leaf")
    n = clamp_int(p.get("lobes"), 2, 7, 4)
    base_y = a.h - 3
    width = a.w * clamp_float(p.get("width"), 0.4, 0.95, 0.72)
    cx = a.w // 2
    for i in range(n):
        bx = cx + int((i - (n - 1) / 2) * width / max(2, n))
        by = base_y - a.rng.randint(2, max(3, int(a.h * 0.16)))
        rx = int(width / n * a.rng.uniform(1.0, 1.7))
        ry = int(rx * a.rng.uniform(0.7, 1.05))
        a.ellipse(bx - rx, by - ry, bx + rx, by + ry // 2, r[2 + i % 2])
    a.ellipse(cx - width * 0.35, base_y - a.h * 0.25, cx + width * 0.1, base_y - a.h * 0.12, r[4])
    a.speckle(int(cx - width / 2), int(base_y - a.h * 0.28), int(cx + width / 2), base_y - 1, [r[1], r[3], r[5]], 22)
    for _ in range(clamp_int(p.get("berries"), 0, 12, 0)):
        bx = a.rng.randint(int(cx - width / 2), int(cx + width / 2))
        by = a.rng.randint(int(base_y - a.h * 0.3), base_y - 2)
        a.dot(bx, by, a.c("fire", 4))


def gen_flower(a: Art, p: dict[str, Any]) -> None:
    stem = a.c("leaf", 3)
    petal_ramp = a.rng.choice(["magic", "fire", "gold", "neon_pink", "snow"])
    pr = a.ramp(petal_ramp)
    cx = a.w // 2
    base = a.h - 2
    top = int(a.h * (1 - clamp_float(p.get("height"), 0.3, 0.9, 0.6)))
    a.line([(cx, base), (cx + a.rng.randint(-2, 2), top)], stem, 1)
    leaves = clamp_int(p.get("leaves"), 0, 4, 2)
    for i in range(leaves):
        yy = base - int((base - top) * (0.25 + 0.2 * i))
        side = -1 if i % 2 == 0 else 1
        a.ellipse(cx + side * 1 - 3, yy, cx + side * 7, yy + 3, a.c("leaf", 2))
    petals = clamp_int(p.get("petals"), 3, 10, 5)
    rad = max(2, int(a.w * clamp_float(p.get("petal_size"), 0.08, 0.3, 0.16)))
    for i in range(petals):
        ang = 2 * math.pi * i / petals - math.pi / 2
        px = cx + math.cos(ang) * rad
        py = top + math.sin(ang) * rad
        a.ellipse(px - rad * 0.7, py - rad * 0.7, px + rad * 0.7, py + rad * 0.7, pr[3])
        a.ellipse(px - rad * 0.3 - 1, py - rad * 0.3 - 1, px + rad * 0.1, py + rad * 0.1, pr[5])
    a.ellipse(cx - rad * 0.55, top - rad * 0.55, cx + rad * 0.55, top + rad * 0.55, a.c("gold", 4))


def gen_rock(a: Art, p: dict[str, Any]) -> None:
    s = a.ramp("stone")
    cx, cy = a.w / 2, a.h * 0.6
    rw = a.w * clamp_float(p.get("width"), 0.3, 0.95, 0.68) / 2
    rh = a.h * clamp_float(p.get("height"), 0.25, 0.8, 0.45) / 2
    pts = []
    n = clamp_int(p.get("vertices"), 5, 12, 8)
    for i in range(n):
        ang = 2 * math.pi * i / n
        rr = 0.72 + a.rng.random() * 0.38
        pts.append((cx + math.cos(ang) * rw * rr, cy + math.sin(ang) * rh * rr))
    a.poly(pts, s[2])
    a.poly([pts[0], pts[1], (cx, cy), (cx - rw * 0.4, cy - rh * 0.2)], s[1])
    a.poly([(cx - rw * 0.3, cy - rh * 0.6), (cx + rw * 0.1, cy - rh * 0.7), (cx + rw * 0.3, cy - rh * 0.1), (cx - rw * 0.1, cy + rh * 0.1)], s[4])
    a.dither(int(cx - rw), int(cy), int(cx + rw), int(cy + rh), s[3], s[2], 0.35)
    for _ in range(clamp_int(p.get("cracks"), 0, 6, 1)):
        x0 = a.rng.randint(int(cx - rw * 0.6), int(cx + rw * 0.6))
        y0 = a.rng.randint(int(cy - rh * 0.2), int(cy + rh * 0.4))
        a.line([(x0, y0), (x0 + a.rng.randint(-4, 4), y0 + a.rng.randint(2, 5))], s[0])


def gen_grass(a: Art, p: dict[str, Any]) -> None:
    r = a.ramp("leaf")
    blades = clamp_int(p.get("blades"), 3, 30, 9)
    base = a.h - 2
    for _ in range(blades):
        x = a.rng.randint(2, a.w - 3)
        h = a.rng.randint(int(a.h * 0.25), int(a.h * 0.8))
        sway = a.rng.randint(-3, 3)
        a.line([(x, base), (x + sway // 2, base - h // 2), (x + sway, base - h)], r[a.rng.choice([2, 3, 4])])
        if a.rng.random() < 0.4:
            a.dot(x + sway, base - h, r[5])


def gen_mushroom(a: Art, p: dict[str, Any]) -> None:
    stem_c = a.ramp("sand")
    cap_name = a.rng.choice(["fire", "magic", "neon_pink", "gold"])
    cap = a.ramp(cap_name)
    cx = a.w // 2
    base = a.h - 2
    stem_h = int(a.h * clamp_float(p.get("height"), 0.2, 0.6, 0.34))
    sw = max(2, int(a.w * 0.12))
    a.box(cx - sw, base - stem_h, cx + sw, base, stem_c[2])
    a.box(cx - sw, base - stem_h, cx - sw + 1, base, stem_c[3])
    cw = int(a.w * clamp_float(p.get("cap_width"), 0.35, 0.95, 0.66))
    ch = int(cw * 0.55)
    top = base - stem_h - ch
    a.ellipse(cx - cw // 2, top, cx + cw // 2, top + ch * 2, cap[2])
    a.box(cx - cw // 2, top + ch // 2, cx + cw // 2, top + ch, cap[2])
    a.ellipse(cx - cw // 2, top, cx + cw // 2, top + ch * 1.2, cap[3])
    a.ellipse(cx - cw // 3, top + 2, cx - cw // 8, top + ch // 2, cap[4])
    spots = clamp_int(p.get("spots"), 0, 10, 4)
    for _ in range(spots):
        sx = a.rng.randint(int(cx - cw * 0.4), int(cx + cw * 0.4))
        sy = a.rng.randint(int(top + ch * 0.25), int(top + ch * 0.85))
        rr = a.rng.randint(1, max(1, cw // 12))
        a.ellipse(sx - rr, sy - rr, sx + rr, sy + rr, a.rng.choice([stem_c[5], cap[5]]))
    a.dither(int(cx - cw / 2), int(top + ch * 0.55), int(cx + cw / 2), int(top + ch * 0.95), cap[1], cap[2], 0.4)


def gen_cloud(a: Art, p: dict[str, Any]) -> None:
    s = a.ramp("snow")
    n = clamp_int(p.get("puffs"), 3, 8, 5)
    cy = a.h * 0.5
    for i in range(n):
        px = a.w * (0.15 + 0.7 * (i + 0.5) / n)
        rad = a.w * a.rng.uniform(0.09, 0.2)
        py = cy + a.rng.uniform(-a.h * 0.12, a.h * 0.06)
        a.ellipse(px - rad, py - rad * 0.8, px + rad, py + rad * 0.8, s[3])
        a.ellipse(px - rad * 0.8, py - rad * 0.9, px + rad * 0.5, py + rad * 0.2, s[4])
    a.box(a.w * 0.15, cy + a.h * 0.06, a.w * 0.85, cy + a.h * 0.14, s[3])
    a.dither(int(a.w * 0.16), int(cy + a.h * 0.09), int(a.w * 0.84), int(cy + a.h * 0.14), s[2], s[3], 0.4)
    if p.get("rain"):
        for _ in range(8):
            x = a.rng.randint(int(a.w * 0.2), int(a.w * 0.8))
            y = int(cy + a.h * 0.16)
            a.line([(x, y), (x - 2, y + a.rng.randint(2, 5))], a.c("water", 4))


def gen_mountain(a: Art, p: dict[str, Any]) -> None:
    s = a.ramp("stone")
    snow = a.ramp("snow")
    peaks = clamp_int(p.get("peaks"), 1, 4, 2)
    base = a.h - 2
    for i in range(peaks):
        cx = a.w * (0.28 + 0.44 * i / max(1, peaks - 1)) if peaks > 1 else a.w / 2
        hw = a.w * a.rng.uniform(0.2, 0.34)
        ph = a.h * a.rng.uniform(0.45, 0.85)
        top = base - ph
        a.poly([(cx - hw, base), (cx, top), (cx + hw, base)], s[2])
        a.poly([(cx, top), (cx - hw, base), (cx - hw * 0.15, base)], s[1])
        a.poly([(cx, top), (cx + hw * 0.1, base), (cx + hw, base)], s[3])
        cap = ph * 0.22
        a.poly([(cx, top), (cx - hw * 0.22, top + cap), (cx - hw * 0.08, top + cap * 0.8), (cx, top + cap), (cx + hw * 0.14, top + cap * 0.9), (cx + hw * 0.22, top + cap)], snow[4])
    a.dither(1, int(base - a.h * 0.1), a.w - 1, base, s[3], s[2], 0.3)


def gen_plant(a: Art, p: dict[str, Any]) -> None:
    pot = a.ramp("fire")
    leaf = a.ramp("leaf")
    base = a.h - 2
    pot_w = int(a.w * clamp_float(p.get("pot_width"), 0.3, 0.8, 0.5))
    pot_h = int(a.h * 0.28)
    cx = a.w // 2
    a.poly([(cx - pot_w // 2, base - pot_h), (cx + pot_w // 2, base - pot_h),
            (cx + pot_w // 2 - 2, base), (cx - pot_w // 2 + 2, base)], pot[2])
    a.box(cx - pot_w // 2, base - pot_h, cx + pot_w // 2, base - pot_h + 2, pot[3])
    leaves = clamp_int(p.get("leaves"), 2, 10, 5)
    for i in range(leaves):
        ang = math.radians(-150 + 120 * i / max(1, leaves - 1))
        L = a.h * a.rng.uniform(0.25, 0.5)
        ex = cx + math.cos(ang) * L
        ey = base - pot_h - 2 + math.sin(ang) * L
        a.line([(cx, base - pot_h - 1), (ex, ey)], leaf[3], 1)
        a.ellipse(ex - 3, ey - 2, ex + 3, ey + 2, leaf[2])
        a.ellipse(ex - 2, ey - 2, ex, ey - 1, leaf[4])


# ---------------------------------------------------------------- fantasy

def gen_chest(a: Art, p: dict[str, Any]) -> None:
    wood = a.ramp("wood")
    gold = a.ramp("gold")
    w = a.w * clamp_float(p.get("width"), 0.4, 0.9, 0.68)
    h = a.h * clamp_float(p.get("height"), 0.3, 0.75, 0.5)
    x0 = int((a.w - w) / 2)
    x1 = int((a.w + w) / 2)
    y1 = a.h - 3
    y0 = int(y1 - h)
    lid_h = max(3, int(h * 0.32))
    a.box(x0, y0 + lid_h, x1, y1, wood[3])
    a.box(x0, y0 + lid_h, x1, y0 + lid_h + 2, wood[2])
    a.box(x0, y1 - 3, x1, y1, wood[1])
    a.plank_pattern(x0 + 1, y0 + lid_h + 2, x1, y1 - 2, wood, 4)
    a.ellipse(x0, y0, x1, y0 + lid_h * 2, wood[2])
    a.box(x0, y0 + lid_h, x1, y0 + lid_h + 1, wood[2])
    a.ellipse(x0 + 2, y0 + 2, x1 - 2, y0 + lid_h, wood[4])
    for bx in (x0 + 3, x1 - 3):
        a.box(bx - 1, y0 + lid_h, bx + 1, y1, gold[3])
        a.box(bx - 1, y0 + lid_h, bx, y1, gold[4])
    a.box(x0 - 1, y0 + lid_h + int(h * 0.12), x1 + 1, y0 + lid_h + int(h * 0.12) + 2, gold[2])
    lx = (x0 + x1) // 2
    a.box(lx - 3, y0 + lid_h + int(h * 0.1), lx + 3, y0 + lid_h + int(h * 0.1) + 6, gold[3])
    a.box(lx - 1, y0 + lid_h + int(h * 0.16), lx + 1, y0 + lid_h + int(h * 0.16) + 2, gold[0])
    if p.get("treasure"):
        for _ in range(5):
            a.dot(a.rng.randint(lx - 5, lx + 5), y0 + lid_h + 1 + a.rng.randint(-2, 2), gold[5])


def gen_barrel(a: Art, p: dict[str, Any]) -> None:
    wood = a.ramp("wood")
    metal = a.ramp("metal")
    w = a.w * clamp_float(p.get("width"), 0.3, 0.7, 0.5)
    hh = a.h * clamp_float(p.get("height"), 0.4, 0.9, 0.68)
    cx = a.w / 2
    y0 = int((a.h - hh) / 2)
    y1 = int(y0 + hh)
    a.ellipse(cx - w / 2, y0, cx + w / 2, y0 + w * 0.3, wood[3])
    a.box(cx - w / 2, y0 + w * 0.15, cx + w / 2, y1 - w * 0.15, wood[2])
    a.ellipse(cx - w / 2, y1 - w * 0.3, cx + w / 2, y1, wood[1])
    a.ellipse(cx - w / 2 + 2, y0 + 2, cx + w / 2 - 2, y0 + w * 0.22, wood[4])
    for i in range(5):
        sx = int(cx - w / 2 + w * (i + 0.5) / 5)
        a.line([(sx, y0 + int(w * 0.15)), (sx, y1 - int(w * 0.15))], wood[1])
        a.line([(sx + 1, y0 + int(w * 0.2)), (sx + 1, y1 - int(w * 0.2))], wood[3])
    for fy in (0.22, 0.75):
        yy = int(y0 + hh * fy)
        a.box(cx - w / 2 - 1, yy, cx + w / 2 + 1, yy + 2, metal[3])
        a.box(cx - w / 2 - 1, yy, cx + w / 2 + 1, yy, metal[4])
    if p.get("label"):
        a.box(cx - 4, y0 + hh * 0.5 - 3, cx + 4, y0 + hh * 0.5 + 3, metal[1])
        a.line([(cx - 2, y0 + hh * 0.5), (cx + 2, y0 + hh * 0.5)], metal[3])


def gen_crystal(a: Art, p: dict[str, Any]) -> None:
    ramp = a.rng.choice(["ice", "magic", "neon_blue", "poison"])
    c = a.ramp(ramp)
    cx = a.w // 2
    base = a.h - 3
    shards = clamp_int(p.get("shards"), 1, 5, 3)
    for i in range(shards):
        ox = int((i - (shards - 1) / 2) * a.w * 0.13)
        hh = a.h * a.rng.uniform(0.35, 0.7)
        ww = a.w * a.rng.uniform(0.08, 0.16)
        top = base - hh
        a.poly([(cx + ox, top), (cx + ox + ww, base), (cx + ox, base + 2), (cx + ox - ww, base)], c[2])
        a.poly([(cx + ox, top), (cx + ox - ww, base), (cx + ox - 1, base)], c[1])
        a.poly([(cx + ox, top + 2), (cx + ox + ww - 2, base - 2), (cx + ox + ww // 2, top + hh * 0.4)], c[4])
    if p.get("glow", True):
        a.glow(c[4], 3, 0.55)
    a.speckle(cx - 6, base - 10, cx + 6, base, [c[5]], 4)


def gen_potion(a: Art, p: dict[str, Any]) -> None:
    glass = a.ramp("snow")
    liquid_name = str(p.get("liquid", "fire"))
    liquid = a.ramp(liquid_name if liquid_name in RAMPS else "fire")
    cx = a.w // 2
    base = a.h - 3
    bw = a.w * clamp_float(p.get("width"), 0.2, 0.6, 0.36)
    bh = a.h * clamp_float(p.get("height"), 0.3, 0.7, 0.48)
    y0 = base - bh
    a.ellipse(cx - bw, y0, cx + bw, base, glass[3])
    a.box(cx - bw, y0 + bh * 0.2, cx + bw, base - bh * 0.2, glass[3])
    a.ellipse(cx - bw + 1, base - bh * 0.5, cx + bw - 1, base - 1, liquid[3])
    a.box(cx - bw, base - bh * 0.5, cx + bw, base - 2, liquid[3])
    a.box(cx - bw + 1, base - bh * 0.42, cx + bw - 1, base - 2, liquid[2])
    neck_w = max(2, int(bw * 0.45))
    a.box(cx - neck_w, y0 - bh * 0.18, cx + neck_w, y0 + bh * 0.3, glass[4])
    a.box(cx - neck_w - 1, y0 - bh * 0.22, cx + neck_w + 1, y0 - bh * 0.12, a.c("wood", 3))
    a.ellipse(cx - bw * 0.6, y0 + bh * 0.15, cx - bw * 0.1, y0 + bh * 0.55, glass[5])
    a.dot(cx - bw * 0.3, y0 + bh * 0.3, "#ffffff")
    if p.get("bubbles", True):
        for _ in range(3):
            bx = a.rng.randint(int(cx - bw * 0.5), int(cx + bw * 0.5))
            by = a.rng.randint(int(base - bh * 0.4), base - 3)
            a.dot(bx, by, liquid[5])


def gen_sword(a: Art, p: dict[str, Any]) -> None:
    blade = a.ramp("metal")
    gold = a.ramp("gold")
    grip = a.ramp(str(p.get("grip", "cloth")) if str(p.get("grip", "cloth")) in RAMPS else "cloth")
    cx = a.w // 2
    top = 3
    tip = a.h - int(a.h * 0.32)
    bw = max(2, int(a.w * clamp_float(p.get("width"), 0.04, 0.16, 0.08)))
    a.poly([(cx, top), (cx + bw, top + a.h * 0.12), (cx + bw, tip), (cx, tip + 3), (cx - bw, tip), (cx - bw, top + a.h * 0.12)], blade[3])
    a.poly([(cx, top), (cx - bw, top + a.h * 0.12), (cx - bw, tip), (cx, tip + 3)], blade[4])
    a.line([(cx, top + 3), (cx, tip)], blade[1])
    gy = tip + 2
    a.box(cx - bw * 2.2, gy, cx + bw * 2.2, gy + 2, gold[3])
    a.box(cx - bw * 2.2, gy, cx + bw * 2.2, gy, gold[4])
    a.poly([(cx - bw * 2.2, gy), (cx - bw * 2.6, gy + 1), (cx - bw * 2.2, gy + 2)], gold[4])
    a.poly([(cx + bw * 2.2, gy), (cx + bw * 2.6, gy + 1), (cx + bw * 2.2, gy + 2)], gold[4])
    for i in range(3):
        a.box(cx - 2, gy + 3 + i * 2, cx + 2, gy + 4 + i * 2, grip[3])
    a.box(cx - 3, gy + 9, cx + 3, gy + 11, gold[2])
    a.dot(cx, gy + 10, gold[5])


def gen_shield(a: Art, p: dict[str, Any]) -> None:
    metal = a.ramp("metal")
    main = a.ramp(str(p.get("metal", "gold")) if str(p.get("metal", "gold")) in RAMPS else "gold")
    shape = str(p.get("shape", "kite"))
    cx = a.w / 2
    top = a.h * 0.14
    w = a.w * 0.68
    bottom = a.h * 0.86
    if shape == "round":
        a.ellipse(cx - w / 2, top, cx + w / 2, top + w, main[2])
        a.ellipse(cx - w / 2 + 2, top + 2, cx + w / 2 - 2, top + w - 2, main[3])
        a.ellipse(cx - w / 6, top + w / 4, cx + w / 6, top + w * 0.75, main[5])
    elif shape == "tower":
        a.poly([(cx - w / 2, top), (cx + w / 2, top), (cx + w / 2, bottom - a.h * 0.08), (cx, bottom), (cx - w / 2, bottom - a.h * 0.08)], main[2])
        a.poly([(cx - w / 2 + 2, top + 2), (cx + w / 2 - 2, top + 2), (cx + w / 2 - 2, bottom - a.h * 0.09), (cx, bottom - 3), (cx - w / 2 + 2, bottom - a.h * 0.09)], main[3])
    else:
        a.poly([(cx - w / 2, top), (cx + w / 2, top), (cx + w / 2, bottom - a.h * 0.22), (cx, bottom), (cx - w / 2, bottom - a.h * 0.22)], main[2])
        a.poly([(cx - w / 2 + 2, top + 3), (cx + w / 2 - 2, top + 3), (cx + w / 2 - 2, bottom - a.h * 0.23), (cx, bottom - 4), (cx - w / 2 + 2, bottom - a.h * 0.23)], main[3])
    a.line([(cx - w / 2 + 1, top + 1), (cx, top + 1), (cx + w / 2 - 1, top + 1)], metal[5])
    emblem = str(p.get("emblem", "cross"))
    cy = a.h * 0.45
    if emblem == "cross":
        a.box(cx - 2, cy - 6, cx + 2, cy + 6, main[5])
        a.box(cx - 6, cy - 2, cx + 6, cy + 2, main[5])
    elif emblem == "star":
        for i in range(5):
            ang = math.pi * 2 * i / 5 - math.pi / 2
            a.line([(cx, cy), (cx + math.cos(ang) * 7, cy + math.sin(ang) * 7)], main[5], 1)
    else:
        a.ellipse(cx - 4, cy - 4, cx + 4, cy + 4, main[5])
    a.dither(int(cx - w / 2), int(bottom - a.h * 0.25), int(cx + w / 2), int(bottom - 2), main[1], main[2], 0.35)


def gen_orb(a: Art, p: dict[str, Any]) -> None:
    magic = a.ramp("magic")
    cx, cy = a.w / 2, a.h / 2
    rad = a.w * clamp_float(p.get("radius"), 0.2, 0.42, 0.28)
    a.glow(magic[4], 4, 0.7)
    a.ellipse(cx - rad, cy - rad, cx + rad, cy + rad, magic[3])
    a.ellipse(cx - rad * 0.8, cy - rad * 0.8, cx + rad * 0.5, cy + rad * 0.2, magic[5])
    a.ellipse(cx - rad, cy + rad * 0.2, cx + rad, cy + rad, magic[2])
    a.ellipse(cx - rad, cy, cx + rad, cy + rad * 0.3, magic[1])
    runes = clamp_int(p.get("runes"), 0, 8, 4)
    for i in range(runes):
        ang = math.pi * 2 * i / max(1, runes)
        a.dot(int(cx + math.cos(ang) * rad * 0.7), int(cy + math.sin(ang) * rad * 0.7), magic[5])
    for _ in range(3):
        sx = a.rng.randint(int(cx - rad * 0.6), int(cx + rad * 0.2))
        sy = a.rng.randint(int(cy - rad * 0.5), int(cy))
        a.dot(sx, sy, "#ffffff")


def gen_totem(a: Art, p: dict[str, Any]) -> None:
    stone = a.ramp("stone")
    gold = a.ramp("gold")
    cx = a.w // 2
    blocks = clamp_int(p.get("blocks"), 1, 4, 2)
    bw = a.w * 0.44
    bh = a.h * 0.28
    base = a.h - 3
    for i in range(blocks):
        y1 = base - i * (bh + 1)
        y0 = y1 - bh
        a.box(cx - bw / 2, y0, cx + bw / 2, y1, stone[2])
        a.box(cx - bw / 2, y0, cx - bw / 2 + 2, y1, stone[3])
        a.box(cx - bw / 2, y1 - 3, cx + bw / 2, y1, stone[1])
        ey = int(y0 + bh * 0.35)
        a.box(cx - bw * 0.28, ey, cx - bw * 0.1, ey + 2, gold[4])
        a.box(cx + bw * 0.1, ey, cx + bw * 0.28, ey + 2, gold[4])
        a.box(cx - bw * 0.22, int(y0 + bh * 0.65), cx + bw * 0.22, int(y0 + bh * 0.75), stone[0])
    a.poly([(cx - bw * 0.8, base), (cx - bw * 0.7, base - 6), (cx - bw * 0.35, base - 4), (cx - bw * 0.2, base)], stone[1])
    a.poly([(cx + bw * 0.2, base), (cx + bw * 0.35, base - 4), (cx + bw * 0.7, base - 6), (cx + bw * 0.8, base)], stone[1])


# ---------------------------------------------------------------- environment

def gen_house(a: Art, p: dict[str, Any]) -> None:
    wall_name = str(p.get("walls", "sand"))
    walls = a.ramp(wall_name if wall_name in RAMPS else "sand")
    roof = a.ramp(str(p.get("roof", "fire")) if str(p.get("roof", "fire")) in RAMPS else "fire")
    wood = a.ramp("wood")
    w = a.w * 0.72
    hh = a.h * 0.52
    x0 = (a.w - w) / 2
    x1 = x0 + w
    y1 = a.h - 4
    y0 = y1 - hh
    a.box(x0, y0, x1, y1, walls[2])
    a.brick_pattern(int(x0), int(y0), int(x1), int(y1), walls, walls[1], 3, 7)
    roof_h = a.h * 0.24
    if p.get("roof_type", "gable") == "flat":
        a.box(x0 - 2, y0 - roof_h * 0.35, x1 + 2, y0, roof[2])
        a.box(x0 - 2, y0 - roof_h * 0.35, x1 + 2, y0 - roof_h * 0.25, roof[3])
    else:
        a.poly([(x0 - 4, y0), (a.w / 2, y0 - roof_h), (x1 + 4, y0)], roof[2])
        a.poly([(a.w / 2, y0 - roof_h), (x0 - 4, y0), (a.w / 2, y0)], roof[1])
        a.line([(a.w / 2, y0 - roof_h + 1), (a.w / 2, y0 - 1)], roof[0])
    door_w = max(4, int(w * 0.2))
    a.box(a.w / 2 - door_w / 2, y1 - hh * 0.45, a.w / 2 + door_w / 2, y1, wood[2])
    a.box(a.w / 2 - door_w / 2 + 1, y1 - hh * 0.45 + 1, a.w / 2 + door_w / 2 - 1, y1 - 2, wood[3])
    a.dot(int(a.w / 2 + door_w * 0.3), int(y1 - hh * 0.2), a.c("gold", 4))
    win = clamp_int(p.get("windows"), 0, 4, 2)
    for i in range(win):
        wx = x0 + w * (0.18 + 0.32 * i)
        a.box(wx, y0 + hh * 0.18, wx + w * 0.16, y0 + hh * 0.45, a.c("water", 3))
        a.box(wx, y0 + hh * 0.18, wx + w * 0.16, y0 + hh * 0.2, wood[1])
        a.line([(wx + w * 0.08, y0 + hh * 0.18), (wx + w * 0.08, y0 + hh * 0.45)], wood[1])
    if p.get("chimney"):
        a.box(x1 - w * 0.2, y0 - roof_h * 0.8, x1 - w * 0.08, y0 - roof_h * 0.2, walls[1])
    a.speckle(int(x0), int(y0), int(x1), int(y1), [walls[1], walls[3]], 10)


def gen_tower(a: Art, p: dict[str, Any]) -> None:
    stone = a.ramp("stone")
    roof = a.ramp(str(p.get("roof", "neon_blue")) if str(p.get("roof", "neon_blue")) in RAMPS else "neon_blue")
    w = a.w * 0.4
    x0 = (a.w - w) / 2
    x1 = x0 + w
    base = a.h - 3
    top = a.h * (0.22 if p.get("spire", True) else 0.18)
    a.box(x0, top, x1, base, stone[2])
    a.brick_pattern(int(x0), int(top), int(x1), int(base), stone, stone[1], 4, 7)
    for i in range(4):
        bx = x0 + i * (w / 4)
        a.box(bx, top - 4, bx + w / 8, top, stone[3])
    if p.get("spire", True):
        a.poly([(x0 - 2, top - 4), ((x0 + x1) / 2, top - a.h * 0.25), (x1 + 2, top - 4)], roof[2])
        a.poly([((x0 + x1) / 2, top - a.h * 0.25), (x0 - 2, top - 4), ((x0 + x1) / 2, top - 4)], roof[1])
    for i in range(2):
        wy = top + (base - top) * (0.25 + i * 0.28)
        a.box((x0 + x1) / 2 - 2, wy, (x0 + x1) / 2 + 2, wy + 5, a.c("water", 2))
        a.box((x0 + x1) / 2 - 1, wy + 1, (x0 + x1) / 2 + 2, wy + 4, a.c("water", 4))
    a.box((x0 + x1) / 2 - 3, base - 7, (x0 + x1) / 2 + 3, base, a.ramp("wood")[2])
    if p.get("flag"):
        a.line([((x0 + x1) / 2, top - a.h * 0.25), ((x0 + x1) / 2, top - a.h * 0.42)], stone[0])
        a.poly([((x0 + x1) / 2, top - a.h * 0.42), ((x0 + x1) / 2 + 8, top - a.h * 0.37), ((x0 + x1) / 2, top - a.h * 0.32)], a.c("fire", 4))
    a.speckle(int(x0), int(top), int(x1), int(base), [stone[1], stone[4]], 12)


def gen_ruin(a: Art, p: dict[str, Any]) -> None:
    stone = a.ramp("stone")
    vine = a.ramp("leaf")
    base = a.h - 4
    cols = clamp_int(p.get("columns"), 1, 3, 2)
    for i in range(cols):
        cx = a.w * (0.25 + 0.5 * i / max(1, cols - 1)) if cols > 1 else a.w / 2
        hh = a.h * a.rng.uniform(0.3, 0.6)
        ww = a.w * 0.14
        a.box(cx - ww / 2, base - hh, cx + ww / 2, base, stone[3])
        a.box(cx - ww / 2, base - hh, cx - ww / 2 + 2, base, stone[4])
        for yy in range(int(base - hh), base, 5):
            a.line([(cx - ww / 2, yy), (cx + ww / 2, yy)], stone[1])
        if i == 0 and cols > 1:
            mid = a.w / 2
            a.box(cx - ww / 2, base - hh * 0.75, mid + ww / 2, base - hh * 0.75 + 4, stone[2])
            a.poly([(cx, base - hh * 0.75), (cx + ww / 2, base - hh * 0.75), (cx + ww / 2, base - hh * 0.35)], stone[1])
    rubble = clamp_int(p.get("rubble"), 0, 16, 6)
    for _ in range(rubble):
        rx = a.rng.randint(3, a.w - 4)
        rw = a.rng.randint(2, 5)
        a.box(rx - rw, base - a.rng.randint(0, 3), rx + rw, base + 1, a.rng.choice(stone[1:4]))
    for _ in range(clamp_int(p.get("vines"), 0, 8, 3)):
        vx = a.rng.randint(4, a.w - 5)
        vy = a.rng.randint(int(a.h * 0.3), base - 4)
        a.line([(vx, vy), (vx + 1, vy + 3), (vx - 1, vy + 6)], vine[3])
        a.dot(vx, vy + 2, vine[4])


def gen_fence(a: Art, p: dict[str, Any]) -> None:
    material = str(p.get("material", "wood"))
    ramp = a.ramp("wood" if material == "wood" else ("metal" if material == "metal" else "stone"))
    base = a.h - 4
    posts = clamp_int(p.get("posts"), 2, 8, 4)
    ph = a.h * clamp_float(p.get("height"), 0.3, 0.7, 0.42)
    for i in range(posts):
        x = a.w * (0.12 + 0.76 * i / max(1, posts - 1))
        a.box(x - 1, base - ph, x + 1, base, ramp[3])
        a.dot(x, int(base - ph) - 1, ramp[4])
    for yy in (0.35, 0.7):
        y = base - ph * (1 - yy) - 2
        a.box(a.w * 0.1, y, a.w * 0.9, y + 2, ramp[2])
        a.box(a.w * 0.1, y, a.w * 0.9, y, ramp[4])
    a.dither(int(a.w * 0.1), int(base - ph), int(a.w * 0.9), base - 1, ramp[1], ramp[2], 0.25)


def gen_bridge(a: Art, p: dict[str, Any]) -> None:
    wood = a.ramp("wood")
    stone = a.ramp("stone")
    material = str(p.get("material", "wood"))
    ramp = wood if material == "wood" else stone
    y = a.h * 0.55
    a.box(a.w * 0.05, y, a.w * 0.95, y + a.h * 0.12, ramp[2])
    a.plank_pattern(int(a.w * 0.06), int(y + 1), int(a.w * 0.94), int(y + a.h * 0.11), ramp, 3)
    for side in (0, 1):
        yy = y - a.h * 0.16 if side == 0 else y + a.h * 0.12
        a.box(a.w * 0.05, yy, a.w * 0.95, yy + 2, ramp[3])
        for i in range(4):
            x = a.w * (0.08 + 0.28 * i)
            a.box(x, yy - (5 if side == 0 else 0), x + 1, yy + (2 if side == 0 else 7), ramp[1])
    if p.get("ropes", False):
        pts = [(a.w * 0.1, y - a.h * 0.12), (a.w * 0.3, y - a.h * 0.05), (a.w * 0.5, y - a.h * 0.1), (a.w * 0.7, y - a.h * 0.05), (a.w * 0.9, y - a.h * 0.12)]
        a.line(pts, a.c("sand", 4))
    a.dither(int(a.w * 0.05), int(y), int(a.w * 0.95), int(y + a.h * 0.12), ramp[1], ramp[2], 0.25)


def gen_door(a: Art, p: dict[str, Any]) -> None:
    wood = a.ramp("wood")
    stone = a.ramp("stone")
    cx = a.w / 2
    w = a.w * clamp_float(p.get("width"), 0.3, 0.7, 0.46)
    hh = a.h * clamp_float(p.get("height"), 0.5, 0.9, 0.72)
    base = a.h - 3
    top = base - hh
    a.box(cx - w / 2 - 2, top - 2, cx + w / 2 + 2, base, stone[2])
    a.box(cx - w / 2, top, cx + w / 2, base, wood[3])
    a.box(cx - w / 2, top, cx + w / 2, top + 2, wood[1])
    a.line([(cx, top + 2), (cx, base)], wood[1])
    panels = clamp_int(p.get("panels"), 1, 4, 2)
    for i in range(panels):
        py = top + 4 + i * (hh - 8) / max(1, panels)
        a.box(cx - w / 2 + 3, py, cx + w / 2 - 3, py + (hh - 8) / max(1, panels) - 2, wood[2])
    if p.get("bars"):
        for i in range(3):
            y = top + hh * (0.25 + i * 0.22)
            a.box(cx - w / 2, y, cx + w / 2, y + 1, a.ramp("metal")[2])
    a.dot(int(cx + w * 0.32), int(top + hh * 0.55), a.c("gold", 4))
    if p.get("open"):
        a.box(cx - w / 2 + 1, top + 1, cx, base - 1, "#0b0c10")


def gen_window(a: Art, p: dict[str, Any]) -> None:
    wood = a.ramp("wood")
    glass = a.ramp("water" if not p.get("lit") else "gold")
    w = a.w * 0.6
    hh = a.h * 0.64
    x0, y0 = (a.w - w) / 2, (a.h - hh) / 2
    a.box(x0 - 2, y0 - 2, x0 + w + 2, y0 + hh + 2, wood[2])
    a.box(x0, y0, x0 + w, y0 + hh, glass[2])
    a.box(x0, y0, x0 + w, y0 + hh * 0.5, glass[3])
    a.poly([(x0 + 2, y0 + hh * 0.55), (x0 + w * 0.45, y0 + 2), (x0 + w * 0.65, y0 + 2), (x0 + w * 0.2, y0 + hh * 0.55)], glass[5])
    a.line([(x0 + w / 2, y0), (x0 + w / 2, y0 + hh)], wood[3], 1)
    a.line([(x0, y0 + hh / 2), (x0 + w, y0 + hh / 2)], wood[3], 1)
    a.box(x0 - 4, y0 + hh + 2, x0 + w + 4, y0 + hh + 4, wood[3])
    if p.get("flower_box"):
        a.box(x0, y0 + hh + 4, x0 + w, y0 + hh + 7, wood[2])
        for i in range(4):
            a.dot(int(x0 + w * (0.15 + 0.23 * i)), int(y0 + hh + 3), a.c("leaf", 4))
            a.dot(int(x0 + w * (0.2 + 0.23 * i)), int(y0 + hh + 2), a.c("fire", 4))


def gen_platform(a: Art, p: dict[str, Any]) -> None:
    style = str(p.get("style", "grass"))
    if style == "grass":
        top = a.ramp("leaf")
        body = a.ramp("wood" if p.get("wood") else "dirt")
    elif style == "metal":
        top = a.ramp("metal")
        body = a.ramp("metal")
    else:
        top = a.ramp("stone")
        body = a.ramp("stone")
    y = a.h * 0.38
    a.box(a.w * 0.06, y, a.w * 0.94, y + a.h * 0.16, body[2])
    a.box(a.w * 0.06, y, a.w * 0.94, y + 4, top[3])
    a.box(a.w * 0.06, y, a.w * 0.94, y + 1, top[4])
    if style != "metal":
        a.plank_pattern(int(a.w * 0.07), int(y + 4), int(a.w * 0.93), int(y + a.h * 0.15), body, 4)
    for i in range(4):
        x = a.w * (0.08 + 0.28 * i)
        a.box(x, y + a.h * 0.1, x + 1, y + a.h * 0.2, body[1])
    for i in range(3):
        a.box(a.w * 0.6 + i * 4, y + a.h * 0.16, a.w * 0.6 + i * 4 + 1, y + a.h * 0.25, body[1])
    a.dither(int(a.w * 0.06), int(y + 5), int(a.w * 0.94), int(y + a.h * 0.14), body[1], body[2], 0.2)
    a.speckle(int(a.w * 0.08), int(y), int(a.w * 0.92), int(y + 3), [top[5]], 5)


# ---------------------------------------------------------------- sci-fi

def gen_computer(a: Art, p: dict[str, Any]) -> None:
    metal = a.ramp("metal")
    glow = a.ramp(str(p.get("glow", "neon_blue")) if str(p.get("glow", "neon_blue")) in RAMPS else "neon_blue")
    w, hh = a.w * 0.7, a.h * 0.55
    x0, y0 = (a.w - w) / 2, a.h * 0.1
    a.box(x0, y0, x0 + w, y0 + hh, metal[2])
    a.box(x0 + 2, y0 + 2, x0 + w - 2, y0 + hh - 2, "#0c1013")
    a.box(x0 + 3, y0 + 3, x0 + w - 3, y0 + hh - 3, glow[1])
    rows = clamp_int(p.get("lines"), 2, 8, 4)
    for i in range(rows):
        yy = y0 + 4 + i * (hh - 8) / max(1, rows)
        lw = a.rng.randint(int(w * 0.2), int(w * 0.7))
        a.box(x0 + 4, yy, x0 + 4 + lw, yy + 1, glow[4])
    a.box(x0 - 2, y0 + hh, x0 + w + 2, y0 + hh + 3, metal[3])
    a.box((a.w - w * 0.4) / 2, y0 + hh + 3, (a.w + w * 0.4) / 2, y0 + hh + 5, metal[1])
    if p.get("tower"):
        tx = x0 + w + 3
        a.box(tx, a.h * 0.2, tx + a.w * 0.14, a.h * 0.85, metal[2])
        for i in range(3):
            a.dot(int(tx + 2), int(a.h * (0.3 + i * 0.12)), glow[4] if i % 2 == 0 else a.c("fire", 4))
    a.glow(glow[3], 2, 0.25)


def gen_console(a: Art, p: dict[str, Any]) -> None:
    metal = a.ramp("metal")
    glow = a.ramp(str(p.get("glow", "poison")) if str(p.get("glow", "poison")) in RAMPS else "poison")
    w, hh = a.w * 0.86, a.h * 0.56
    x0, y0 = (a.w - w) / 2, (a.h - hh) / 2
    a.poly([(x0, y0 + hh * 0.2), (x0 + w * 0.12, y0), (x0 + w, y0), (x0 + w, y0 + hh), (x0, y0 + hh)], metal[2])
    a.box(x0 + 3, y0 + 4, x0 + w * 0.55, y0 + hh * 0.55, "#0a0d10")
    a.speckle(int(x0 + 5), int(y0 + 6), int(x0 + w * 0.54), int(y0 + hh * 0.5), [glow[3], glow[4]], 10)
    knobs = clamp_int(p.get("knobs"), 1, 6, 3)
    for i in range(knobs):
        kx = x0 + w * 0.68 + (i % 3) * w * 0.09
        ky = y0 + hh * (0.22 + 0.3 * (i // 3))
        a.ellipse(kx - 2, ky - 2, kx + 2, ky + 2, metal[4])
        a.dot(int(kx), int(ky), a.c("fire", 4))
    for i in range(4):
        a.box(x0 + w * 0.62, y0 + hh * 0.62 + i * 4, x0 + w * 0.92, y0 + hh * 0.62 + i * 4 + 1, metal[1])
        a.box(x0 + w * 0.64, y0 + hh * 0.62 + i * 4, x0 + w * 0.64 + a.rng.randint(2, 10), y0 + hh * 0.62 + i * 4 + 1, glow[3])
    a.box(x0, y0 + hh - 2, x0 + w, y0 + hh, metal[1])


def gen_robot(a: Art, p: dict[str, Any]) -> None:
    metal = a.ramp("metal")
    accent = a.ramp(str(p.get("accent", "neon_blue")) if str(p.get("accent", "neon_blue")) in RAMPS else "neon_blue")
    cx = a.w / 2
    head = a.w * 0.3
    hy = a.h * 0.12
    a.box(cx - head / 2, hy, cx + head / 2, hy + head * 0.8, metal[2])
    a.box(cx - head / 2 + 2, hy + 3, cx + head / 2 - 2, hy + head * 0.55, "#0b0e12")
    eye_w = max(2, int(head * 0.16))
    a.box(cx - head * 0.28, hy + head * 0.2, cx - head * 0.28 + eye_w, hy + head * 0.2 + 2, accent[4])
    a.box(cx + head * 0.12, hy + head * 0.2, cx + head * 0.12 + eye_w, hy + head * 0.2 + 2, accent[4])
    a.line([(cx, hy), (cx, hy - 5)], metal[3])
    a.ellipse(cx - 1, hy - 7, cx + 1, hy - 5, accent[4])
    bt = a.h * 0.36
    bw = a.w * 0.42
    a.box(cx - bw / 2, bt, cx + bw / 2, bt + a.h * 0.28, metal[2])
    a.box(cx - bw * 0.3, bt + 3, cx + bw * 0.3, bt + a.h * 0.16, metal[3])
    a.box(cx - bw * 0.12, bt + a.h * 0.07, cx + bw * 0.12, bt + a.h * 0.12, accent[3])
    for side in (-1, 1):
        ax = cx + side * (bw / 2 + 2)
        a.box(ax - 2, bt + 3, ax + 2, bt + a.h * 0.24, metal[2])
        a.box(ax - 2, bt + a.h * 0.24, ax + 2, bt + a.h * 0.3, accent[2])
    legs = clamp_int(p.get("legs"), 1, 2, 2)
    for i in range(legs):
        lx = cx - bw * 0.25 if legs == 2 and i == 0 else (cx + bw * 0.25 if legs == 2 else cx)
        a.box(lx - 3, bt + a.h * 0.28, lx + 3, a.h - 5, metal[2])
        a.box(lx - 4, a.h - 5, lx + 4, a.h - 2, metal[3])
    a.speckle(int(cx - head / 2), int(hy), int(cx + head / 2), int(hy + head * 0.8), [metal[4]], 6)


def gen_container(a: Art, p: dict[str, Any]) -> None:
    metal = a.ramp("metal")
    accent = a.ramp(str(p.get("stripe", "fire")) if str(p.get("stripe", "fire")) in RAMPS else "fire")
    w, hh = a.w * 0.72, a.h * 0.5
    x0, y0 = (a.w - w) / 2, (a.h - hh) / 2
    a.box(x0, y0, x0 + w, y0 + hh, metal[2])
    for i in range(5):
        x = x0 + 2 + i * (w - 4) / 5
        a.box(x, y0 + 2, x + 1, y0 + hh - 2, metal[1])
        a.box(x + 1, y0 + 2, x + 2, y0 + hh - 2, metal[4])
    a.box(x0, y0 + 2, x0 + w, y0 + 6, metal[1])
    a.box(x0, y0 + hh - 6, x0 + w, y0 + hh - 2, metal[1])
    if p.get("hazard"):
        for i in range(5):
            x = x0 + w * 0.25 + i * 4
            a.poly([(x, y0 + hh * 0.55), (x + 3, y0 + hh * 0.55), (x, y0 + hh * 0.75), (x - 3, y0 + hh * 0.75)], accent[4])
    a.box(x0 + w * 0.1, y0 + hh * 0.25, x0 + w * 0.3, y0 + hh * 0.4, metal[1])
    a.line([(x0 + w * 0.12, y0 + hh * 0.3), (x0 + w * 0.28, y0 + hh * 0.3)], metal[4])
    a.line([(x0 + w * 0.12, y0 + hh * 0.35), (x0 + w * 0.24, y0 + hh * 0.35)], metal[4])


def gen_industrial(a: Art, p: dict[str, Any]) -> None:
    metal = a.ramp("metal")
    accent = a.ramp(str(p.get("accent", "fire")) if str(p.get("accent", "fire")) in RAMPS else "fire")
    base = a.h - 3
    tw = a.w * 0.28
    a.box(a.w * 0.6 - tw / 2, a.h * 0.3, a.w * 0.6 + tw / 2, base, metal[2])
    for i in range(3):
        yy = a.h * (0.36 + i * 0.18)
        a.box(a.w * 0.6 - tw / 2, yy, a.w * 0.6 + tw / 2, yy + 2, metal[4])
    a.box(a.w * 0.1, a.h * 0.35, a.w * 0.34, a.h * 0.55, metal[3])
    a.line([(a.w * 0.34, a.h * 0.45), (a.w * 0.6 - tw / 2, a.h * 0.45)], metal[1], 3)
    cx = a.w * 0.54
    cy = a.h * 0.62
    a.ellipse(cx - 7, cy - 7, cx + 7, cy + 7, metal[2])
    a.ellipse(cx - 5, cy - 5, cx + 5, cy + 5, metal[3])
    for i in range(4):
        ang = math.pi * i / 2
        a.line([(cx, cy), (cx + math.cos(ang) * 6, cy + math.sin(ang) * 6)], accent[3], 1)
    a.box(a.w * 0.6 - 2, a.h * 0.16, a.w * 0.6 + 2, a.h * 0.3, metal[1])
    a.glow(accent[4], 3, 0.35) if p.get("glow") else None
    for i in range(4):
        a.box(a.w * 0.06 + i * 4, base - 4, a.w * 0.06 + i * 4 + 2, base, metal[1])


def gen_decoration(a: Art, p: dict[str, Any]) -> None:
    glow = a.ramp(str(p.get("neon", "neon_pink")) if str(p.get("neon", "neon_pink")) in RAMPS else "neon_pink")
    frame = a.ramp("metal")
    mode = str(p.get("mode", "sign"))
    if mode == "pillar":
        x = a.w / 2
        a.box(x - 4, a.h * 0.15, x + 4, a.h - 4, frame[2])
        for i in range(3):
            a.box(x - 6, a.h * (0.25 + i * 0.22), x + 6, a.h * (0.25 + i * 0.22) + 2, glow[3])
        a.glow(glow[4], 3, 0.4)
        return
    w, hh = a.w * 0.52, a.h * 0.34
    x0, y0 = (a.w - w) / 2, (a.h - hh) / 2
    a.box(x0 + 4, y0 + hh, x0 + w * 0.35, y0 + hh + 4, frame[2])
    a.box(x0 + w * 0.65, y0 + hh, x0 + w - 4, y0 + hh + 4, frame[2])
    a.box(x0, y0, x0 + w, y0 + hh, "#0b0d12")
    a.box(x0 + 2, y0 + 2, x0 + w - 2, y0 + 3, glow[4])
    a.box(x0 + 2, y0 + hh - 3, x0 + w - 2, y0 + hh - 2, glow[4])
    a.box(x0 + 2, y0 + 2, x0 + 3, y0 + hh - 2, glow[4])
    a.box(x0 + w - 3, y0 + 2, x0 + w - 2, y0 + hh - 2, glow[4])
    for i in range(3):
        yy = y0 + 6 + i * 6
        a.box(x0 + 6, yy, x0 + w * (0.45 + 0.15 * (i % 2)), yy + 2, glow[3])
    a.glow(glow[4], 4, 0.5)


# ---------------------------------------------------------------- registry

COMMON_PARAMS = [
    {"name": "size", "label": "Pixel size", "type": "int", "default": 48, "min": 16, "max": 128, "step": 8},
    {"name": "style", "label": "Style", "type": "select", "default": "classic", "options": ["classic", "pastel", "neon", "mono"]},
    {"name": "palette", "label": "Restrict to palette", "type": "palette", "default": ""},
    {"name": "outline", "label": "Dark outline", "type": "bool", "default": True},
]


def _p(name: str, label: str, typ: str, default: Any, mn: Any = None, mx: Any = None, options: list[str] | None = None) -> dict[str, Any]:
    return {"name": name, "label": label, "type": typ, "default": default, "min": mn, "max": mx, "options": options or []}


GENERATORS: dict[str, dict[str, Any]] = {
    # nature
    "tree": {"group": "nature", "name": "Tree", "fn": gen_tree, "params": [
        _p("height", "Height", "float", 0.8, 0.4, 0.95), _p("width", "Canopy width", "float", 0.72, 0.4, 1.0),
        _p("trunk_width", "Trunk width", "float", 0.1, 0.05, 0.24), _p("canopy", "Canopy", "select", "round", options=["round", "pine", "palm"]),
        _p("branches", "Branches / layers", "int", 5, 2, 9), _p("leaf_density", "Leaf density", "float", 0.6, 0.1, 1.0),
        _p("bark_lines", "Bark detail", "int", 3, 0, 12),
    ]},
    "bush": {"group": "nature", "name": "Bush", "fn": gen_bush, "params": [
        _p("lobes", "Lobes", "int", 4, 2, 7), _p("width", "Width", "float", 0.72, 0.4, 0.95), _p("berries", "Berries", "int", 0, 0, 12),
    ]},
    "flower": {"group": "nature", "name": "Flower", "fn": gen_flower, "params": [
        _p("petals", "Petals", "int", 5, 3, 10), _p("height", "Height", "float", 0.6, 0.3, 0.9),
        _p("petal_size", "Petal size", "float", 0.16, 0.08, 0.3), _p("leaves", "Leaves", "int", 2, 0, 4),
    ]},
    "rock": {"group": "nature", "name": "Rock", "fn": gen_rock, "params": [
        _p("width", "Width", "float", 0.68, 0.3, 0.95), _p("height", "Height", "float", 0.45, 0.25, 0.8),
        _p("vertices", "Facets", "int", 8, 5, 12), _p("cracks", "Cracks", "int", 1, 0, 6),
    ]},
    "grass": {"group": "nature", "name": "Grass tuft", "fn": gen_grass, "params": [
        _p("blades", "Blades", "int", 9, 3, 30),
    ]},
    "mushroom": {"group": "nature", "name": "Mushroom", "fn": gen_mushroom, "params": [
        _p("height", "Stem height", "float", 0.34, 0.2, 0.6), _p("cap_width", "Cap width", "float", 0.66, 0.35, 0.95), _p("spots", "Spots", "int", 4, 0, 10),
    ]},
    "cloud": {"group": "nature", "name": "Cloud", "fn": gen_cloud, "params": [
        _p("puffs", "Puffs", "int", 5, 3, 8), _p("rain", "Rain", "bool", False),
    ]},
    "mountain": {"group": "nature", "name": "Mountain", "fn": gen_mountain, "params": [
        _p("peaks", "Peaks", "int", 2, 1, 4),
    ]},
    "plant": {"group": "nature", "name": "Potted plant", "fn": gen_plant, "params": [
        _p("leaves", "Leaves", "int", 5, 2, 10), _p("pot_width", "Pot width", "float", 0.5, 0.3, 0.8),
    ]},
    # fantasy
    "chest": {"group": "fantasy", "name": "Treasure chest", "fn": gen_chest, "params": [
        _p("width", "Width", "float", 0.68, 0.4, 0.9), _p("height", "Height", "float", 0.5, 0.3, 0.75),
        _p("treasure", "Gold spill", "bool", False),
    ]},
    "barrel": {"group": "fantasy", "name": "Barrel", "fn": gen_barrel, "params": [
        _p("width", "Width", "float", 0.5, 0.3, 0.7), _p("height", "Height", "float", 0.68, 0.4, 0.9), _p("label", "Label", "bool", False),
    ]},
    "crystal": {"group": "fantasy", "name": "Crystal", "fn": gen_crystal, "params": [
        _p("shards", "Shards", "int", 3, 1, 5), _p("glow", "Glow", "bool", True),
    ]},
    "potion": {"group": "fantasy", "name": "Potion", "fn": gen_potion, "params": [
        _p("width", "Bottle width", "float", 0.36, 0.2, 0.6), _p("height", "Bottle height", "float", 0.48, 0.3, 0.7),
        _p("liquid", "Liquid", "select", "fire", options=["fire", "water", "poison", "magic", "neon_pink"]), _p("bubbles", "Bubbles", "bool", True),
    ]},
    "sword": {"group": "fantasy", "name": "Sword", "fn": gen_sword, "params": [
        _p("width", "Blade width", "float", 0.08, 0.04, 0.16),
        _p("grip", "Grip", "select", "cloth", options=["cloth", "wood", "metal", "magic"]),
    ]},
    "shield": {"group": "fantasy", "name": "Shield", "fn": gen_shield, "params": [
        _p("shape", "Shape", "select", "kite", options=["kite", "round", "tower"]),
        _p("metal", "Metal", "select", "gold", options=["gold", "metal", "bronze"]),
        _p("emblem", "Emblem", "select", "cross", options=["cross", "star", "circle"]),
    ]},
    "orb": {"group": "fantasy", "name": "Magic orb", "fn": gen_orb, "params": [
        _p("radius", "Radius", "float", 0.28, 0.2, 0.42), _p("runes", "Runes", "int", 4, 0, 8),
    ]},
    "totem": {"group": "fantasy", "name": "Totem", "fn": gen_totem, "params": [
        _p("blocks", "Blocks", "int", 2, 1, 4),
    ]},
    # environment
    "house": {"group": "environment", "name": "House", "fn": gen_house, "params": [
        _p("roof_type", "Roof", "select", "gable", options=["gable", "flat"]),
        _p("walls", "Walls", "select", "sand", options=["sand", "stone", "wood", "snow"]),
        _p("roof", "Roof color", "select", "fire", options=["fire", "magic", "neon_blue", "leaf"]),
        _p("windows", "Windows", "int", 2, 0, 4), _p("chimney", "Chimney", "bool", True),
    ]},
    "tower": {"group": "environment", "name": "Tower", "fn": gen_tower, "params": [
        _p("spire", "Spire roof", "bool", True), _p("flag", "Flag", "bool", True),
        _p("roof", "Roof color", "select", "neon_blue", options=["neon_blue", "magic", "fire", "leaf"]),
    ]},
    "ruin": {"group": "environment", "name": "Ruins", "fn": gen_ruin, "params": [
        _p("columns", "Columns", "int", 2, 1, 3), _p("rubble", "Rubble", "int", 6, 0, 16), _p("vines", "Vines", "int", 3, 0, 8),
    ]},
    "fence": {"group": "environment", "name": "Fence", "fn": gen_fence, "params": [
        _p("posts", "Posts", "int", 4, 2, 8), _p("height", "Height", "float", 0.42, 0.3, 0.7),
        _p("material", "Material", "select", "wood", options=["wood", "stone", "metal"]),
    ]},
    "bridge": {"group": "environment", "name": "Bridge", "fn": gen_bridge, "params": [
        _p("material", "Material", "select", "wood", options=["wood", "stone"]), _p("ropes", "Ropes", "bool", False),
    ]},
    "door": {"group": "environment", "name": "Door", "fn": gen_door, "params": [
        _p("panels", "Panels", "int", 2, 1, 4), _p("open", "Open", "bool", False), _p("bars", "Iron bars", "bool", False),
    ]},
    "window": {"group": "environment", "name": "Window", "fn": gen_window, "params": [
        _p("lit", "Lit", "bool", False), _p("flower_box", "Flower box", "bool", True),
    ]},
    "platform": {"group": "environment", "name": "Platform", "fn": gen_platform, "params": [
        _p("style", "Style", "select", "grass", options=["grass", "stone", "metal"]), _p("wood", "Wooden body", "bool", False),
    ]},
    # sci-fi
    "computer": {"group": "scifi", "name": "Computer", "fn": gen_computer, "params": [
        _p("lines", "Screen lines", "int", 4, 2, 8), _p("tower", "Tower", "bool", True),
        _p("glow", "Screen glow", "select", "neon_blue", options=["neon_blue", "poison", "neon_pink", "gold"]),
    ]},
    "console": {"group": "scifi", "name": "Console", "fn": gen_console, "params": [
        _p("knobs", "Knobs", "int", 3, 1, 6), _p("glow", "Display glow", "select", "poison", options=["poison", "neon_blue", "neon_pink", "fire"]),
    ]},
    "robot": {"group": "scifi", "name": "Robot", "fn": gen_robot, "params": [
        _p("legs", "Legs", "int", 2, 1, 2),
        _p("accent", "Accent", "select", "neon_blue", options=["neon_blue", "neon_pink", "poison", "gold"]),
    ]},
    "container": {"group": "scifi", "name": "Cargo container", "fn": gen_container, "params": [
        _p("hazard", "Hazard stripes", "bool", True),
        _p("stripe", "Stripe", "select", "fire", options=["fire", "gold", "poison", "neon_pink"]),
    ]},
    "industrial": {"group": "scifi", "name": "Industrial unit", "fn": gen_industrial, "params": [
        _p("glow", "Indicator glow", "bool", True),
        _p("accent", "Accent", "select", "fire", options=["fire", "neon_blue", "poison", "gold"]),
    ]},
    "decoration": {"group": "scifi", "name": "Neon decor", "fn": gen_decoration, "params": [
        _p("mode", "Type", "select", "sign", options=["sign", "pillar"]),
        _p("neon", "Neon", "select", "neon_pink", options=["neon_pink", "neon_blue", "poison", "gold"]),
    ]},
}

GROUP_LABELS = {
    "nature": "Nature",
    "fantasy": "Fantasy",
    "environment": "Environment",
    "scifi": "Sci-Fi",
}


def catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": gid,
            "name": g["name"],
            "group": g["group"],
            "group_label": GROUP_LABELS.get(g["group"], g["group"]),
            "params": COMMON_PARAMS + g["params"],
        }
        for gid, g in GENERATORS.items()
    ]


def _sanitize(spec: dict[str, Any], value: Any) -> Any:
    typ = spec["type"]
    if typ == "int":
        return clamp_int(value, int(spec["min"]), int(spec["max"]), int(spec["default"]))
    if typ == "float":
        return clamp_float(value, float(spec["min"]), float(spec["max"]), float(spec["default"]))
    if typ == "bool":
        return bool(value) if value is not None else bool(spec["default"])
    if typ == "select":
        return value if value in spec.get("options", []) else spec["default"]
    if typ == "palette":
        return str(value or "")
    return value


def generate_asset(
    generator: str,
    params: dict[str, Any] | None = None,
    seed: int = 1337,
) -> tuple[Image.Image, dict[str, Any]]:
    if generator not in GENERATORS:
        raise ValueError(f"Unknown generator: {generator}")
    g = GENERATORS[generator]
    specs = COMMON_PARAMS + g["params"]
    raw = params or {}
    clean: dict[str, Any] = {}
    for spec in specs:
        clean[spec["name"]] = _sanitize(spec, raw.get(spec["name"], spec["default"]))
    size = int(clean["size"])
    art = Art(size, seed, clean["style"], bool(clean["outline"]))
    g["fn"](art, clean)
    img = art.finish()
    pal_id = clean.get("palette")
    if pal_id:
        colors = palette_by_id(pal_id)
        if colors:
            from .pixelart import hex_to_rgb, nearest_palette_map
            arr = np.array(img, dtype=np.uint8, copy=True)
            rgb = arr[..., :3]
            pal = np.array([hex_to_rgb(c) for c in colors], dtype=np.uint8)
            idx = nearest_palette_map(rgb, pal)
            arr[..., :3] = pal[idx]
            img = Image.fromarray(arr, "RGBA")
    info = {
        "generator": generator,
        "name": g["name"],
        "group": g["group"],
        "seed": int(seed),
        "params": clean,
        "width": img.width,
        "height": img.height,
        "palette_id": pal_id or None,
        "colors": int(len(np.unique(np.asarray(img.convert("RGB").resize((min(64, img.width), min(64, img.height)))), axis=0))),
        "deterministic": True,
    }
    return img, info


def generate_variations(
    generator: str,
    params: dict[str, Any] | None,
    seed: int,
    count: int = 4,
    progress: Callable[[int, str], None] | None = None,
) -> list[tuple[Image.Image, dict[str, Any]]]:
    count = clamp_int(count, 1, 12, 4)
    out = []
    for i in range(count):
        img, info = generate_asset(generator, params, seed + i)
        out.append((img, info))
        if progress:
            progress(int(100 * (i + 1) / count), f"Variation {i + 1}/{count}")
    return out
