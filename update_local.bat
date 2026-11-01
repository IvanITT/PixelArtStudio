@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo   Pixel Art ^& Game Asset Studio - local update
echo ============================================================
echo.

if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERROR] Backend environment missing. Run install.bat first.
  pause
  exit /b 1
)

echo [1/4] Stopping a running server (if any)...
call stop.bat

echo [2/4] Updating Python dependencies...
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 (
  echo [ERROR] pip install failed.
  pause
  exit /b 1
)

echo [3/4] Updating frontend dependencies and rebuilding...
pushd frontend
call npm install
if errorlevel 1 (
  echo [ERROR] npm install failed.
  popd
  pause
  exit /b 1
)
call npm run build
if errorlevel 1 (
  echo [ERROR] Frontend build failed.
  popd
  pause
  exit /b 1
)
popd

echo [4/4] Running backend tests...
pushd backend
".venv\Scripts\python.exe" -m pytest -q
popd

echo.
echo Update complete. Start the studio again with start.bat.
pause
