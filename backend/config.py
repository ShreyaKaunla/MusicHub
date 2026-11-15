"""Central configuration. Single-user, local-first: your music and history never leave this machine."""
import json
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent

DATA_DIR = Path(os.getenv("DATA_DIR", str(BACKEND_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = str(DATA_DIR / "sql_db.db")

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

# Watch the music folder and process new songs automatically.
AUTO_SYNC = os.getenv("AUTO_SYNC", "1") == "1"

# ---- the music folder -------------------------------------------------------------------------
# Priority: MUSIC_DIR env var > folder remembered in settings.json > ~/Music.
# The choice is saved, so it survives server restarts and `python scan.py` in a new terminal.
_SETTINGS = DATA_DIR / "settings.json"


def _saved_folder():
    try:
        return json.loads(_SETTINGS.read_text(encoding="utf-8")).get("music_dir") or None
    except (OSError, ValueError):
        return None


_env_music = os.getenv("MUSIC_DIR")
_music_dir = _env_music or _saved_folder() or str(Path.home() / "Music")
_configured = bool(_env_music or _saved_folder())


def get_active_music_folder() -> str:
    return _music_dir


def folder_is_configured() -> bool:
    """False until a folder was chosen explicitly (or adopted from an existing library)."""
    return _configured


def set_active_music_folder(path) -> None:
    global _music_dir, _configured
    _music_dir = str(path)
    _configured = True
    if not _env_music:  # an explicit MUSIC_DIR pins the folder; never overwrite that
        try:
            _SETTINGS.write_text(json.dumps({"music_dir": _music_dir}), encoding="utf-8")
        except OSError as e:
            print(f"⚠️ Could not save the music folder choice: {e}")
