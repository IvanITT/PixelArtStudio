# Fix — Image → Pixel Art processing, progress and preview

**Date:** 2026-11-01
**Symptom:** after loading an image, the module showed no process button, no progress percentage and no source/result preview.

## Root cause

- The converter had **no explicit action button**: it relied on a hidden 320 ms debounced auto-preview.
- The centre stage defaulted to the *result* image, but `preview` was `null` until the silent request finished, so the stage rendered “No image”. The source was never shown while waiting.
- Processing used the synchronous `/api/pixelart/preview` endpoint, which exposes no progress events. There was nothing to display as a percentage.

## Fixes

**Backend**

- Refactored the preview pipeline into a shared `_render_preview()` helper.
- Added **`POST /api/pixelart/job`**: runs the existing `process_pixel_art()` in the background job pool and forwards its real stage progress (10 % adjusting, 25 % resizing, 45 % quantizing, 65 % dithering, 100 % done).
- The synchronous preview endpoint remains for compatibility/tests.
- Added an API test for the background job (`test_pixelart_background_job`), bringing the suite to **57 passing tests**.

**Frontend**

- The source image is shown **immediately** as soon as it is selected/imported (badge **FUENTE**), before any processing.
- Added a prominent **Procesar / Process** button in the toolbar; it starts the background job and is disabled while running.
- Added a real **progress bar + percentage + stage label** in three places:
  - a strip below the toolbar,
  - an overlay on the image,
  - the Output panel.
- On completion the view switches automatically to the **RESULTADO/RESULT** image and shows size, colours, work grid, time, palette and **Download PNG**.
- Users can switch **Resultado/Fuente** at any time.
- Changing options marks the result as “Cambios sin procesar” without destroying the current preview; press Process again to update it.
- Changing the project/source clears the old preview and stops polling.

## Verification

- Imported a 1600×1200 PNG on a fresh project.
- Before processing: source visible with **FUENTE** badge and the **Procesar** button enabled.
- Immediately after clicking: button read **“Processing 0%”**, overlay showed **“Procesando… 0% · En cola”**.
- After completion: **RESULTADO** badge, output **128×96**, **16 colours**, **51 ms**, palette swatches and **Descargar PNG** visible.
- `npm run typecheck` and `npm run build` pass; backend **57 passed**.

## Files touched

- `backend/app/routers/pixelart.py` — shared preview renderer + `/pixelart/job`.
- `backend/tests/test_api.py` — background-job test.
- `frontend/src/api/client.ts` — `pixelPreviewJob`.
- `frontend/src/pages/PixelArt.tsx` — manual processing, job polling, source/result stage, progress UI.
- `frontend/src/i18n.tsx` — process/progress/error translations.
- `README.md` — updated workflow.
