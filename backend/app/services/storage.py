from __future__ import annotations

import io
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

from ..config import (
    DATA_DIR,
    ID_RE,
    PROJECTS_DIR,
    new_id,
    now,
    project_dir,
    read_json,
    safe_join,
    valid_id,
    write_json,
)
from ..db import db, json_field, rows_to_dicts
from .images import (
    ImageValidationError,
    decode_image,
    ensure_rgba,
    image_to_bytes,
    make_thumbnail_file,
    normalize_mode,
    sha256_bytes,
    thumb,
)

ASSET_KINDS = {
    "source", "pixelart", "sprite", "spritesheet", "tile", "tileset",
    "procedural", "false3d", "frame", "animation", "workspace", "export",
}
BUCKETS = {"assets", "thumbs", "sources", "previews", "exports", "backups"}


class ProjectError(ValueError):
    pass


def project_paths(project_id: str) -> dict[str, Path]:
    base = project_dir(project_id)
    paths = {
        "base": base,
        "assets": base / "assets",
        "thumbs": base / "thumbs",
        "sources": base / "sources",
        "previews": base / "previews",
        "exports": base / "exports",
        "backups": base / "backups",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths


def create_project(
    name: str,
    description: str = "",
    category: str = "General",
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    name = (name or "Untitled project").strip()[:100]
    pid = new_id()
    paths = project_paths(pid)
    ts = now()
    initial_state = state or {
        "workspace": {"width": 512, "height": 512, "layers": []},
        "pixelart": {},
        "tileset": {},
        "false3d": {},
    }
    with db() as conn:
        conn.execute(
            "INSERT INTO projects(id,name,description,category,favorite,state,settings,created_at,updated_at) VALUES(?,?,?,?,0,?,?,?,?)",
            (pid, name, description, category, json.dumps(initial_state), "{}", ts, ts),
        )
    write_project_json(pid)
    return get_project(pid)  # type: ignore[return-value]


def _project_row(pid: str) -> dict[str, Any] | None:
    valid_id(pid)
    with db() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    return dict(row) if row else None


def get_project(pid: str) -> dict[str, Any] | None:
    row = _project_row(pid)
    if not row:
        return None
    out = dict(row)
    out["state"] = json_field(row, "state", {})
    out["settings"] = json_field(row, "settings", {})
    out["favorite"] = bool(row.get("favorite"))
    with db() as conn:
        counts = conn.execute(
            "SELECT kind, COUNT(*) AS n FROM assets WHERE project_id=? GROUP BY kind", (pid,)
        ).fetchall()
        out["asset_counts"] = {c["kind"]: c["n"] for c in counts}
        out["asset_count"] = sum(c["n"] for c in counts)
        out["animation_count"] = conn.execute(
            "SELECT COUNT(*) AS n FROM animations WHERE project_id=?", (pid,)
        ).fetchone()["n"]
        thumb_row = conn.execute(
            "SELECT id, thumb FROM assets WHERE project_id=? AND thumb IS NOT NULL ORDER BY created_at DESC LIMIT 1",
            (pid,),
        ).fetchone()
    out["thumbnail_url"] = (
        f"/api/files/{pid}/thumbs/{thumb_row['thumb']}" if thumb_row and thumb_row["thumb"] else None
    )
    out["size_bytes"] = _dir_size(project_dir(pid))
    return out


def list_projects(search: str = "", category: str = "", favorite: bool | None = None) -> list[dict[str, Any]]:
    query = "SELECT id FROM projects WHERE 1=1"
    params: list[Any] = []
    if search:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    if category:
        query += " AND category=?"
        params.append(category)
    if favorite:
        query += " AND favorite=1"
    query += " ORDER BY updated_at DESC"
    with db() as conn:
        ids = [r["id"] for r in conn.execute(query, params).fetchall()]
    return [p for p in (get_project(i) for i in ids) if p]


def update_project(pid: str, data: dict[str, Any]) -> dict[str, Any]:
    row = _project_row(pid)
    if not row:
        raise ProjectError("Project not found")
    sets: list[str] = []
    params: list[Any] = []
    for field in ("name", "description", "category"):
        if field in data and data[field] is not None:
            value = str(data[field])[:200]
            if field == "name":
                value = value.strip()[:100] or row["name"]
            sets.append(f"{field}=?")
            params.append(value)
    if "favorite" in data:
        sets.append("favorite=?")
        params.append(1 if data["favorite"] else 0)
    if "state" in data and isinstance(data["state"], dict):
        if data.get("replace_state"):
            merged = data["state"]
        else:
            merged = json_field(row, "state", {})
            merged.update(data["state"])
        sets.append("state=?")
        params.append(json.dumps(merged))
    if "settings" in data and isinstance(data["settings"], dict):
        merged_s = json_field(row, "settings", {})
        merged_s.update(data["settings"])
        sets.append("settings=?")
        params.append(json.dumps(merged_s))
    sets.append("updated_at=?")
    params.append(now())
    params.append(pid)
    with db() as conn:
        conn.execute(f"UPDATE projects SET {', '.join(sets)} WHERE id=?", params)
    write_project_json(pid)
    return get_project(pid)  # type: ignore[return-value]


def delete_project(pid: str) -> bool:
    row = _project_row(pid)
    if not row:
        return False
    with db() as conn:
        for table in ("assets", "animations", "backups", "library_tags"):
            conn.execute(f"DELETE FROM {table} WHERE project_id=?", (pid,))
        conn.execute("DELETE FROM projects WHERE id=?", (pid,))
    base = project_dir(pid)
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    return True


def duplicate_project(pid: str) -> dict[str, Any]:
    src = _project_row(pid)
    if not src:
        raise ProjectError("Project not found")
    new_pid = new_id()
    src_dir = project_dir(pid)
    dst_dir = project_dir(new_pid)
    shutil.copytree(src_dir, dst_dir, ignore=shutil.ignore_patterns("backups", "previews"))
    ts = now()
    with db() as conn:
        conn.execute(
            "INSERT INTO projects(id,name,description,category,favorite,thumbnail,state,settings,created_at,updated_at) VALUES(?,?,?,?,0,?,?,?,?,?)",
            (
                new_pid, (src["name"] + " copy")[:100], src["description"], src["category"],
                src.get("thumbnail"), src["state"], src["settings"], ts, ts,
            ),
        )
        assets = conn.execute("SELECT * FROM assets WHERE project_id=?", (pid,)).fetchall()
        asset_map: dict[str, str] = {}
        for a in assets:
            new_aid = new_id()
            asset_map[a["id"]] = new_aid
            conn.execute(
                "INSERT INTO assets(id,project_id,name,kind,filename,thumb,width,height,size_bytes,sha256,tags,favorite,meta,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (new_aid, new_pid, a["name"], a["kind"], a["filename"], a["thumb"], a["width"], a["height"], a["size_bytes"], a["sha256"], a["tags"], a["favorite"], a["meta"], a["created_at"], a["updated_at"]),
            )
        anims = conn.execute("SELECT * FROM animations WHERE project_id=?", (pid,)).fetchall()
        for an in anims:
            frames = json.loads(an["frames"] or "[]")
            new_frames = [asset_map.get(f, "") for f in frames]
            new_frames = [f for f in new_frames if f]
            conn.execute(
                "INSERT INTO animations(id,project_id,name,fps,loop,frames,meta,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (new_id(), new_pid, an["name"], an["fps"], an["loop"], json.dumps(new_frames), an["meta"], ts, ts),
            )
    with db() as conn:
        pal = conn.execute("SELECT * FROM palettes WHERE project_id=?", (pid,)).fetchall()
        for p in pal:
            conn.execute(
                "INSERT INTO palettes(id,name,colors,builtin,project_id,note,created_at) VALUES(?,?,?,0,?,?,?)",
                (new_id(), p["name"], p["colors"], new_pid, p["note"], ts),
            )
    write_project_json(new_pid)
    return get_project(new_pid)  # type: ignore[return-value]


def write_project_json(pid: str) -> Path:
    row = _project_row(pid)
    if not row:
        raise ProjectError("Project not found")
    project_paths(pid)
    with db() as conn:
        assets = rows_to_dicts(conn.execute("SELECT * FROM assets WHERE project_id=? ORDER BY created_at", (pid,)).fetchall())
        animations = rows_to_dicts(conn.execute("SELECT * FROM animations WHERE project_id=?", (pid,)).fetchall())
        palettes = rows_to_dicts(conn.execute("SELECT * FROM palettes WHERE project_id=?", (pid,)).fetchall())
    for a in assets:
        a["meta"] = json_field(a, "meta", {})
        a["favorite"] = bool(a.get("favorite"))
        a["path"] = f"assets/{a['filename']}"
        a["thumb_path"] = f"thumbs/{a['thumb']}" if a.get("thumb") else None
    for an in animations:
        an["frames"] = json.loads(an.get("frames") or "[]")
        an["meta"] = json_field(an, "meta", {})
        an["loop"] = bool(an.get("loop"))
    payload = {
        "format": "pixel-art-studio-project",
        "version": 1,
        "id": pid,
        "name": row["name"],
        "description": row["description"],
        "category": row["category"],
        "favorite": bool(row["favorite"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "state": json_field(row, "state", {}),
        "settings": json_field(row, "settings", {}),
        "assets": assets,
        "palettes": palettes,
        "animations": animations,
        "paths": {
            "sources": "sources/",
            "assets": "assets/",
            "thumbnails": "thumbs/",
            "exports": "exports/",
        },
    }
    path = safe_join(project_dir(pid), "project.json")
    write_json(path, payload)
    return path


def backup_project(pid: str, note: str = "autosave", keep: int = 15) -> dict[str, Any] | None:
    paths = project_paths(pid)
    write_project_json(pid)
    stamp = now().replace(":", "").replace("-", "")
    filename = f"project-{stamp}-{new_id()[:4]}.json"
    src = safe_join(paths["base"], "project.json")
    dst = safe_join(paths["backups"], filename)
    try:
        dst.write_bytes(src.read_bytes())
    except OSError:
        return None
    bid = new_id()
    ts = now()
    with db() as conn:
        conn.execute(
            "INSERT INTO backups(id,project_id,filename,note,created_at) VALUES(?,?,?,?,?)",
            (bid, pid, filename, note, ts),
        )
        old = conn.execute(
            "SELECT id, filename FROM backups WHERE project_id=? ORDER BY created_at DESC LIMIT -1 OFFSET ?",
            (pid, keep),
        ).fetchall()
        for o in old:
            conn.execute("DELETE FROM backups WHERE id=?", (o["id"],))
    for o in old:
        try:
            safe_join(paths["backups"], o["filename"]).unlink(missing_ok=True)
        except Exception:
            pass
    return {"id": bid, "filename": filename, "note": note, "created_at": ts}


def list_backups(pid: str) -> list[dict[str, Any]]:
    valid_id(pid)
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            "SELECT * FROM backups WHERE project_id=? ORDER BY created_at DESC", (pid,)
        ).fetchall())
    return rows


def restore_backup(pid: str, backup_id: str) -> dict[str, Any]:
    paths = project_paths(pid)
    with db() as conn:
        row = conn.execute("SELECT * FROM backups WHERE id=? AND project_id=?", (backup_id, pid)).fetchone()
    if not row:
        raise ProjectError("Backup not found")
    data = read_json(safe_join(paths["backups"], row["filename"]))
    if not data or data.get("format") != "pixel-art-studio-project":
        raise ProjectError("Backup file is invalid")
    update_project(pid, {
        "state": data.get("state", {}),
        "settings": data.get("settings", {}),
        "replace_state": True,
        "name": data.get("name"),
        "description": data.get("description", ""),
        "category": data.get("category", "General"),
    })
    return get_project(pid)  # type: ignore[return-value]


def _dir_size(path: Path) -> int:
    total = 0
    if path.exists():
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    return total


# ---------------------------------------------------------------- assets

def create_asset(
    pid: str,
    name: str,
    kind: str,
    image: Image.Image | None = None,
    meta: dict[str, Any] | None = None,
    tags: str = "",
    fmt: str = "PNG",
    original_bytes: bytes | None = None,
    original_filename: str | None = None,
) -> dict[str, Any]:
    if kind not in ASSET_KINDS:
        raise ValueError(f"Unknown asset kind: {kind}")
    paths = project_paths(pid)
    aid = new_id()
    meta = dict(meta or {})
    if original_filename:
        meta.setdefault("original_filename", original_filename)
    if image is None and original_bytes is None:
        raise ValueError("Asset needs image data")
    if image is None:
        image = decode_image(original_bytes or b"")
    image = normalize_mode(image)
    if original_bytes is not None:
        ext = Path(original_filename or "source.png").suffix.lower()
        if ext not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}:
            ext = ".png"
        try:
            src_path = safe_join(paths["sources"], f"{aid}{ext}")
            src_path.write_bytes(original_bytes)
            meta["source_file"] = f"sources/{src_path.name}"
        except Exception:
            pass
    ext = "png" if fmt.upper() == "PNG" else fmt.lower().replace("jpeg", "jpg")
    filename = f"{aid}.{ext}"
    target = safe_join(paths["assets"], filename)
    if fmt.upper() == "PNG":
        image.save(target, format="PNG", compress_level=6)
    else:
        target.write_bytes(image_to_bytes(image, fmt))
    thumb_name = f"{aid}.png"
    make_thumbnail_file(ensure_rgba(image), str(safe_join(paths["thumbs"], thumb_name)), 320)
    digest = sha256_bytes(target.read_bytes())
    ts = now()
    with db() as conn:
        conn.execute(
            "INSERT INTO assets(id,project_id,name,kind,filename,thumb,width,height,size_bytes,sha256,tags,favorite,meta,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,0,?,?,?)",
            (aid, pid, (name or "Asset")[:120], kind, filename, thumb_name, image.width, image.height, target.stat().st_size, digest, tags, json.dumps(meta), ts, ts),
        )
        conn.execute("UPDATE projects SET updated_at=? WHERE id=?", (ts, pid))
    with db() as conn:
        for tag in [t.strip() for t in tags.split(",") if t.strip()]:
            conn.execute("INSERT OR IGNORE INTO library_tags(project_id,asset_id,tag) VALUES(?,?,?)", (pid, aid, tag))
    return get_asset(aid)  # type: ignore[return-value]


def get_asset(aid: str) -> dict[str, Any] | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM assets WHERE id=?", (aid,)).fetchone()
    if not row:
        return None
    return serialize_asset(dict(row))


def serialize_asset(row: dict[str, Any]) -> dict[str, Any]:
    pid = row["project_id"]
    meta = json_field(row, "meta", {})
    out = dict(row)
    out["meta"] = meta
    out["favorite"] = bool(row.get("favorite"))
    out["tags"] = [t for t in (row.get("tags") or "").split(",") if t]
    out["size_bytes"] = row.get("size_bytes") or 0
    out["url"] = f"/api/files/{pid}/assets/{row['filename']}"
    out["thumb_url"] = f"/api/files/{pid}/thumbs/{row['thumb']}" if row.get("thumb") else None
    out["download_url"] = f"/api/assets/{row['id']}/download"
    out["src_url"] = (
        f"/api/files/{pid}/{meta['source_file']}" if meta.get("source_file") else None
    )
    return out


def list_assets(
    pid: str,
    kind: str | None = None,
    search: str = "",
    favorite: bool | None = None,
    tag: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    valid_id(pid)
    q = "SELECT * FROM assets WHERE project_id=?"
    params: list[Any] = [pid]
    if kind and kind != "all":
        kinds = [k.strip() for k in kind.split(",") if k.strip()]
        q += f" AND kind IN ({','.join('?' * len(kinds))})"
        params += kinds
    if search:
        q += " AND (name LIKE ? OR tags LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    if favorite:
        q += " AND favorite=1"
    if tag:
        q += " AND (',' || tags || ',') LIKE ?"
        params.append(f"%,{tag},%")
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(max(1, min(limit, 2000)))
    with db() as conn:
        rows = rows_to_dicts(conn.execute(q, params).fetchall())
    return [serialize_asset(r) for r in rows]


def update_asset(aid: str, data: dict[str, Any]) -> dict[str, Any] | None:
    row = get_asset(aid)
    if not row:
        return None
    sets: list[str] = []
    params: list[Any] = []
    if "name" in data:
        sets.append("name=?")
        params.append(str(data["name"])[:120] or row["name"])
    if "tags" in data:
        tags = data["tags"]
        if isinstance(tags, list):
            tags = ",".join(str(t).strip() for t in tags if str(t).strip())
        sets.append("tags=?")
        params.append(str(tags)[:500])
    if "favorite" in data:
        sets.append("favorite=?")
        params.append(1 if data["favorite"] else 0)
    if "meta" in data and isinstance(data["meta"], dict):
        merged = row["meta"]
        merged.update(data["meta"])
        sets.append("meta=?")
        params.append(json.dumps(merged))
    if not sets:
        return row
    sets.append("updated_at=?")
    params.append(now())
    params.append(aid)
    with db() as conn:
        conn.execute(f"UPDATE assets SET {', '.join(sets)} WHERE id=?", params)
        conn.execute("DELETE FROM library_tags WHERE asset_id=?", (aid,))
        tags_val = data.get("tags") or row.get("tags") or ""
        if isinstance(tags_val, list):
            tags_val = ",".join(tags_val)
        for tag in [t.strip() for t in str(tags_val).split(",") if t.strip()]:
            conn.execute(
                "INSERT OR IGNORE INTO library_tags(project_id,asset_id,tag) VALUES(?,?,?)",
                (row["project_id"], aid, tag),
            )
    return get_asset(aid)


def delete_asset(aid: str) -> bool:
    row = get_asset(aid)
    if not row:
        return False
    pid = row["project_id"]
    paths = project_paths(pid)
    for bucket, key in (("assets", "filename"), ("thumbs", "thumb")):
        name = row.get(key)
        if name:
            try:
                safe_join(paths[bucket], name).unlink(missing_ok=True)
            except Exception:
                pass
    src = row["meta"].get("source_file")
    if src:
        try:
            safe_join(paths["base"], src).unlink(missing_ok=True)
        except Exception:
            pass
    with db() as conn:
        conn.execute("DELETE FROM assets WHERE id=?", (aid,))
        conn.execute("DELETE FROM library_tags WHERE asset_id=?", (aid,))
    return True


def asset_file(pid: str, bucket: str, filename: str) -> Path:
    if bucket not in BUCKETS:
        raise ProjectError("Invalid bucket")
    paths = project_paths(pid)
    path = safe_join(paths[bucket], filename)
    if not path.is_file():
        raise ProjectError("File not found")
    return path


def save_preview(pid: str, img: Image.Image, key: str) -> str:
    paths = project_paths(pid)
    import hashlib

    name = hashlib.sha256(key.encode()).hexdigest()[:24] + ".png"
    target = safe_join(paths["previews"], name)
    image = ensure_rgba(img)
    image.save(target, format="PNG", compress_level=4)
    files = sorted(paths["previews"].glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[800:]:
        old.unlink(missing_ok=True)
    return f"/api/files/{pid}/previews/{name}?v={int(target.stat().st_mtime)}"


def save_bytes_asset(
    pid: str, name: str, kind: str, data: bytes, ext: str, meta: dict[str, Any] | None = None, tags: str = ""
) -> dict[str, Any]:
    paths = project_paths(pid)
    aid = new_id()
    ext = ext.lower().lstrip(".")
    filename = f"{aid}.{ext}"
    target = safe_join(paths["assets"], filename)
    target.write_bytes(data)
    thumb_name = f"{aid}.png"
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            make_thumbnail_file(ensure_rgba(im), str(safe_join(paths["thumbs"], thumb_name)), 320)
            w, h = im.size
    except Exception:
        w, h = 0, 0
        thumb_name = ""
    ts = now()
    with db() as conn:
        conn.execute(
            "INSERT INTO assets(id,project_id,name,kind,filename,thumb,width,height,size_bytes,sha256,tags,favorite,meta,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,0,?,?,?)",
            (aid, pid, name[:120], kind, filename, thumb_name or None, w, h, len(data), sha256_bytes(data), tags, json.dumps(meta or {}), ts, ts),
        )
        conn.execute("UPDATE projects SET updated_at=? WHERE id=?", (ts, pid))
    return get_asset(aid)  # type: ignore[return-value]


def data_usage() -> dict[str, Any]:
    projects = 0
    for p in PROJECTS_DIR.glob("*"):
        if p.is_dir():
            projects += 1
    return {
        "data_dir": str(DATA_DIR),
        "projects": projects,
        "total_bytes": _dir_size(DATA_DIR),
        "cache_bytes": _dir_size(DATA_DIR / "cache"),
        "tmp_bytes": _dir_size(DATA_DIR / "tmp"),
    }


def cleanup_temp(older_than_seconds: int = 3600) -> int:
    import time

    removed = 0
    cutoff = time.time() - older_than_seconds
    for folder in (DATA_DIR / "tmp", DATA_DIR / "cache"):
        if not folder.exists():
            continue
        for p in folder.glob("*"):
            try:
                if p.is_file() and p.stat().st_mtime < cutoff:
                    p.unlink()
                    removed += 1
                elif p.is_dir() and p.stat().st_mtime < cutoff:
                    shutil.rmtree(p, ignore_errors=True)
                    removed += 1
            except OSError:
                pass
    return removed


def get_animations(pid: str) -> list[dict[str, Any]]:
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            "SELECT * FROM animations WHERE project_id=? ORDER BY created_at", (pid,)
        ).fetchall())
    for r in rows:
        r["frames"] = json.loads(r.get("frames") or "[]")
        r["meta"] = json_field(r, "meta", {})
        r["loop"] = bool(r.get("loop"))
    return rows
