# Phase 4 — Procedural Generator and False 3D Lab

**Status:** complete.

## Completed features

**Procedural (31 generators)**

- Nature: tree, bush, flower, rock, grass tuft, mushroom, cloud, mountain, potted plant.
- Fantasy: chest, barrel, crystal, potion, sword, shield, magic orb, totem.
- Environment: house, tower, ruin, fence, bridge, door, window, platform.
- Sci-fi: computer, console, robot, cargo container, industrial unit, neon decoration.
- Per-generator parameter schemas (ints, floats, booleans, selects) drive the UI automatically.
- Seeded deterministic output, variant families, palette restriction (built-in or custom), style presets (classic/pastel/neon/mono), dark outline, save-to-project metadata.

**False 3D (2.5D)**

- Templates: isometric object, isometric building, top-down RPG prop, side-view platformer prop, fake environment.
- Controls: projection (iso/top/side/shear), extrusion, relief light, floor count, perspective, angle, scale, cast shadow offsets/blur/opacity, backdrop, grid.
- Luminance heightmap generation with blur and inversion, saved as a real asset.
- Explicit disclaimer that the result is simulated 2.5D, not geometry reconstruction.

## Bugs fixed during the phase

- `Art.box` / `Art.ellipse` reversed coordinates crashed with `x1 < x0`; normalized before drawing.
- Palette mapping read a read-only NumPy array; switched to `copy=True`.
- Palette lookup now falls back to built-in palettes if the palette table is empty (fresh data directory).

## Tests

- All 31 generators produce non-empty RGBA output and exact seeds reproduce identical pixels.
- Palette restriction keeps every visible colour inside the requested palette.
- Variant families differ while remaining deterministic.
- Every false-3D template renders, shadow options change output, heightmap respects blur/inversion.

## Performance (test host)

- Six procedural assets: **36.1 ms**, 0.12 MB peak.
- False-3D projection: **339.5 ms**, 12.3 MB peak.

## Limitations

- Procedural art is stylised; the generators are not machine-learning models and do not invent novel object categories.
- Shadows are raster approximations; no normal maps or lighting engine.

## Next

Animation studio, asset library and export packages.
