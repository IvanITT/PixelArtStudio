@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERROR] Backend environment missing. Run install.bat first.
  pause
  exit /b 1
)

echo Starting backend on http://127.0.0.1:8765 ...
start "Pixel Art Studio - backend (dev)" powershell -NoProfile -NoExit -Command "Set-Location '%~dp0'; & 'backend\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --app-dir backend --reload"

echo Starting Vite dev server on http://127.0.0.1:5173 ...
start "Pixel Art Studio - vite (dev)" powershell -NoProfile -NoExit -Command "Set-Location '%~dp0frontend'; npm run dev"

ping -n 5 127.0.0.1 >nul
start "" "http://127.0.0.1:5173"
exit /b 0
