import os
import sqlite3 as sql
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from tinytag import TinyTag

# Re-exported so existing imports (extras.py, main.py) keep working.
from config import DB_PATH, get_active_music_folder, set_active_music_folder  # noqa: F401

VECTOR_DIM = 128


def _connect(timeout=30.0):
    return sql.connect(DB_PATH, timeout=timeout)


def _base(path):
    """Case-insensitive bare file name, whichever OS wrote the path."""
    return os.path.basename(str(path).replace("\\", "/")).lower()


def _resolve(path):
    """The stored path if the file is still there, else the same file name inside the active folder."""
    if os.path.isfile(path):
        return path
    alt = os.path.join(get_active_music_folder(), os.path.basename(str(path).replace("\\", "/")))
    return alt if os.path.isfile(alt) else None


def ensure_schema_is_stable():
    conn = _connect()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT UNIQUE,
        title TEXT, artist TEXT, album TEXT, genre TEXT,
        vector_data BLOB,
        cluster_id INTEGER
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS user_playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS playlist_tracks (
        playlist_id INTEGER,
        track_id INTEGER,
        FOREIGN KEY(playlist_id) REFERENCES user_playlists(id) ON DELETE CASCADE,
        FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE
    )""")
    cols = {r[1] for r in cur.execute("PRAGMA table_info(tracks)")}
    for col, ddl in [("vector_data", "BLOB"), ("cluster_id", "INTEGER"), ("genre", "TEXT"),
                     ("embedding", "BLOB"), ("embed_model", "TEXT")]:
        if col not in cols:
            cur.execute(f"ALTER TABLE tracks ADD COLUMN {col} {ddl}")
    conn.commit()
    conn.close()


def _mp3_files(folder):
    return sorted(f for f in os.listdir(folder) if f.lower().endswith(".mp3"))


# ------------------------------------------------------------------ step 1: tags
def run_scan(settle=0):
    """Adds NEW files only (skipping any touched in the last `settle` seconds: still being copied). A file counts as known if its NAME is already in the DB (whatever folder
    string it was stored under), so re-scanning never creates duplicates."""
    ensure_schema_is_stable()
    folder = get_active_music_folder()
    if not os.path.isdir(folder):
        print(f"⚠️ Music folder not found: {folder}")
        return 0

    conn = _connect()
    cur = conn.cursor()
    known = {_base(r[0]) for r in cur.execute("SELECT file_path FROM tracks")}
    added = 0
    for name in _mp3_files(folder):
        if _base(name) in known:
            continue
        path = os.path.join(folder, name)
        if settle and time.time() - os.path.getmtime(path) < settle:
            continue  # half-copied file: the next check picks it up
        stem = os.path.splitext(name)[0]
        try:
            tag = TinyTag.get(path)
            title = tag.title or stem
            artist = tag.artist.capitalize() if tag.artist else "Unknown Artist"
            album = tag.album or "Unknown"
            genre = tag.genre or "Unknown"
        except Exception:
            title, artist, album, genre = stem, "Unknown Artist", "Unknown", "Unknown"
        cur.execute(
            "INSERT OR IGNORE INTO tracks (file_path, title, artist, album, genre) VALUES (?,?,?,?,?)",
            (path, title, artist, album, genre),
        )
        added += cur.rowcount
    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    conn.close()
    print(f"✅ Scan complete: {added} new, {total} total tracks.")
    return added


# ------------------------------------------------------------------ step 2: fingerprints
def fingerprint(path):
    """Swappable feature extractor: returns a float32 vector or None on failure."""
    try:
        import librosa  # lazy: only needed when fingerprinting new songs
        try:
            y, sr = librosa.load(path, sr=None, mono=True, dtype=np.float32)
        except Exception:
            y, sr = librosa.load(path, sr=22050, mono=True, dtype=np.float32)
        n_fft, hop = (2048, 512) if sr <= 22050 else (4096, 1024)
        m = librosa.feature.melspectrogram(y=y, sr=sr, n_fft=n_fft, hop_length=hop,
                                           n_mels=VECTOR_DIM, fmin=0.0, fmax=11025.0)
        vec = np.mean(librosa.power_to_db(m, ref=np.max), axis=1).astype(np.float32)
        return np.pad(vec, (0, max(0, VECTOR_DIM - len(vec))))[:VECTOR_DIM]
    except Exception as e:
        print(f"⚠️ Could not fingerprint {os.path.basename(path)}: {e}")
        return None  # stays NULL, retried on the next scan (no fake zero vectors)


def _work(item):
    orig, real = item
    vec = fingerprint(real)
    return orig, (vec.tobytes() if vec is not None else None)


def mel(on_progress=None):
    """Fingerprints only tracks that don't have a vector yet. on_progress(done, total) is optional."""
    ensure_schema_is_stable()
    conn = _connect()
    rows = [r[0] for r in conn.execute("SELECT file_path FROM tracks WHERE vector_data IS NULL")]
    conn.close()
    todo = [(p, _resolve(p)) for p in rows]
    todo = [(o, r) for o, r in todo if r]
    if not todo:
        print("✅ Nothing new to fingerprint.")
        return 0

    print(f"🎵 Fingerprinting {len(todo)} new tracks...")
    workers = max(1, min(8, (os.cpu_count() or 2) - 1))
    results = []
    try:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for i, res in enumerate(pool.map(_work, todo, chunksize=4), 1):
                results.append(res)
                if on_progress:
                    on_progress(i, len(todo))
    except Exception as e:
        print(f"Parallel fingerprinting failed ({e}); finishing in one process")
        for i, item in enumerate(todo[len(results):], len(results) + 1):
            results.append(_work(item))
            if on_progress:
                on_progress(i, len(todo))

    rows = [(blob, p) for p, blob in results if blob is not None]
    conn = _connect(60.0)
    for i in range(0, len(rows), 50):
        conn.executemany("UPDATE tracks SET vector_data=? WHERE file_path=?", rows[i:i + 50])
        conn.commit()
    conn.close()
    print(f"✅ Stored {len(rows)} fingerprints.")
    return len(rows)


# ------------------------------------------------------------------ step 2b: pretrained embeddings
def embed_new(on_progress=None):
    """Embeds tracks that have no embedding (or one from a different model). Resumable."""
    from embeddings import embed, EMBED_MODEL  # lazy: needs torch + transformers
    ensure_schema_is_stable()
    conn = _connect(60.0)
    rows = [r[0] for r in conn.execute(
        "SELECT file_path FROM tracks WHERE embedding IS NULL OR embed_model IS NOT ?", (EMBED_MODEL,))]
    todo = [(p, _resolve(p)) for p in rows]
    todo = [(o, r) for o, r in todo if r]
    print(f"🧠 Embedding {len(todo)} tracks with {EMBED_MODEL} (resumable: safe to stop and re-run)")
    done = fails = 0
    for n, (orig, real) in enumerate(todo, 1):
        vec = embed(real)
        fails = 0 if vec is not None else fails + 1
        if fails >= 15:  # a few corrupt MP3s are normal; 15 in a row means a systematic error
            conn.commit()
            conn.close()
            raise RuntimeError("15 songs in a row failed to embed. Fix the error printed above, then re-run "
                               "(finished songs are kept).")
        if vec is not None:
            conn.execute("UPDATE tracks SET embedding=?, embed_model=? WHERE file_path=?",
                         (vec.tobytes(), EMBED_MODEL, orig))
            done += 1
        if n % 10 == 0:
            conn.commit()
        if on_progress:
            on_progress(n, len(todo))
    conn.commit()
    conn.close()
    print(f"✅ Stored {done} embeddings.")
    return done


# ------------------------------------------------------------------ step 3: K-Means
def clustering(k_max=20, rounds=15, seed=0):
    """K-Means from scratch, vectorised with NumPy. Reassigns every track (cheap)."""
    ensure_schema_is_stable()
    conn = _connect()
    rows = conn.execute("SELECT file_path, vector_data FROM tracks WHERE vector_data IS NOT NULL").fetchall()
    conn.close()
    rows = [(p, np.frombuffer(b, dtype=np.float32)) for p, b in rows]
    rows = [(p, v) for p, v in rows if v.shape[0] == VECTOR_DIM]
    if not rows:
        print("⚠️ No vectors yet; run mel() first.")
        return

    X = np.stack([v for _, v in rows])
    k = min(k_max, len(X))
    rng = np.random.default_rng(seed)
    cent = X[rng.choice(len(X), size=k, replace=False)].copy()

    for _ in range(rounds):
        d = np.linalg.norm(X[:, None, :] - cent[None, :, :], axis=2)
        labels = d.argmin(axis=1)
        for j in range(k):
            members = X[labels == j]
            if len(members):
                cent[j] = members.mean(axis=0)

    conn = _connect()
    conn.executemany("UPDATE tracks SET cluster_id=? WHERE file_path=?",
                     [(int(l), p) for (p, _), l in zip(rows, labels)])
    conn.commit()
    conn.close()
    print(f"✅ Saved {len(rows)} cluster assignments ({k} clusters).")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:  # python scan.py "C:\path\to\music": remembered for the server too
        set_active_music_folder(os.path.abspath(sys.argv[1]))
    print(f"Music folder: {get_active_music_folder()}")
    run_scan()
    mel()
    clustering()
    try:
        embed_new()
    except ImportError:
        print("ℹ️ Skipping embeddings: run `pip install -r requirements-ml.txt` to enable them.")
    print("🚀 Pipeline complete.")
