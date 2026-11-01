from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("PAS_DATA_DIR", REPO_ROOT / "data")).resolve()
PROJECTS_DIR = DATA_DIR / "projects"
DB_PATH = DATA_DIR / "studio.db"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

ID_RE = re.compile(r"^[a-f0-9]{8,32}$")

DEFAULT_SETTINGS: dict[str, Any] = {
    "max_upload_mb": 32,
    "max_image_pixels": 40_000_000,
    "preview_max_dim": 1200,
    "max_output_dim": 1024,
    "worker_threads": 4,
    "max_tiles": 4096,
    "cache_limit_mb": 512,
    "autosave_seconds": 20,
    "allow_network": False,
    "host": "127.0.0.1",
    "port": 8765,
    "accent": "violet",
    "reduce_motion": False,
    "max_sheet_dim": 8192,
}

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP", "BMP", "GIF"}


def ensure_dirs() -> None:
    for d in (DATA_DIR, PROJECTS_DIR, DATA_DIR / "tmp", DATA_DIR / "cache"):
        d.mkdir(parents=True, exist_ok=True)


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def valid_id(value: str) -> str:
    if not isinstance(value, str) or not ID_RE.match(value):
        raise ValueError("Invalid identifier")
    return value


def project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / valid_id(project_id)


def safe_join(base: Path, *parts: str) -> Path:
    """Resolve a path under base, rejecting traversal and absolute parts."""
    base = base.resolve()
    candidate = base
    for part in parts:
        if not part or part in {".", ".."} or "/" in part or "\\" in part:
            raise ValueError("Unsafe path segment")
        candidate = candidate / part
    resolved = candidate.resolve()
    if resolved != base and base not in resolved.parents:
        raise ValueError("Path escapes allowed directory")
    return resolved


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
