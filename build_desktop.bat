@echo off
setlocal
cd /d %~dp0

if not exist "build-env\Scripts\python.exe" (
    echo [!] No build-env python found. Create it first:
    echo     python -m venv build-env
    echo     build-env\Scripts\pip install -r backend\requirements.txt -r backend\requirements-ml.txt pyinstaller
    exit /b 1
)

echo [1/3] Building the web UI into backend\web ...
pushd my-react-app
  if not exist node_modules (
    echo    npm install first ...
    call npm install || goto :err
  )
  call npm run build || goto :err
popd
if exist "backend\web" rmdir /s /q "backend\web"
robocopy "my-react-app\dist" "backend\web" /E /NFL /NDL /NJH /NJS >nul
if errorlevel 8 goto :err

echo [2/3] Packaging the desktop app with PyInstaller ...
pushd backend
  "%~dp0build-env\Scripts\python.exe" -m PyInstaller MusicHub.spec --noconfirm --distpath "..\dist" --workpath "..\build" || goto :err
popd

echo [3/3] Done: dist\MusicHub\MusicHub.exe
echo       Optional installer: run build_installer.bat
goto :eof

:err
popd
echo [!] Build failed.
exit /b 1
