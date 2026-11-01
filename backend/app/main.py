from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import DATA_DIR, FRONTEND_DIST, ensure_dirs, now
from .db import db, get_settings, init_db
from .jobs import job_manager
from .routers import animation, export, pixelart, procedural, projects, pseudo3d, sprites, style, system, tileset
from .services.palettes import seed_builtin_palettes
from .services.storage import cleanup_temp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pixel-art-studio")

VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    init_db()
    seed_builtin_palettes()
    settings = get_settings()
    job_manager().configure(int(settings.get("worker_threads", 4)))
    with db() as conn:
        conn.execute(
            "UPDATE jobs SET status='error', message='Interrupted', error='Application stopped while the task was running', updated_at=? WHERE status IN ('queued','running')",
            (now(),),
        )
    removed = cleanup_temp(24 * 3600)
    log.info("Pixel Art & Game Asset Studio %s ready. Data: %s (temp cleaned: %s)", VERSION, DATA_DIR, removed)
    if not settings.get("allow_network", False):
        log.info("Local-only mode: no external network calls are made by the application.")
    yield
    log.info("Shutting down")


app = FastAPI(
    title="Pixel Art & Game Asset Studio",
    version=VERSION,
    description="Offline-first CPU image processing, pixel art, sprites, tilesets, procedural assets, false 3D and animation.",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8765", "http://localhost:8765",
        "http://127.0.0.1:5173", "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > 1_000_000_000:
                return JSONResponse({"detail": "Request exceeds the 1 GB hard limit"}, status_code=413)
        except ValueError:
            pass
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse({"detail": exc.errors()}, status_code=422)


for r in (system.router, projects.router, pixelart.router, sprites.router, tileset.router,
          procedural.router, pseudo3d.router, animation.router, export.router, style.router):
    app.include_router(r, prefix="/api")


if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="static")


@app.get("/", include_in_schema=False)
def root():
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return HTMLResponse(
        """<!doctype html><html><head><meta charset="utf-8"><title>Pixel Art & Game Asset Studio</title>
        <style>body{background:#0e1116;color:#dbe2ea;font-family:system-ui;padding:48px;line-height:1.6}
        code{background:#1b2029;padding:2px 6px;border-radius:4px}a{color:#b79cff}</style></head><body>
        <h1>Pixel Art &amp; Game Asset Studio</h1>
        <p>The API is running. The frontend bundle was not found.</p>
        <p>Build it once with <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>,
        then reload this page. For development run <code>npm run dev</code> and open port 5173.</p>
        <p>API documentation: <a href="/api/docs">/api/docs</a></p></body></html>""",
        status_code=200,
    )


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    index = FRONTEND_DIST / "index.html"
    candidate = (FRONTEND_DIST / path).resolve()
    if FRONTEND_DIST.exists() and str(candidate).startswith(str(FRONTEND_DIST.resolve())) and candidate.is_file():
        return FileResponse(candidate)
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"detail": "Not found"}, status_code=404)


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(settings.get("port", 8765)),
        reload=False,
        log_level="info",
    )
