"""Mood analysis and sorting (offline/desktop feature). Likes and playlists live in userdata.py.

librosa is imported lazily so the hosted server (which never analyses audio) doesn't need it.
"""
import os
import sqlite3 as sql

import numpy as np
from fastapi import APIRouter, BackgroundTasks, HTTPException
from tinytag import TinyTag
from concurrent.futures import ProcessPoolExecutor

from config import DB_PATH, ALLOW_ANALYSIS, get_active_music_folder
from identity import ensure_owner_schema

router = APIRouter()
MOODS = ["Happy", "Sad", "Soothing", "Energetic", "Bollywood Party", "Oldy", "Motivational"]
progress = {"running": False, "done": 0, "total": 0}


def db():
    return sql.connect(DB_PATH, timeout=30)


def ensure_extra_schema():
    c = db()
    cur = c.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS mood_features (
        track_id INTEGER PRIMARY KEY, tempo REAL, rms REAL, centroid REAL,
        onset REAL, mode_score REAL, year INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS mood_removed (
        playlist_id INTEGER, track_id INTEGER, PRIMARY KEY (playlist_id, track_id))""")
    for table, col, ddl in [("user_playlists", "is_mood", "INTEGER DEFAULT 0"),
                            ("playlist_tracks", "auto", "INTEGER DEFAULT 0"),
                            ("tracks", "language", "TEXT")]:
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})")]
        if col not in cols:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    c.commit()
    c.close()


# ------------------------------------------------------------------ mood analysis
# Krumhansl-Schmuckler key profiles: used to tell major (bright) from minor (dark)
MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def _mode_score(chroma):
    maj = max(np.corrcoef(chroma, np.roll(MAJ, k))[0, 1] for k in range(12))
    mnr = max(np.corrcoef(chroma, np.roll(MIN, k))[0, 1] for k in range(12))
    return float(maj - mnr)  # > 0 major, < 0 minor


def _analyze_file(path):
    """20 s clip from the middle at 11 kHz: far cheaper than the whole song, plenty for these features."""
    try:
        import librosa
        try:
            from librosa.feature.rhythm import tempo as _tempo
        except ImportError:  # older librosa
            from librosa.beat import tempo as _tempo
        y, sr = librosa.load(path, sr=11025, mono=True, offset=40, duration=20)
        if len(y) < sr * 5:  # short song: take it from the start
            y, sr = librosa.load(path, sr=11025, mono=True, duration=20)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        return (
            float(np.atleast_1d(_tempo(onset_envelope=onset_env, sr=sr))[0]),
            float(np.mean(librosa.feature.rms(y=y))),
            float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))),
            float(np.mean(onset_env)),
            _mode_score(np.mean(librosa.feature.chroma_stft(y=y, sr=sr), axis=1)),
        )
    except Exception:
        return None


def _year(path):
    try:
        return int(str(TinyTag.get(path).year)[:4])
    except Exception:
        return None


def _pct(a):
    """Percentile rank 0..1 inside the user's own library, so thresholds adapt to it."""
    return a.argsort().argsort() / max(len(a) - 1, 1)


def assign_moods():
    ensure_owner_schema()  # mood playlists are the ones with owner ''
    c = db()
    cur = c.cursor()
    rows = cur.execute("""SELECT t.id, t.genre, t.title, t.language,
                                 f.tempo, f.rms, f.centroid, f.onset, f.mode_score, f.year
                          FROM tracks t JOIN mood_features f ON f.track_id = t.id""").fetchall()
    pids = {}
    for m in MOODS:
        cur.execute("INSERT OR IGNORE INTO user_playlists (name, owner) VALUES (?, '')", (m,))
        cur.execute("UPDATE user_playlists SET is_mood=1 WHERE name=? AND owner=''", (m,))
        pids[m] = cur.execute("SELECT id FROM user_playlists WHERE name=? AND owner=''", (m,)).fetchone()[0]
        cur.execute("DELETE FROM playlist_tracks WHERE playlist_id=? AND auto=1", (pids[m],))
    removed = {(r[0], r[1]) for r in cur.execute("SELECT playlist_id, track_id FROM mood_removed")}
    manual = {(r[0], r[1]) for r in cur.execute("SELECT playlist_id, track_id FROM playlist_tracks")}

    tags = []  # (mood, track_id)
    ok = [r for r in rows if r[4] is not None]
    if ok:
        A = np.array([[r[4], r[5], r[6], r[7], r[8]] for r in ok], dtype=float)
        tempo, rms, cent, ons, mode = [_pct(A[:, i]) for i in range(5)]
        energy = 0.35 * rms + 0.30 * ons + 0.20 * tempo + 0.15 * cent
        valence = 0.50 * mode + 0.30 * cent + 0.20 * tempo
        for i, r in enumerate(ok):
            tid, bpm, e, v = r[0], r[4], energy[i], valence[i]
            meta = " ".join(str(x or "") for x in (r[1], r[2], r[3])).lower()
            desi = any(w in meta for w in ["bollywood", "punjabi", "hindi", "bhangra", "desi", "party"])
            if v < 0.35 and e < 0.50: tags.append(("Sad", tid))
            if e < 0.30 and v >= 0.35: tags.append(("Soothing", tid))
            if v > 0.65 and e >= 0.35: tags.append(("Happy", tid))
            if e > 0.75: tags.append(("Energetic", tid))
            if e > 0.60 and v > 0.50 and 95 <= bpm <= 160: tags.append(("Motivational", tid))
            if desi and e > 0.55 and v > 0.50: tags.append(("Bollywood Party", tid))
    for r in rows:  # Oldy is metadata-based: audio can't reliably tell the era
        meta = " ".join(str(x or "") for x in (r[1], r[2])).lower()
        if (r[9] and r[9] <= 1999) or any(w in meta for w in ["oldies", "retro", "vintage"]):
            tags.append(("Oldy", r[0]))

    for mood, tid in tags:
        pid = pids[mood]
        if (pid, tid) in removed or (pid, tid) in manual:
            continue
        cur.execute("INSERT INTO playlist_tracks (playlist_id, track_id, auto) VALUES (?,?,1)", (pid, tid))
    c.commit()
    c.close()


def _resolve(path):
    if os.path.exists(path):
        return path
    alt = os.path.join(get_active_music_folder(), os.path.basename(path))
    return alt if os.path.exists(alt) else None


def _task(item):
    """Runs inside a worker process."""
    tid, path = item
    if not path:
        return tid, None, None
    return tid, _analyze_file(path), _year(path)


def _save(batch):
    c = db()
    c.executemany("INSERT OR REPLACE INTO mood_features VALUES (?,?,?,?,?,?,?)", batch)
    c.commit()
    c.close()


def _store(results):
    batch = []
    for tid, feats, year in results:
        batch.append((tid, *(feats or (None,) * 5), year))
        progress["done"] += 1
        if len(batch) >= 25:
            _save(batch)
            batch = []
    if batch:
        _save(batch)


def _pending_ids():
    c = db()
    ids = {r[0] for r in c.execute("SELECT id FROM tracks WHERE id NOT IN (SELECT track_id FROM mood_features)")}
    c.close()
    return ids


def _run_analysis():
    try:
        c = db()
        todo = c.execute("SELECT id, file_path FROM tracks WHERE id NOT IN (SELECT track_id FROM mood_features)").fetchall()
        c.close()
        items = [(tid, _resolve(p)) for tid, p in todo]
        progress["total"] = len(items)
        try:
            workers = max(1, min(8, (os.cpu_count() or 2) - 1))
            with ProcessPoolExecutor(max_workers=workers) as pool:
                _store(pool.map(_task, items, chunksize=4))
        except Exception as e:  # multiprocessing unavailable: do the rest one by one
            print(f"Parallel analysis failed ({e}); continuing in a single process")
            left = _pending_ids()
            progress["done"] = progress["total"] - len(left)
            _store(_task(it) for it in items if it[0] in left)
        assign_moods()
    finally:
        progress["running"] = False


@router.post("/api/analyze-moods")
def analyze_moods(bg: BackgroundTasks):
    if not ALLOW_ANALYSIS:
        raise HTTPException(403, "Mood analysis is disabled on this server (precomputed offline).")
    ensure_extra_schema()
    if progress["running"]:
        return {"status": "already running"}
    progress.update(running=True, done=0, total=0)
    bg.add_task(_run_analysis)
    return {"status": "started"}


@router.get("/api/analyze-moods/status")
def analyze_status():
    return progress
