# Phase 3 — Sprite Extractor and Tileset Generator

**Status:** complete.

## Completed features

**Sprites**

- Mask modes: auto alpha, background colour, target colour, luminance threshold.
- Connected-component extraction with tolerance, minimum area, maximum sprite count, merge-gap grouping (border-safe dilation), padding, transparency trimming and optional 64×64 normalization.
- Per-sprite alpha cutout, bounding-box metadata, SHA-256 identity and near-duplicate detection with average hash.
- Save sprites as assets, multi-select, sprite-sheet packing with columns/spacing/padding/max dimension and metadata.

**Tilesets**

- Uniform-grid extraction with margin, spacing, offset X/Y, empty-tile removal and duplicate/near-duplicate hashes.
- Tile previews with source coordinates and selection; sheet export.
- 16-mask autotile generation for nine terrain families with seed and variation count; gallery of masks and a saved tileset asset.
- Seamless edge blending with measured seam error before/after.
- Hue/saturation/brightness recolour and save.

## Files

`backend/app/services/{sprites,tileset}.py`, `backend/app/routers/{sprites,tileset}.py`, `frontend/src/pages/{Sprites,Tileset}.tsx`.

## Bugs fixed during the phase

- Sprite distance computation used `int16`, overflowing for large distances and producing invalid square roots; switched to `float32`.
- Merge-gap morphology closing merged unrelated sprites; replaced with dilation-based grouping and a clamped border-safe dilate.
- Sheet compositing failed on RGB tiles; both `tiles_to_sheet` and `pack_spritesheet` now normalize to RGBA first.
- Grid test expectation corrected to 25 tiles for a 5×5 grid (the implementation was verified correct).

## Tests

- Alpha and background segmentation, trims, merge gap, min area, max sprites, duplicate counts.
- Packing layout dimensions and metadata.
- Grid extraction with margins/spacing/offsets, empty removal, duplicates and truncation.
- Autotile mask count, seamless error reduction and recolour output.

## Performance (test host)

- Sprite extraction from a 512×256 sheet: **9.0 ms**, 2.3 MB peak.
- Tileset extraction from 512×512 at 32 px: **145.8 ms**, 0.3 MB peak.
- 16-mask terrain generation: **12.8 ms**, 0.14 MB peak.

## Limitations

- Touching sprites need merge-gap tuning or a different mask mode.
- Autotile families are procedural approximations, not imported tileset standards (Wang/edge sets are on the roadmap).

## Next

Procedural generators and the False 3D lab.
