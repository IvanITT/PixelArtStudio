@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo   Pixel Art ^& Game Asset Studio - first-time installer
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3.10+ was not found on PATH.
  echo Install Python from https://www.python.org/downloads/ and enable "Add python.exe to PATH".
  pause
  exit /b 1
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo [1/5] Creating Python virtual environment...
  python -m venv "backend\.venv"
  if errorlevel 1 (
    echo [ERROR] Could not create the virtual environment.
    pause
    exit /b 1
  )
) else (
  echo [1/5] Python virtual environment already exists.
)

echo [2/5] Installing backend dependencies (offline-friendly, pinned versions)...
"backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 (
  echo [ERROR] Backend dependency installation failed.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js / npm was not found on PATH. Install Node.js 18+ from https://nodejs.org/
  pause
  exit /b 1
)

echo [3/5] Installing frontend dependencies...
pushd frontend
call npm install
if errorlevel 1 (
  echo [ERROR] npm install failed.
  popd
  pause
  exit /b 1
)

echo [4/5] Building the production frontend bundle...
call npm run build
if errorlevel 1 (
  echo [ERROR] Frontend build failed.
  popd
  pause
  exit /b 1
)
popd

echo [5/5] Verifying the backend test suite...
pushd backend
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 (
  echo [WARN] Some backend tests failed. The app may still run, but check the output above.
)
popd

echo.
echo ============================================================
echo   Installation complete. Run start.bat to launch the studio.
echo   Everything runs locally at http://127.0.0.1:8765
echo ============================================================
pause
