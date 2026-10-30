"""Fast nearest-neighbour search over stored embeddings. NumPy only (safe for the hosted server)."""
import os
import sqlite3 as sql
import threading

import numpy as np

from config import DB_PATH

_lock = threading.Lock()
_index = None
_sig = None
UNKNOWN = {None, "", "unknown", "Unknown", "Unknown Artist"}
# Small additive bonuses on cosine similarity (range -1..1) for matching metadata.
BONUS = {"genre": 0.02, "artist": 0.03, "album": 0.02}


def invalidate():
    global _index, _sig
    with _lock:
        _index, _sig = None, None


def _signature():
    """Cheap fingerprint of the table, so a scan run in another process is noticed without a restart."""
    c = sql.connect(DB_PATH, timeout=30)
    try:
        return c.execute("SELECT COUNT(*), COUNT(embedding), MAX(id) FROM tracks").fetchone()
    except sql.OperationalError:
        return None
    finally:
        c.close()


def _load():
    c = sql.connect(DB_PATH, timeout=30)
    rows = c.execute("SELECT file_path, genre, artist, album, embedding FROM tracks "
                     "WHERE embedding IS NOT NULL").fetchall()
    c.close()
    vecs = [np.frombuffer(r[4], dtype=np.float32) for r in rows]
    dim = max((v.shape[0] for v in vecs), default=0)
    keep = [i for i, v in enumerate(vecs) if v.shape[0] == dim]
    if not keep:
        return None
    paths = [rows[i][0] for i in keep]
    return {
        "paths": paths,
        "by_name": {os.path.basename(p): i for i, p in enumerate(paths)},
        "genre": [rows[i][1] for i in keep],
        "artist": [rows[i][2] for i in keep],
        "album": [rows[i][3] for i in keep],
        "mat": np.stack([vecs[i] for i in keep]),
    }


def _get():
    global _index, _sig
    sig = _signature()
    with _lock:
        if _index is None or sig != _sig:
            _index, _sig = _load(), sig
        return _index


def similar(basename, k=10):
    """Top-k most similar tracks as [{'path', 'score'}] (lower score = closer, like the old API).
    Returns [] if the track has no embedding yet so callers can fall back."""
    idx = _get()
    if not idx or basename not in idx["by_name"]:
        return []
    i = idx["by_name"][basename]
    sims = idx["mat"] @ idx["mat"][i]
    for field, bonus in BONUS.items():
        ref = idx[field][i]
        if ref in UNKNOWN:
            continue
        sims = sims + bonus * np.array([v == ref for v in idx[field]], dtype=np.float32)
    sims[i] = -np.inf
    top = np.argsort(-sims)[:k]
    return [{"path": idx["paths"][j], "score": float(1.0 - sims[j])} for j in top if np.isfinite(sims[j])]
