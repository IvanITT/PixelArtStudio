# Fix — image import on a fresh install

**Date:** 2026-11-01
**Symptom:** selecting an image in the top bar or a drop zone did not load anything.

## Root cause

The studio starts with **no active project**. The top-bar **Import** button was disabled when `projectId` was null, and the module drop zones called:

```ts
if (!projectId) return;
```

The file chooser could open, but the upload returned immediately without an error, asset or toast. On a fresh installation the user therefore saw “nothing happens”.

The backend upload endpoint itself was healthy: a direct multipart upload returned `201/200` with the asset metadata.

## Fixes

1. **`ensureProject()` in the studio store** — returns the active project or creates/selects “Mi proyecto” / “My project” automatically before an import.
2. **Top bar** — Import is no longer disabled without a project; `upload()` calls `ensureProject()` before uploading and still shows errors/success toasts.
3. **All module drop zones** — Pixel Art, Sprite Extractor, Tileset Generator and False 3D now use the same `ensureProject()` path instead of silently returning.
4. **Automatic selection** — the imported asset is stored as `lastImported`; the four image-based modules select it immediately, so the preview/canvas shows the image without an extra click.
5. **Actionable error messages** — unsupported formats, size limits, decode failures and occupied ports are surfaced. Spanish translation patterns were added for upload errors and imported-asset toasts.

## Verification

- Deleted all projects, opened `/pixelart`, imported a 320×240 PNG through the top-bar input.
- Result: project **“Mi proyecto”** created automatically, asset **upload_test** saved, source selected, preview generated (**15 colours**), success toast shown.
- Repeated with no project via the same code path used by drop zones; upload and auto-selection worked.
- Uploading an invalid `.txt` displayed: “No se pudo decodificar la imagen…” instead of failing silently.
- `npm run typecheck` and `npm run build` pass; backend suite remains **56 passed**.

## Files touched

- `frontend/src/store/studio.ts` — `ensureProject`, `lastImported`.
- `frontend/src/components/TopBar.tsx` — enabled import, ensure project, select imported asset.
- `frontend/src/pages/{PixelArt,Sprites,Tileset,False3D}.tsx` — ensure project on upload and auto-select `lastImported`.
- `frontend/src/i18n.tsx` — upload/error/toast translations.
- `README.md` — first-import behaviour.
