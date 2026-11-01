# Phase 7 — Bilingual interface (Spanish / English)

**Status:** complete.

## Requested feature

Add a language switch in the top bar to change the interface between Spanish and English.

## Implementation

- **Top bar control:** an `ES | EN` segmented switch in the header, next to the project selector. It applies instantly, does not reload the page and preserves selection, forms, layers and playback state.
- **Persistence:** choice stored in `localStorage` (`pas.language`). On first visit the browser language is used; `es-*` opens in Spanish, everything else in English. The `<html lang>` attribute is updated for accessibility and spell-checking.
- **Translation layer:** `frontend/src/i18n.tsx` contains a 600+ phrase Spanish dictionary, plural/count patterns and a `Localize` renderer used by every page, the shell, sidebar, status bar, toasts, asset pickers, image stage and workspace.
- **Attribute coverage:** placeholders, tooltips (`title`), `aria-label`, alternative text, panel subtitles, field labels, hints and option lists are translated together with visible text.
- **Dynamic values:** count/format patterns (`3 assets`, `12 shown · 4 selected`, `4 threads`, `1,318 ms`, `Analyse at …`) translate correctly while numbers, dimensions, hex colours, file names and user data stay untouched.
- **No data mutation:** only React display values are translated. Asset names, project names, tags, seeds, filenames and API payloads remain in their original language, so switching back to English restores the exact original UI.
- **Backend-driven labels:** procedural generator names/groups/parameters, false-3D templates, terrain names and animation templates are mapped in the dictionary so content coming from the API is also presented in Spanish.

## Files

- `frontend/src/i18n.tsx` — language type, dictionary, patterns, `Localize`, `LanguageRoot`.
- `frontend/src/store/studio.ts` — persisted `language` state and `setLanguage`.
- `frontend/src/components/TopBar.tsx` — ES/EN control.
- `frontend/src/App.tsx` — `LanguageRoot` around the router.
- All pages and shell components — wrapped with `Localize`.
- `README.md` — usage and behaviour documentation.

## Verification

- `npm run typecheck` clean.
- `npm run build` succeeds: 232 modules, 567.8 KB JS (168.2 KB gzip), 38.6 KB CSS.
- Browser pass in both languages on `/`, `/pixelart`, `/sprites`, `/tileset`, `/procedural`, `/false3d`, `/animation`, `/library`, `/style`, `/projects`, `/settings`.
- Confirmed instant ES → EN → ES switching, `documentElement.lang` updates, persistence after reload, and no React console errors.
- Confirmed user data is preserved: project name “Prueba ES” and assets “Tree 77 / Tree 78” are displayed unchanged in both languages.
- Backend suite remains **56 passed**; no API or storage changes were required.

## Limitations

- Interface translations are curated; a few technical terms intentionally remain in English (CPU, RAM, PNG, GIF, WebP, JSON, FPS, `start.bat`, palette brand names such as “PICO-8-inspired”).
- User-entered values and imported asset names are not translated.
- The feature is client-side only; API responses and OpenAPI descriptions remain English.

## Next

- Extract the dictionary to per-module JSON files if more languages are added.
- Add a language selector to Settings as a secondary entry point.
- Optional right-to-left layout audit if an RTL language is added later.
