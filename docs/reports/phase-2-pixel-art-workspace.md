# Phase 2 — Image → Pixel Art and workspace

**Status:** complete.

## Completed features

- Pixel-art pipeline: resize methods (lanczos, bicubic, bilinear, nearest), block-size snapping, quantizers (median cut, octree, adaptive/max-coverage, seeded k-means), colour counts 2–256.
- Dithering: Floyd–Steinberg, Atkinson, Jarvis–Judice–Ninke and ordered Bayer; strength control.
- Adjustments: brightness, contrast, saturation, denoise, edge preserve, edge enhance.
- Palette lock to built-in/project palettes or custom hex list; automatic background transparency; output grid alignment; preview cache with hash keys.
- UI: source picker and drag-drop import, presets (16-bit RPG, Game Boy, PICO-8, HD pixel art, poster), live debounced preview, result/source comparison, palette swatches, output metrics and export.
- Konva workspace: layer list, drag/scale/rotate/opacity, visibility, z-order, duplicate/delete, 30-step undo/redo, pixel grid, zoom/fit, layout persistence in project state and composite PNG export.
- Shell UI: sidebar, top bar search/import/save, status bar, toasts, autosave timer and keyboard shortcuts.

## Files

`backend/app/services/pixelart.py`, `backend/app/routers/pixelart.py`, `frontend/src/pages/PixelArt.tsx`, `frontend/src/components/{Workspace,ImageStage,Shell,TopBar}.tsx`.

## Tests

- Width/height and colour count after conversion.
- Determinism for identical options (including seeded k-means).
- Every quantizer × dither combination.
- Custom palette restriction and transparency/block-size behaviour.
- Workspace composite export through the API.

## Performance (test host)

- 384×288 preview, 24 colours, Floyd–Steinberg: **476.6 ms**, 11.2 MB peak.
- 256×192 k-means, 16 colours: **273.7 ms**, 8.9 MB peak.
- Preview cache hit: no image recomputation (hash-based file lookup).

## Limitations

- Very large sources are downscaled for preview (`preview_max_dim`, default 1200) and output is capped (`max_output_dim`, default 1024).
- The workspace is a compositor, not a full drawing editor (no brush/eraser yet).

## Next

Sprite extraction and tileset generation.

## Revision (2026-11-01)

The converter now requires an explicit **Process** action and shows the source immediately. Processing runs through a background job with real percentage/stage progress and automatically displays the result. See `fix-pixelart-processing.md`.
