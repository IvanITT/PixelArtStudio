@echo off
setlocal EnableExtensions

set PORT=8765
set FOUND=0

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
  echo Stopping local studio server ^(PID %%P^)...
  taskkill /PID %%P /T /F >nul 2>nul
  set FOUND=1
)

if "%FOUND%"=="0" (
  echo The studio server is not running on port %PORT%.
) else (
  echo Done. The studio server has been stopped.
)
exit /b 0
