"""Centralized export: image formats, spritesheet metadata, engine presets, ZIP."""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from typing import Any

import numpy as np
from PIL import Image

from .images import ensure_rgba, image_to_bytes
from .tileset import tileset_metadata_godot

SUPPORTED_FORMATS = {"png", "jpeg", "jpg", "bmp", "gif", "webp"}
PRESETS = {
    "generic": {"name": "Generic 2D engine", "folder": "assets", "naming": "{project}/{kind}/{name}"},
    "generic_sheet": {"name": "Generic spritesheet", "folder": "spritesheets", "naming": "{project}/{name}"},
    "godot": {"name": "Godot 4", "folder": "godot", "naming": "{project}/{kind}/{name}"},
    "unity": {"name": "Unity", "folder": "unity", "naming": "{project}/Sprites/{name}"},
    "rpgmaker": {"name": "RPG Maker", "folder": "rpgmaker", "naming": "{project}/img/{kind}/{name}"},
}


def slug(value: str) -> str:
    v = re.sub(r"[^a-zA-Z0-9 _-]+", "", value or "").strip().replace(" ", "_")
    return v or "asset"


def convert_image(img: Image.Image, fmt: str) -> bytes:
    fmt = fmt.lower()
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: {fmt}")
    pil_fmt = "JPEG" if fmt in {"jpg", "jpeg"} else fmt.upper()
    if pil_fmt == "GIF":
        rgba = ensure_rgba(img)
        p = rgba.convert("P", palette=Image.Palette.ADAPTIVE, colors=255)
        alpha = rgba.getchannel("A")
        mask = alpha.point(lambda v: 255 if v < 128 else 0)
        p.paste(255, mask=mask)
        buf = io.BytesIO()
        p.save(buf, format="GIF", transparency=255)
        return buf.getvalue()
    return image_to_bytes(img, pil_fmt)


def _godot_spriteframes(asset: dict[str, Any], texture_name: str) -> str:
    meta = asset.get("meta") or {}
    frames = (meta.get("sheet") or meta).get("frames") or {}
    rects = []
    for i, (name, data) in enumerate(frames.items()):
        fr = data.get("frame", data)
        rects.append((name, fr.get("x", 0), fr.get("y", 0), fr.get("w", 0), fr.get("h", 0)))
    lines = [
        '[gd_resource type="SpriteFrames" load_steps=%d format=3]' % (len(rects) + 2),
        "",
        f'[ext_resource type="Texture2D" path="res://{texture_name}" id="1_tex"]',
        "",
    ]
    for i, (name, x, y, w, h) in enumerate(rects):
        lines += [
            f'[sub_resource type="AtlasTexture" id="AtlasTexture_{i}"]',
            'atlas = ExtResource("1_tex")',
            f"region = Rect2({x}, {y}, {w}, {h})",
            "",
        ]
    anim_name = slug(str(asset.get("name", "default"))).lower()
    lines.append("[resource]")
    lines.append("animations = [{")
    lines.append(f'"frames": [')
    for i in range(len(rects)):
        lines.append(f'{{"duration": 1.0, "texture": SubResource("AtlasTexture_{i}")}},')
    lines.append('],')
    lines.append(f'"loop": true,')
    lines.append(f'"name": &"{anim_name}",')
    lines.append(f'"speed": {float(meta.get("fps", 8)):.1f}')
    lines.append("}]")
    return "\n".join(lines) + "\n"


def _unity_meta(asset: dict[str, Any], texture_guid_seed: str) -> str:
    meta = asset.get("meta") or {}
    sheet = meta.get("sheet") or meta
    frames = sheet.get("frames") or {}
    total_h = (sheet.get("size") or {}).get("h") or 0
    rects = []
    for name, data in frames.items():
        fr = data.get("frame", data)
        y = fr.get("y", 0)
        h = fr.get("h", 0)
        unity_y = total_h - y - h if total_h else y
        rects.append((name, fr.get("x", 0), unity_y, fr.get("w", 0), fr.get("h", 0)))
    sprite_entries = "\n".join(
        f"""  - serializedVersion: 2
    name: {slug(name)}
    rect:
      serializedVersion: 2
      x: {int(x)}
      y: {int(y)}
      width: {int(w)}
      height: {int(h)}
    alignment: 0
    pivot: {{x: 0.5, y: 0.5}}
    border: {{x: 0, y: 0, z: 0, w: 0}}
    spriteID: 5e97eb03825dee720800000000000000
    internalID: 0
    vertices: []
    indices: 
    edges: []
    weights: []"""
        for name, x, y, w, h in rects
    )
    return f"""fileFormatVersion: 2
guid: {texture_guid_seed}
TextureImporter:
  internalIDToNameTable: []
  externalObjects: {{}}
  serializedVersion: 12
  mipmaps:
    mipMapMode: 0
    enableMipMap: 0
  isReadable: 0
  sRGBTexture: 1
  alphaIsTransparency: 1
  textureType: 8
  spriteMode: 2
  spriteExtrude: 1
  spriteBorder: {{x: 0, y: 0, z: 0, w: 0}}
  spritePixelsToUnits: 100
  spriteSheet:
    serializedVersion: 2
    sprites:
{sprite_entries}
  spritePackingTag: 
  userData: 
"""


def build_zip(
    project_name: str,
    assets: list[dict[str, Any]],
    images: dict[str, Image.Image],
    preset: str = "generic",
    fmt: str = "png",
    naming: str | None = None,
    include_catalog: bool = True,
) -> tuple[bytes, dict[str, Any]]:
    if preset not in PRESETS:
        preset = "generic"
    cfg = PRESETS[preset]
    naming = naming or cfg["naming"]
    fmt = fmt.lower()
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported export format: {fmt}")
    buf = io.BytesIO()
    manifest: list[dict[str, Any]] = []
    rows: list[list[Any]] = []
    used_names: set[str] = set()
    extension = "jpg" if fmt in {"jpeg", "jpg"} else fmt
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, asset in enumerate(assets):
            aid = asset["id"]
            img = images.get(aid)
            if img is None:
                continue
            base = naming.format(
                project=slug(project_name),
                kind=slug(asset.get("kind", "asset")),
                name=slug(asset.get("name", f"asset_{idx}"))[:60],
                index=idx + 1,
            ).replace("//", "/").strip("/")
            name = f"{base}.{extension}"
            if name.lower() in used_names:
                name = f"{base}_{idx + 1}.{extension}"
            used_names.add(name.lower())
            directory = f"{cfg['folder']}/"
            arc = directory + name if not name.startswith(directory) else name
            try:
                data = convert_image(img, fmt)
            except Exception:
                continue
            zf.writestr(arc, data)
            meta = asset.get("meta") or {}
            sheet = meta.get("sheet") or meta
            entry = {
                "id": asset["id"],
                "name": asset.get("name"),
                "kind": asset.get("kind"),
                "file": arc,
                "width": img.width,
                "height": img.height,
                "tags": asset.get("tags") or [],
                "frames": sheet.get("frames") if isinstance(sheet, dict) else None,
                "fps": meta.get("fps"),
                "tileset": meta.get("autotile"),
            }
            manifest.append(entry)
            rows.append([
                asset["id"], asset.get("name", ""), asset.get("kind", ""), img.width, img.height,
                arc, ",".join(asset.get("tags") or []), asset.get("created_at", ""),
            ])
            if preset == "godot" and entry.get("frames"):
                zf.writestr(arc.rsplit("/", 1)[0] + "/" + slug(asset.get("name", "sprite")) + ".tres", _godot_spriteframes(asset, name))
            if preset == "godot" and entry.get("tileset"):
                zf.writestr(arc.rsplit("/", 1)[0] + "/tileset.tres", tileset_metadata_godot({**(asset.get("meta") or {}), **meta}))
            if preset == "unity" and entry.get("frames"):
                guid = f"{abs(hash(asset['id'])) % (10**32):032x}"[:32]
                zf.writestr(arc + ".meta", _unity_meta(asset, guid))
        if include_catalog:
            zf.writestr(f"{cfg['folder']}/manifest.json", json.dumps({
                "app": "Pixel Art & Game Asset Studio",
                "preset": preset,
                "project": project_name,
                "format": fmt,
                "assets": manifest,
            }, indent=2, ensure_ascii=False))
            sbuf = io.StringIO()
            writer = csv.writer(sbuf, lineterminator="\n")
            writer.writerow(["id", "name", "kind", "width", "height", "file", "tags", "created_at"])
            writer.writerows(rows)
            zf.writestr(f"{cfg['folder']}/catalog.csv", sbuf.getvalue())
            zf.writestr(f"{cfg['folder']}/README.txt", _readme(preset, cfg))
    info = {"preset": preset, "format": fmt, "count": len(manifest), "bytes": len(buf.getvalue())}
    return buf.getvalue(), info


def _readme(preset: str, cfg: dict[str, Any]) -> str:
    return f"""Pixel Art & Game Asset Studio export
Preset: {cfg['name']} ({preset})
Generated locally, offline.

Contents
--------
{cfg['folder']}/...   exported images
manifest.json         machine-readable metadata (frames, tilesets, tags)
catalog.csv           spreadsheet-friendly asset catalog

Notes
-----
- PNG/WebP exports preserve alpha. JPEG/BMP cannot store transparency and are
  flattened onto black.
- Dimensions and palette values are never rescaled silently during export.
- Godot presets include SpriteFrames .tres and TileSet .tres helpers.
- Unity presets include .meta sprite-sheet slice definitions.
"""


def export_single_zip(img: Image.Image, name: str, fmt: str = "png") -> tuple[bytes, str]:
    data = convert_image(img, fmt)
    buf = io.BytesIO()
    ext = "jpg" if fmt in {"jpeg", "jpg"} else fmt
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{slug(name)}.{ext}", data)
    return buf.getvalue(), f"{slug(name)}.{ext}"
