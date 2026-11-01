from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from .config import DB_PATH, DEFAULT_SETTINGS, ensure_dirs, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT DEFAULT '',
  category TEXT DEFAULT 'General',
  favorite INTEGER DEFAULT 0,
  thumbnail TEXT,
  state TEXT DEFAULT '{}',
  settings TEXT DEFAULT '{}',
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  filename TEXT NOT NULL,
  thumb TEXT,
  width INTEGER,
  height INTEGER,
  size_bytes INTEGER DEFAULT 0,
  sha256 TEXT,
  tags TEXT DEFAULT '',
  favorite INTEGER DEFAULT 0,
  meta TEXT DEFAULT '{}',
  created_at TEXT,
  updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id, kind);
CREATE INDEX IF NOT EXISTS idx_assets_sha ON assets(sha256);
CREATE TABLE IF NOT EXISTS palettes (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  colors TEXT NOT NULL,
  builtin INTEGER DEFAULT 0,
  project_id TEXT,
  note TEXT DEFAULT '',
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS animations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  fps INTEGER DEFAULT 8,
  loop INTEGER DEFAULT 1,
  frames TEXT DEFAULT '[]',
  meta TEXT DEFAULT '{}',
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  status TEXT DEFAULT 'queued',
  progress INTEGER DEFAULT 0,
  message TEXT DEFAULT '',
  result TEXT,
  error TEXT,
  project_id TEXT,
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS benchmarks (
  id TEXT PRIMARY KEY,
  module TEXT NOT NULL,
  metrics TEXT NOT NULL,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS backups (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  filename TEXT NOT NULL,
  note TEXT DEFAULT '',
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS library_tags (
  project_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  tag TEXT NOT NULL,
  PRIMARY KEY (project_id, asset_id, tag)
);
"""


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def json_field(row: dict[str, Any], key: str, default: Any = None) -> dict[str, Any]:
    raw = row.get(key)
    if not raw:
        return default if default is not None else {}
    try:
        return json.loads(raw)
    except Exception:
        return default if default is not None else {}


def init_db() -> None:
    ensure_dirs()
    with db() as conn:
        conn.executescript(SCHEMA)
        for k, v in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES(?,?)",
                (k, json.dumps(v)),
            )
        # Repair projects left mid-save.
        conn.execute(
            "UPDATE projects SET updated_at=? WHERE updated_at IS NULL", (now(),)
        )


def get_settings() -> dict[str, Any]:
    out = dict(DEFAULT_SETTINGS)
    with db() as conn:
        for row in conn.execute("SELECT key, value FROM settings"):
            try:
                out[row["key"]] = json.loads(row["value"])
            except Exception:
                pass
    return out


def set_settings(values: dict[str, Any]) -> dict[str, Any]:
    current = get_settings()
    for k, v in values.items():
        if k not in DEFAULT_SETTINGS:
            continue
        expected = type(DEFAULT_SETTINGS[k])
        if expected is bool:
            v = bool(v)
        elif expected is int:
            try:
                v = int(v)
            except Exception:
                continue
            if k in {"max_upload_mb"}:
                v = max(1, min(v, 512))
            elif k in {"max_image_pixels"}:
                v = max(1_000_000, min(v, 200_000_000))
            elif k in {"preview_max_dim", "max_output_dim"}:
                v = max(128, min(v, 4096))
            elif k == "worker_threads":
                v = max(1, min(v, 8))
            elif k == "max_tiles":
                v = max(64, min(v, 65536))
            elif k == "cache_limit_mb":
                v = max(64, min(v, 4096))
            elif k == "autosave_seconds":
                v = max(5, min(v, 300))
            elif k == "max_sheet_dim":
                v = max(512, min(v, 16384))
            elif k == "port":
                v = max(1024, min(v, 65535))
        current[k] = v
    with db() as conn:
        for k, v in values.items():
            if k in DEFAULT_SETTINGS:
                conn.execute(
                    "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (k, json.dumps(current[k])),
                )
    return current
