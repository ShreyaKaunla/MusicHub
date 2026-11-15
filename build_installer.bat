@echo off
setlocal
cd /d %~dp0

if not exist "dist\MusicHub\MusicHub.exe" (
    echo [!] dist\MusicHub\MusicHub.exe not found. Run build_desktop.bat first.
    exit /b 1
)

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo [!] Inno Setup 6 not found. Install it with:  winget install JRSoftware.InnoSetup
    exit /b 1
)

echo [1/1] Building the installer ...
"%ISCC%" installer.iss || exit /b 1

echo Done: installer_output\MusicHub-1.0.0-Setup.exe
