@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%CSC%" (
  echo [ERROR] No se encontro el compilador de C# de .NET Framework.
  echo Instala .NET Framework 4.8 o usa start.bat como lanzador.
  pause
  exit /b 1
)

echo Compilando PixelArtStudio.exe...
"%CSC%" /nologo /target:winexe /platform:anycpu /optimize+ /codepage:65001 ^
  /win32icon:"launcher\PixelArtStudio.ico" ^
  /reference:System.dll /reference:System.Core.dll /reference:System.Windows.Forms.dll /reference:System.Drawing.dll ^
  /out:"PixelArtStudio.exe" ^
  "launcher\AssemblyInfo.cs" "launcher\PixelArtStudioLauncher.cs"

if errorlevel 1 (
  echo [ERROR] Fallo la compilacion del lanzador.
  pause
  exit /b 1
)

echo.
echo Listo: %CD%\PixelArtStudio.exe
exit /b 0
