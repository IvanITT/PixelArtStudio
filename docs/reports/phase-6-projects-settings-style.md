# Phase 6 — Projects, settings, style consistency and quality pass

**Status:** complete.

## Completed features

**Projects**

- Card grid with search/category filter, favourites, counts, on-disk size and last update.
- Create/edit (name, description, category), duplicate, export `.pasproject.zip`, import `.pasproject.zip`, delete with confirmation.
- Manual snapshots and backup history (15 per project) with restore; autosave every 20 s by default.
- Opening a project selects it for every module and restores the workspace layout.

**Settings**

- Engine limits: upload MB, max pixels, preview/output dimensions, max tiles, max sheet dimension, cache limit, autosave interval, worker threads.
- Appearance: six accent colours and reduced motion.
- Palette management: list built-ins/project palettes, create custom palettes, delete non-built-ins.
- System panel: live memory/CPU, data usage, cache/temp sizes, versions, platform, frontend build status and links to Swagger/OpenAPI.
- Jobs panel and maintenance: cleanup temp/cache, run benchmarks with progress, benchmark history table.

**Asset Style Consistency (new module)**

- Persistent per-project style profile: palette id or custom hex list, colour budget, pixel scale 1–8×, outline mode/width/colour, shading steps, Bayer dithering and colour grading.
- Deterministic apply pipeline and per-asset audit metadata (`meta.style_info`).
- Consistency report with per-asset score, visible colours, palette coverage, outline ratio, estimated pixel scale and pairwise palette overlap; aggregate score and recommendations.
- UI page `/style`: profile editor, target grid with filters/selection, preview/apply actions, result gallery with before/after scores, and live report table.
- Integrated into the sidebar, dashboard quick actions, dashboard title bar, API client, OpenAPI schema and project ZIP settings.

**Quality fixes**

- Kanva workspace crash (`removeChild` NotFoundError) caused by React overlays sharing the Konva container; the stage now has its own absolute container and overlays are siblings.
- Backup list now refreshes immediately after “Snapshot now”.
- Empty project reports exclude source photos by default, so generated assets drive the score.
- Style pixel-scale resampling handles odd dimensions without stretching blocks; scale audit prefers the pre-outline measurement.
- Fixed status-bar/system data type mismatch (`data_dir`, `total_bytes`, `cache_bytes`, `tmp_bytes`).

## Files

`frontend/src/pages/{Projects,Settings,Style}.tsx`, `frontend/src/api/{client,types}.ts`, `backend/app/services/style.py`, `backend/app/routers/style.py`, `backend/tests/test_style.py`, launcher scripts, `README.md`.

## Tests

- Full backend suite: **56 passed** (51 previous + 5 style tests).
- Style tests: default/palette resolution, exact palette mapping and audit, inside-only outline, pixel-scale detection (including odd dimensions), aggregate consistency/pairwise overlap.
- Frontend: `npm run typecheck` clean; `npm run build` succeeds (231 modules, 530 KB JS / 154 KB gzip).
- End-to-end browser pass on all pages: project create, image import, pixel-art save, sprite extract + pack, tileset extract/save/autotile/seamless, procedural variants, 2.5D save, animation template + GIF export, library ZIP job, style apply/report, workspace layout + composite, settings palette/benchmark/cleanup, project snapshot/export/import/delete.
- Launcher pass: `stop.bat` stops the listener; `start.bat` rebuilds if needed, waits without console input and opens the studio.

## Performance

- Benchmark suite: **10/10 modules OK, 1,318 ms total, 12.3 MB peak** on the 4-core test host.
- Style report on 26 assets: a few seconds, CPU-only; style apply of 4 sprites: under 1 s.

## Limitations

- Style profile application is post-processing; it does not regenerate content semantically.
- Report analysis is synchronous; very large libraries should be analysed in selection batches.
- The `start.bat` window must remain open (minimized) while the studio is used; use the optional Electron strategy for a windowless build.

## Next

Optional Electron installer, drawing tools, Wang tilesets and background report jobs.
