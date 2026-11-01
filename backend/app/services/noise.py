"""Deterministic CPU noise utilities (Perlin, simplex, value noise, FFT textures).

All functions accept an explicit seed so generated assets are reproducible.
"""
from __future__ import annotations

import numpy as np

_F2 = 0.5 * (np.sqrt(3.0) - 1.0)
_G2 = (3.0 - np.sqrt(3.0)) / 6.0
_GRAD2 = np.array([[1, 1], [-1, 1], [1, -1], [-1, -1], [1, 0], [-1, 0], [0, 1], [0, -1]], dtype=np.float32)


def _perm(seed: int) -> np.ndarray:
    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    p = rng.permutation(256).astype(np.int32)
    return np.concatenate([p, p])


def value_noise(width: int, height: int, scale: float = 8.0, seed: int = 0, octaves: int = 1, persistence: float = 0.5) -> np.ndarray:
    """Smooth value noise in [0,1], deterministic."""
    rng = np.random.default_rng(seed)
    total = np.zeros((height, width), dtype=np.float32)
    amp = 1.0
    norm = 0.0
    freq = max(1.0, scale)
    for _ in range(max(1, octaves)):
        gw = max(2, int(np.ceil(width / freq)) + 2)
        gh = max(2, int(np.ceil(height / freq)) + 2)
        grid = rng.random((gh, gw), dtype=np.float32)
        gx = np.arange(width, dtype=np.float32) / freq
        gy = np.arange(height, dtype=np.float32) / freq
        x0 = np.floor(gx).astype(int)
        y0 = np.floor(gy).astype(int)
        fx = gx - x0
        fy = gy - y0
        fx = fx * fx * (3 - 2 * fx)
        fy = fy * fy * (3 - 2 * fy)
        g00 = grid[np.ix_(y0, x0)]
        g10 = grid[np.ix_(y0, x0 + 1)]
        g01 = grid[np.ix_(y0 + 1, x0)]
        g11 = grid[np.ix_(y0 + 1, x0 + 1)]
        top = g00 + (g10 - g00) * fx[None, :]
        bot = g01 + (g11 - g01) * fx[None, :]
        total += (top + (bot - top) * fy[:, None]) * amp
        norm += amp
        amp *= persistence
        freq = max(1.0, freq / 2)
    return np.clip(total / max(norm, 1e-6), 0, 1)


def perlin(width: int, height: int, scale: float = 8.0, seed: int = 0, octaves: int = 3, persistence: float = 0.5) -> np.ndarray:
    p = _perm(seed)
    total = np.zeros((height, width), dtype=np.float32)
    amp, norm, freq = 1.0, 0.0, max(1.0, scale)
    for _ in range(max(1, octaves)):
        gx = (np.arange(width, dtype=np.float32) + 0.5) / freq
        gy = (np.arange(height, dtype=np.float32) + 0.5) / freq
        x0 = np.floor(gx).astype(np.int32)
        y0 = np.floor(gy).astype(np.int32)
        fx = gx - x0
        fy = gy - y0
        xi = x0 & 255
        yi = y0 & 255
        xf = fx - np.floor(fx)
        yf = fy - np.floor(fy)
        u = xf * xf * xf * (xf * (xf * 6 - 15) + 10)
        v = yf * yf * yf * (yf * (yf * 6 - 15) + 10)
        aa = p[p[xi] + yi]
        ab = p[p[xi] + yi + 1]
        ba = p[p[xi + 1] + yi]
        bb = p[p[xi + 1] + yi + 1]
        g = _GRAD2

        def dot(hsh: np.ndarray, dx: np.ndarray, dy: np.ndarray) -> np.ndarray:
            gg = g[hsh % 8]
            return gg[..., 0] * dx + gg[..., 1] * dy

        n00 = dot(aa, xf[None, :], yf[:, None])
        n10 = dot(ba, xf[None, :] - 1.0, yf[:, None])
        n01 = dot(ab, xf[None, :], yf[:, None] - 1.0)
        n11 = dot(bb, xf[None, :] - 1.0, yf[:, None] - 1.0)
        nx0 = n00 + (n10 - n00) * u[None, :]
        nx1 = n01 + (n11 - n01) * u[None, :]
        total += (nx0 + (nx1 - nx0) * v[:, None]) * amp
        norm += amp
        amp *= persistence
        freq = max(1.0, freq / 2)
    out = total / max(norm, 1e-6)
    return np.clip((out + 1.0) * 0.5, 0, 1)


def simplex(width: int, height: int, scale: float = 8.0, seed: int = 0, octaves: int = 3, persistence: float = 0.5) -> np.ndarray:
    p = _perm(seed)
    total = np.zeros((height, width), dtype=np.float32)
    amp, norm, freq = 1.0, 0.0, max(1.0, scale)
    for _ in range(max(1, octaves)):
        x = (np.arange(width, dtype=np.float32) + 0.5) / freq
        y = (np.arange(height, dtype=np.float32) + 0.5) / freq
        xx, yy = np.meshgrid(x, y)
        s = (xx + yy) * _F2
        i = np.floor(xx + s)
        j = np.floor(yy + s)
        t = (i + j) * _G2
        x0 = xx - (i - t)
        y0 = yy - (j - t)
        i1 = (x0 > y0).astype(np.float32)
        j1 = 1.0 - i1
        x1 = x0 - i1 + _G2
        y1 = y0 - j1 + _G2
        x2 = x0 - 1.0 + 2.0 * _G2
        y2 = y0 - 1.0 + 2.0 * _G2
        ii = (i.astype(np.int32) & 255)
        jj = (j.astype(np.int32) & 255)
        gi0 = p[ii + p[jj]] % 8
        gi1 = p[ii + np.int32(i1) + p[jj + np.int32(j1)]] % 8
        gi2 = p[ii + 1 + p[jj + 1]] % 8
        g = _GRAD2

        def contrib(xv, yv, gi):
            gg = g[gi]
            return gg[..., 0] * xv + gg[..., 1] * yv

        t0 = 0.5 - x0 * x0 - y0 * y0
        t1 = 0.5 - x1 * x1 - y1 * y1
        t2 = 0.5 - x2 * x2 - y2 * y2
        n = np.zeros_like(xx)
        for tv, xv, yv, gi in ((t0, x0, y0, gi0), (t1, x1, y1, gi1), (t2, x2, y2, gi2)):
            tt = np.maximum(tv, 0.0)
            n += tt * tt * tt * tt * contrib(xv, yv, gi)
        total += n * 70.0 * amp
        norm += amp
        amp *= persistence
        freq = max(1.0, freq / 2)
    out = total / max(norm, 1e-6)
    return np.clip((out + 1.0) * 0.5, 0, 1)


def fbm_spectral(width: int, height: int, seed: int = 0, beta: float = 2.2) -> np.ndarray:
    """Seamless fractal noise via 1/f^beta spectral synthesis (periodic by construction)."""
    rng = np.random.default_rng(seed)
    white = rng.standard_normal((height, width)).astype(np.float32)
    fy = np.fft.fftfreq(height)[:, None]
    fx = np.fft.fftfreq(width)[None, :]
    radius = np.sqrt(fx * fx + fy * fy)
    radius[0, 0] = 1.0
    spectrum = np.fft.fft2(white) * (radius ** (-beta / 2.0))
    spectrum[0, 0] = 0
    out = np.real(np.fft.ifft2(spectrum)).astype(np.float32)
    out -= out.min()
    if out.max() > 0:
        out /= out.max()
    return out


def cellular(width: int, height: int, seed: int = 0, fill: float = 0.46, iterations: int = 4, birth: int = 5, survive: int = 4) -> np.ndarray:
    """Cellular automata cave/organic mask (toroidal neighborhood)."""
    rng = np.random.default_rng(seed)
    grid = (rng.random((height, width)) < fill).astype(np.uint8)
    for _ in range(max(0, iterations)):
        padded = np.pad(grid, 1, mode="wrap")
        neighbors = sum(
            padded[dy:dy + height, dx:dx + width]
            for dy in range(3)
            for dx in range(3)
        ) - grid
        grid = ((neighbors >= birth) | ((grid == 1) & (neighbors >= survive))).astype(np.uint8)
    return grid


def ramp_color(t: np.ndarray, stops: list[str]) -> np.ndarray:
    """Map a [0,1] array to RGB using a hex color ramp."""
    from PIL import ImageColor

    cols = np.array([ImageColor.getrgb(c) for c in stops], dtype=np.float32)
    t = np.clip(t, 0, 1) * (len(cols) - 1)
    i0 = np.floor(t).astype(np.int32)
    i1 = np.minimum(i0 + 1, len(cols) - 1)
    f = (t - i0)[..., None]
    return (cols[i0] * (1 - f) + cols[i1] * f).astype(np.uint8)
