@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set PORT=8765
set HOST=127.0.0.1

if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERROR] Backend environment missing. Run install.bat first.
  pause
  exit /b 1
)

if not exist "frontend\dist\index.html" (
  echo [WARN] Production frontend bundle not found. Attempting a build...
  pushd frontend
  call npm run build
  popd
  if not exist "frontend\dist\index.html" (
    echo [ERROR] Frontend bundle is missing. Run install.bat or "npm run build" inside frontend.
    pause
    exit /b 1
  )
)

powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue; if ($c) { Write-Host '[INFO] Studio is already running on port %PORT%.'; exit 0 } else { exit 1 }"
if not errorlevel 1 (
  start "" "http://%HOST%:%PORT%"
  exit /b 0
)

echo Starting Pixel Art ^& Game Asset Studio at http://%HOST%:%PORT% ...
start "Pixel Art Studio - local server" /min "backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --host %HOST% --port %PORT% --app-dir backend

rem Give uvicorn a moment to bind the port before opening the browser.
ping -n 4 127.0.0.1 >nul
start "" "http://%HOST%:%PORT%"

echo.
echo The server runs in a minimized window titled "Pixel Art Studio - local server".
echo Close that window or run stop.bat to stop it.
exit /b 0
