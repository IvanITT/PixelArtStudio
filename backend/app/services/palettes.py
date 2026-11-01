"""Built-in palettes.

These are original implementations/approximations inspired by classic hardware
and community palettes. Names referencing consoles or software are used
descriptively; all trademarks belong to their respective owners. No affiliation
is implied and no copyrighted asset data is bundled. Every palette is a plain
list of hex colors editable or replaceable by the user.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from ..config import new_id, now
from ..db import db

BUILTIN_PALETTES: list[dict[str, Any]] = [
    {
        "id": "gameboy",
        "name": "Game Boy (4)",
        "colors": ["#0f380f", "#306230", "#8bac0f", "#9bbc0f"],
        "note": "Four-green DMG-inspired screen palette. Trademark: Nintendo.",
    },
    {
        "id": "nes",
        "name": "NES-inspired (16)",
        "colors": [
            "#000000", "#7c7c7c", "#bcbcbc", "#f8f8f8",
            "#0000fc", "#0078f8", "#3cbcfc", "#a4e4fc",
            "#940084", "#d800cc", "#f878f8", "#f8b8f8",
            "#a80020", "#f83800", "#f87858", "#fca044",
        ],
        "note": "Approximation of NES-era hues; not an official palette dump.",
    },
    {
        "id": "c64",
        "name": "C64-inspired (16)",
        "colors": [
            "#000000", "#ffffff", "#880000", "#aaffee",
            "#cc44cc", "#00cc55", "#0000aa", "#eeee77",
            "#dd8855", "#664400", "#ff7777", "#333333",
            "#777777", "#aaff66", "#0088ff", "#bbbbbb",
        ],
        "note": "VIC-II-inspired colors. Trademark: Commodore/Cloanto.",
    },
    {
        "id": "cga",
        "name": "CGA-inspired (16)",
        "colors": [
            "#000000", "#0000aa", "#00aa00", "#00aaaa",
            "#aa0000", "#aa00aa", "#aa5500", "#aaaaaa",
            "#555555", "#5555ff", "#55ff55", "#55ffff",
            "#ff5555", "#ff55ff", "#ffff55", "#ffffff",
        ],
        "note": "IBM CGA 16-color hardware palette approximation.",
    },
    {
        "id": "pico8",
        "name": "PICO-8-inspired (16)",
        "colors": [
            "#000000", "#1d2b53", "#7e2553", "#008751",
            "#ab5236", "#5f574f", "#c2c3c7", "#fff1e8",
            "#ff004d", "#ffa300", "#ffec27", "#00e436",
            "#29adff", "#83769c", "#ff77a8", "#ffccaa",
        ],
        "note": "Well-known fantasy-console palette approximation. Trademark: Lexaloffle.",
    },
    {
        "id": "grayscale",
        "name": "Grayscale (8)",
        "colors": ["#000000", "#242424", "#484848", "#6d6d6d", "#919191", "#b6b6b6", "#dadada", "#ffffff"],
        "note": "Neutral 8-step ramp, public domain.",
    },
    {
        "id": "retro_fantasy",
        "name": "Retro Fantasy (24)",
        "colors": [
            "#140c1c", "#442434", "#30346d", "#4e4a4e", "#854c30", "#346524", "#d04648", "#757161",
            "#597dce", "#d27d2c", "#8595a1", "#6daa2c", "#d2aa99", "#6dc2ca", "#dad45e", "#deeed6",
            "#2b1b2e", "#5b3a4a", "#7a4b2a", "#a86b35", "#3e6b2f", "#7fb069", "#5c6f9e", "#c9d6df",
        ],
        "note": "Original earthy fantasy ramp created for this studio.",
    },
    {
        "id": "cyberpunk",
        "name": "Cyberpunk (24)",
        "colors": [
            "#050510", "#0d1030", "#141a4a", "#1b2a6b", "#233b8f", "#2d55b3", "#3a76d6", "#5aa3ff",
            "#ff2a6d", "#ff5e9c", "#ff9ad5", "#b026ff", "#7a2bff", "#4d1a99", "#00f0ff", "#14c8d6",
            "#0a8a99", "#f9f871", "#ffd166", "#ef476f", "#06d6a0", "#118ab2", "#073b4c", "#e8f1f2",
        ],
        "note": "Original neon-noir ramp created for this studio.",
    },
    {
        "id": "pastel",
        "name": "Pastel Soft (16)",
        "colors": [
            "#2d2a3e", "#4f4a6b", "#7d7599", "#b8b0cc", "#f2e9f5", "#ffd6e0", "#ffb3c6", "#ff8fab",
            "#ffc09f", "#ffe5b4", "#b8e0d2", "#95d5b2", "#74c69d", "#a0c4ff", "#bdb2ff", "#cdb4db",
        ],
        "note": "Original pastel ramp created for this studio.",
    },
]


def seed_builtin_palettes() -> None:
    with db() as conn:
        for p in BUILTIN_PALETTES:
            conn.execute(
                "INSERT OR IGNORE INTO palettes(id,name,colors,builtin,project_id,note,created_at) VALUES(?,?,?,1,NULL,?,?)",
                (p["id"], p["name"], ",".join(p["colors"]), p["note"], now()),
            )


def palette_by_id(palette_id: str) -> list[str] | None:
    if not palette_id:
        return None
    builtin = next((p for p in BUILTIN_PALETTES if p["id"] == palette_id), None)
    if builtin is not None:
        return list(builtin["colors"])
    try:
        with db() as conn:
            row = conn.execute("SELECT colors FROM palettes WHERE id=?", (palette_id,)).fetchone()
    except sqlite3.Error:
        return None
    if not row:
        return None
    return [c for c in row["colors"].split(",") if c]


def list_palettes(project_id: str | None = None) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM palettes WHERE builtin=1 OR project_id IS NULL OR project_id=? ORDER BY builtin DESC, name",
            (project_id,),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "colors": r["colors"].split(","),
            "builtin": bool(r["builtin"]),
            "project_id": r["project_id"],
            "note": r["note"],
        }
        for r in rows
    ]


def save_palette(name: str, colors: list[str], project_id: str | None, note: str = "") -> dict[str, Any]:
    pid = new_id()
    colors = [normalize_hex(c) for c in colors if normalize_hex(c)]
    if not colors:
        raise ValueError("Palette must contain at least one color")
    with db() as conn:
        conn.execute(
            "INSERT INTO palettes(id,name,colors,builtin,project_id,note,created_at) VALUES(?,?,?,0,?,?,?)",
            (pid, name.strip()[:80] or "Custom palette", ",".join(colors[:256]), project_id, note, now()),
        )
    return {"id": pid, "name": name, "colors": colors, "builtin": False, "project_id": project_id, "note": note}


def delete_palette(palette_id: str) -> bool:
    with db() as conn:
        cur = conn.execute("DELETE FROM palettes WHERE id=? AND builtin=0", (palette_id,))
        return cur.rowcount > 0


def normalize_hex(value: str) -> str | None:
    v = (value or "").strip()
    if not v:
        return None
    if not v.startswith("#"):
        v = "#" + v
    if len(v) == 4:
        v = "#" + "".join(ch * 2 for ch in v[1:])
    if len(v) != 7:
        return None
    try:
        int(v[1:], 16)
    except ValueError:
        return None
    return v.lower()
