"""Starts the MusicHub backend (FastAPI) on http://127.0.0.1:8000.

Frontend dev server: `npm run dev` inside my-react-app/ (talks to port 8000).
"""
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(BASE, "backend")


def main():
    # Prefer the full-ML environment (torch + transformers -> CLAP recommendations).
    candidates = [
        os.path.join(BASE, "build-env", "Scripts", "python.exe"),
        os.path.join(BACKEND, "env", "Scripts", "python.exe"),
        os.path.join(BACKEND, "venv", "Scripts", "python.exe"),
        sys.executable,
    ]
    python = next((p for p in candidates if os.path.exists(p)), sys.executable)
    print(f"⚡ Starting MusicHub backend on http://127.0.0.1:8000 (python: {python})")
    env = {**os.environ, "PYTHONUTF8": "1"}  # emoji logs crash on the Windows cp1252 console otherwise
    subprocess.run([python, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],
                   cwd=BACKEND, env=env)


if __name__ == "__main__":
    main()
