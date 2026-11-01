# Phase 5 — Animation, Asset Library and export packages

**Status:** complete.

## Completed features

**Animation**

- Animation records stored in SQLite with FPS, loop flag, ordered frame asset ids and metadata.
- Add frame, append, duplicate frame, reorder, delete and upload a custom frame.
- Templates: idle, walk, run, jump, fall, attack, hurt, death; frame count and replace-existing options.
- Playback with adjustable FPS, timeline thumbnails and frame inspector.
- Export: horizontal sheet (columns/gap/padding), animated GIF, animated WebP and JSON metadata; each export is saved as a real project asset.

**Asset Library**

- Grid with kind filters, text search, favourites and zoom density.
- Detail modal with rename, tag editing, dimensions, size, SHA-256, metadata JSON, download and delete.
- Multi-select batch actions (favourite, tags, delete), sprite-sheet packing and ZIP export.
- ZIP export runs as a background job with progress and a download link; preset, format and package name are configurable.

**Exporter**

- PNG/JPEG/BMP/WebP/GIF conversion with alpha handling.
- ZIP layout and manifests for generic, generic-spritesheet, Godot 4, Unity and RPG Maker.
- JSON/CSV metadata, safe ZIP entry names, atomic temp writes.

## Files

`backend/app/services/{animation,exporter}.py`, `backend/app/routers/{animation,export}.py`, `frontend/src/pages/{Animation,Library}.tsx`.

## Tests

- Template frame counts and determinism.
- Frame add/duplicate/reorder/delete and frame assets.
- Sheet dimensions, GIF/WebP signatures and JSON metadata.
- All image conversions and invalid format rejection.
- ZIP manifests for every preset and traversal-safe entries.

## Performance (test host)

- Animation sheet: **1.3 ms**, 0.01 MB peak.
- Animated GIF: **16.5 ms**, 0.11 MB peak.
- ZIP package: **6.9 ms**, 0.45 MB peak (small fixture).

## Limitations

- GIF is limited to a 256-colour palette; use WebP or PNG sheets for full RGBA.
- Sprite-sheet export uses uniform cell sizes; mixed-size sprites are padded.

## Next

Project manager, settings, style consistency and full quality pass.
