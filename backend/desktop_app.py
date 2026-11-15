"""Desktop app entry point (packaged with PyInstaller, see build_desktop.bat).

Runs the FastAPI backend, serves the built UI from backend/web, then opens it in the browser.
Library data (database, settings, logs) lives in %LOCALAPPDATA%\\MusicHub so the installed app
and its data survive updates.
"""
import multiprocessing
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

APP_NAME = "MusicHub"
START_PORT = 8000
BACKEND_READY_TIMEOUT = 20  # seconds


def data_dir():
    base = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / APP_NAME


def _setup_environment():
    """Must run before anything imports config."""
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DATA_DIR", str(d))
    os.environ.setdefault("PYTHONUTF8", "1")
    logs = d / "logs"
    logs.mkdir(exist_ok=True)
    # windowed exe: no console — send all prints/logs to a rotating-ish log file
    log_file = open(logs / time.strftime("musichub_%Y%m%d.log"), "a", buffering=1, encoding="utf-8")
    sys.stdout = log_file
    sys.stderr = log_file
    return d


def _is_musichub(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as r:
            import json
            return json.loads(r.read().decode()).get("status") == "ok"
    except Exception:
        return False


def _find_port():
    port = START_PORT
    if not _port_free(port):
        if _is_musichub(port):      # an instance is already running: just open it
            return port, True
        while port < START_PORT + 20 and not _port_free(port):
            port += 1
    return port, False


def _port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def main():
    multiprocessing.freeze_support()   # required: scan.py fingerprinting spawns worker processes
    data = _setup_environment()
    print(f"{APP_NAME} data folder: {data}")

    port, reuse = _find_port()
    url = f"http://127.0.0.1:{port}"
    if reuse:
        print(f"{APP_NAME} already running at {url} — opening it.")
        webbrowser.open(url)
        return

    import uvicorn
    import main as backend_main

    threading.Timer(1.5, webbrowser.open, (url,)).start()
    print(f"Serving {APP_NAME} at {url} (Ctrl+C or closing the console exits).")
    uvicorn.run(backend_main.app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
