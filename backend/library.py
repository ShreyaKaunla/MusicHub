"""Keeps the database in step with the music folder, automatically.

A background watcher checks the folder every few seconds. When it finds new MP3s it runs the whole
pipeline: tags -> fingerprints -> clusters -> pretrained embeddings -> (mood playlists, if you use them).
Progress is exposed at /api/library/status so the UI can show it, and nothing fails silently:
if embeddings can't be computed (e.g. torch missing) the reason is reported there.
"""
import os
import sqlite3 as sql
import threading
import time
from collections import Counter

from fastapi import APIRouter, HTTPException

import config
import embeddings
import similarity
import taste
from config import DB_PATH, get_active_music_folder

router = APIRouter()
POLL_SECONDS = 15
SETTLE_SECONDS = 5      # ignore files touched in the last few seconds: they may still be copying

_lock = threading.Lock()  # one sync at a time
status = {"running": False, "stage": "idle", "done": 0, "total": 0, "error": None, "last_finished": None}
_attempted_startup_repair = False


def _base(p):
    return os.path.basename(str(p).replace("\\", "/")).lower()


def embeddings_available():
    return embeddings.available()


def _counts():
    c = sql.connect(DB_PATH, timeout=30)
    try:
        r = c.execute("SELECT COUNT(*), COUNT(vector_data), COUNT(embedding) FROM tracks").fetchone()
    except sql.OperationalError:
        r = (0, 0, 0)
    c.close()
    return {"tracks": r[0], "fingerprinted": r[1], "embedded": r[2]}


def pending_files():
    """MP3s in the folder that aren't in the database yet (and have stopped changing)."""
    folder = get_active_music_folder()
    if not os.path.isdir(folder):
        return []
    c = sql.connect(DB_PATH, timeout=30)
    try:
        known = {_base(r[0]) for r in c.execute("SELECT file_path FROM tracks")}
    except sql.OperationalError:
        known = set()
    c.close()
    now, out = time.time(), []
    for f in os.listdir(folder):
        if f.lower().endswith(".mp3") and f.lower() not in known:
            try:
                if now - os.path.getmtime(os.path.join(folder, f)) >= SETTLE_SECONDS:
                    out.append(f)
            except OSError:
                pass
    return out


def _missing_work():
    k = _counts()
    need = k["fingerprinted"] < k["tracks"]
    if embeddings_available():
        need = need or k["embedded"] < k["tracks"]
    return need


def adopt_folder_from_db():
    """If no folder was ever chosen, use the folder your existing library lives in (and remember it).
    Without this the server falls back to ~/Music after every restart and audio/auto-sync break."""
    if config.folder_is_configured():
        return
    c = sql.connect(DB_PATH, timeout=30)
    try:
        paths = [r[0] for r in c.execute("SELECT file_path FROM tracks LIMIT 5000")]
    except sql.OperationalError:
        paths = []
    c.close()
    dirs = Counter(os.path.dirname(p) for p in paths if p)
    for d, _ in dirs.most_common(3):
        if d and os.path.isdir(d):
            config.set_active_music_folder(d)
            print(f"📂 Music folder remembered from your library: {d}")
            return


def _progress(done, total):
    status["done"], status["total"] = done, total


def _has_mood_data():
    c = sql.connect(DB_PATH, timeout=30)
    try:
        return c.execute("SELECT COUNT(*) FROM mood_features").fetchone()[0] > 0
    except sql.OperationalError:
        return False
    finally:
        c.close()


def run_pipeline():
    """The whole sync. Returns False if another sync is already running."""
    if not _lock.acquire(blocking=False):
        return False
    try:
        import scan
        status.update(running=True, error=None, stage="scanning", done=0, total=0)
        notes = []
        try:
            scan.run_scan(settle=SETTLE_SECONDS)
            status.update(stage="fingerprinting", done=0, total=0)
            scan.mel(on_progress=_progress)
            scan.clustering()
            if embeddings_available():
                status.update(stage="embedding", done=0, total=0)
                scan.embed_new(on_progress=_progress)
            else:
                notes.append("Smart (CLAP) recommendations are off for new songs: the AI audio model "
                             "isn't available in this installation.")
            similarity.invalidate()
            taste.invalidate()
            if _has_mood_data():   # only if you already use mood playlists
                status.update(stage="moods", done=0, total=0)
                import extras
                extras.progress.update(running=True, done=0, total=0)
                extras._run_analysis()
        except Exception as e:
            print(f"Library sync failed: {e}")
            notes.append(f"Sync problem: {e}")
        status["error"] = " ".join(notes) or None
        return True
    finally:
        status.update(running=False, stage="idle", last_finished=time.time())
        _lock.release()


def start_sync():
    """Runs the pipeline in the background. False if one is already running."""
    if _lock.locked():
        return False
    threading.Thread(target=run_pipeline, daemon=True, name="library-sync").start()
    return True


def _watch():
    global _attempted_startup_repair
    time.sleep(3)  # let the server finish starting first
    while True:
        try:
            if config.folder_is_configured() and not _lock.locked():
                repair = not _attempted_startup_repair and _missing_work()
                _attempted_startup_repair = True   # corrupt files are retried once per server start, not forever
                if pending_files() or repair:
                    run_pipeline()
        except Exception as e:
            print(f"Library watcher error: {e}")
        time.sleep(POLL_SECONDS)


def start_watcher():
    if config.AUTO_SYNC:
        threading.Thread(target=_watch, daemon=True, name="library-watcher").start()


# ------------------------------------------------------------------ API
@router.get("/api/library/status")
def library_status():
    return {**status, "pending": len(pending_files()), "counts": _counts(),
            "embeddings_available": embeddings_available(), "folder": get_active_music_folder(),
            "folder_configured": config.folder_is_configured(), "auto_sync": config.AUTO_SYNC}


@router.post("/api/library/sync")
def library_sync():
    return {"status": "started" if start_sync() else "already running"}
