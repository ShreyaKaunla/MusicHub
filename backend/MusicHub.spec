# PyInstaller spec for the MusicHub desktop build (light: ONNX CLAP, no torch).
# Build: cd backend && ..\build-env\Scripts\python.exe -m PyInstaller MusicHub.spec --noconfirm
# Expects backend/web/ (built UI) and backend/models/clap_audio_int8.onnx to exist.
# -*- mode: python ; coding: utf-8 -*-
import os

from PyInstaller.utils.hooks import collect_all

datas = [
    ("web", "web"),          # the built React UI, served by the backend itself
]
# bundle only the runtime model (the fp32 export stays dev-only: it's >100 MB)
for _name in ("clap_audio_int8.onnx",):
    _p = os.path.join(SPECPATH, "models", _name)
    if os.path.isfile(_p):
        datas.append((_p, "models"))
binaries = []
hiddenimports = []

# Brute-force collect the runtime-critical packages (handles lazy imports, data files and DLLs).
for pkg in [
    "librosa", "numba", "llvmlite", "soundfile", "audioread",
    "onnxruntime", "uvicorn", "fastapi", "starlette", "anyio", "sniffio", "click", "h11",
    "pydantic", "pydantic_core", "annotated_types", "typing_extensions",
    "mutagen", "tinytag", "email_validator", "idna",
]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["desktop_app.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # never shipped in the light build (embeddings.py falls back to the ONNX backend)
        "torch", "torchvision", "torchaudio", "transformers", "safetensors",
        # clearly not needed
        "tkinter", "matplotlib", "IPython", "pandas", "PyQt5", "PySide2", "PySide6",
        "torchcodec", "torchlibrosa",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MusicHub",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # windowed app: logs go to %LOCALAPPDATA%\MusicHub\logs
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MusicHub",
)
