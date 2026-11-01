# Phase 1 — Foundation, storage and local engine

**Status:** complete.

## Completed features

- FastAPI application with local-only binding, CORS restricted to `127.0.0.1:8765` / `127.0.0.1:5173`, security headers and JSON error handlers.
- `config.py`: repository paths, `PAS_DATA_DIR` override, `safe_join`, validated hex identifiers, pinned default settings.
- SQLite schema for projects, assets, animations, palettes, library tags, jobs, backups and benchmarks; startup migration/repair.
- Storage layer: project folders (`assets`, `thumbs`, `sources`, `previews`, `exports`, `backups`), asset serialization URLs, project JSON writer, 15-snapshot rotation, data-usage metrics and temp cleanup.
- Background job manager: bounded worker pool, progress messages, SSE event stream, cancellation, startup recovery for interrupted jobs.
- Image utilities: validated decode, RGBA normalization, thumbnails, resizing, hashing, transparency trimming, byte formatting.
- Launcher scripts: `install.bat`, `start.bat`, `stop.bat`, `update_local.bat`, `run_dev.bat`.
- Vite/React/TypeScript/Tailwind frontend skeleton with strict typecheck.

## Files

`backend/app/{config,db,jobs,main}.py`, `backend/app/services/{images,storage,palettes,projectio}.py`, `backend/app/routers/{system,projects}.py`, launcher `.bat` files, `frontend` toolchain.

## Tests

- Project creation, rename, duplicate, delete and backup/restore.
- Asset upload validation, thumbnail/source preservation, tag/favourite updates and batch actions.
- Path-traversal rejection for ids, uploads, downloads and ZIP entries.
- Job lifecycle, progress and SSE event shape.
- Project `.pasproject.zip` export/import round-trip.

## Performance

- Server startup with DB init and palette seeding: under 1 s on the test host.
- Empty data directory footprint: ~85 KB (SQLite + initial project folders).

## Limitations

- Uploads are capped by settings; the default 40 MP limit rejects very large camera images with a clear error.
- SQLite is single-writer; the job pool serializes metadata writes but image processing runs concurrently.

## Next

Pixel-art processing pipeline and the interactive workspace.
