# Phase 8 — Root executable launcher

**Status:** complete.

## Requested feature

Add an executable in the project root that starts the platform automatically.

## Implementation

- **`PixelArtStudio.exe`** in the repository root. Double-click launches the studio; no console window is shown.
- Written in C# and compiled as a Windows GUI executable with the C# compiler shipped with .NET Framework 4.8 (`build_exe.bat`).
- Embedded icon (`launcher/PixelArtStudio.ico`) and product/version metadata (`1.0.0.0`).
- Startup sequence:
  1. Locates the executable directory.
  2. Verifies `backend\.venv\Scripts\python.exe`.
  3. If `frontend\dist\index.html` is missing, tries `npm run build` in `frontend` (up to 3 minutes).
  4. Checks whether port 8765 is already listening.
  5. If no server is running, launches `uvicorn app.main:app` hidden via `cmd.exe`, with stdout/stderr redirected to `data\launcher-server.log`.
  6. Polls `/api/health` for up to 30 seconds.
  7. Opens `http://127.0.0.1:8765` in the default browser and exits, leaving the server running.
- **Single instance:** a named mutex prevents duplicate launches; a second launch waits for health and only opens the browser.
- **Existing instance:** if the port is already serving the studio, it opens the browser without spawning anything.
- **Error handling:** message boxes for missing dependencies, a failed frontend build, an occupied port, early server exit or timeout, with the diagnostic log path.
- **Stop:** `stop.bat` still stops the server started by the executable.
- **Rebuild:** `build_exe.bat` recompiles the launcher from `launcher\*.cs` and the icon.

## Files

- `PixelArtStudio.exe` — ready to run.
- `launcher/PixelArtStudioLauncher.cs` — launcher logic.
- `launcher/AssemblyInfo.cs` — version metadata.
- `launcher/PixelArtStudio.ico` — icon.
- `launcher/make_icon.py` — icon generator.
- `build_exe.bat` — reproducible build.
- `README.md` — usage instructions.

## Verification

- Stopped the running server, double-click equivalent (`Start-Process PixelArtStudio.exe`), waited 6 s: `/api/health` returned **200**, launcher exited, browser requests appeared in `data\launcher-server.log`.
- Ran the executable again while the server was active: it exited after ~2 s without creating a second listener; exactly **1** process listened on port 8765.
- Confirmed product metadata and icon are embedded.
- `npm run typecheck` / `npm run build` still pass; backend suite remains **56 passed**.

## Limitations

- Windows-only (uses .NET Framework and `cmd.exe`); `start.bat` remains the cross-platform alternative.
- The executable is unsigned, so SmartScreen may show a warning the first time. The full source and reproducible build are included.
- It starts the server in the background but does not provide a tray menu; use `stop.bat` to stop it or close the hidden `cmd.exe`/Python process from Task Manager.
- `install.bat` must be run once before the executable can start the platform.

## Next

- Add a tray icon with “Open studio”, “Stop server” and “Quit”.
- Code-sign the launcher and package the backend with PyInstaller/Electron for a fully self-contained installer.
