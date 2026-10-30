"""Precision@k: how often are a song's top-k neighbours in the same genre?

Run:  python evaluate.py          (needs both fingerprints and embeddings in the DB)

Fairness choices:
 - Genre-bonus/artist-bonus are NOT used here (they would leak the labels).
 - Neighbours by the SAME ARTIST are excluded, otherwise "same artist" inflates the score.
 - Only genres with >= 6 tracks are scored; 'Unknown' is skipped.
 - A standardised-mel baseline is included so the gain isn't just from a better distance function.
"""
import re
import sqlite3 as sql
import sys
from collections import Counter

import numpy as np

from config import DB_PATH

K = 5


def norm_genre(g):
    if not g:
        return None
    g = re.split(r"[;/,]", str(g))[0].strip().lower()
    return None if g in ("", "unknown") or g.isdigit() or g.startswith("(") else g


def _scores(X, kind):
    if kind == "cosine":
        Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
        return Xn @ Xn.T
    sq = (X ** 2).sum(1)
    return -(sq[:, None] + sq[None, :] - 2 * X @ X.T)  # negative squared euclidean


def precision_at_k(X, genres, artists, k=K, kind="cosine", min_genre=6, rng=None):
    S = rng.random((len(X), len(X))) if kind == "random" else _scores(X, kind)
    counts = Counter(g for g in genres if g)
    ok = [i for i, g in enumerate(genres) if g and counts[g] >= min_genre]
    hits = []
    for i in ok:
        row = S[i].copy()
        row[i] = -np.inf
        same_artist = np.array([artists[j] == artists[i] and artists[i] not in (None, "Unknown Artist")
                                for j in range(len(X))])
        row[same_artist] = -np.inf
        if np.isfinite(row).sum() < k:  # too few eligible neighbours after exclusions
            continue
        top = np.argpartition(-row, k)[:k]
        hits.append(np.mean([genres[j] == genres[i] for j in top]))
    return float(np.mean(hits)) if hits else float("nan"), len(ok)


def main():
    c = sql.connect(DB_PATH)
    rows = c.execute("SELECT genre, artist, vector_data, embedding FROM tracks "
                     "WHERE vector_data IS NOT NULL AND embedding IS NOT NULL").fetchall()
    c.close()
    if len(rows) < 30:
        sys.exit("Need at least ~30 tracks with both fingerprints and embeddings. Run: python scan.py")
    genres = [norm_genre(r[0]) for r in rows]
    artists = [r[1] for r in rows]
    mel = np.stack([np.frombuffer(r[2], dtype=np.float32) for r in rows])
    emb = np.stack([np.frombuffer(r[3], dtype=np.float32) for r in rows])
    mel_std = (mel - mel.mean(0)) / (mel.std(0) + 1e-9)
    rng = np.random.default_rng(0)

    table = [
        ("Random", precision_at_k(None if False else mel, genres, artists, kind="random", rng=rng)),
        ("Mel fingerprint, euclidean (current)", precision_at_k(mel, genres, artists, kind="euclid")),
        ("Mel fingerprint, standardised + cosine", precision_at_k(mel_std, genres, artists, kind="cosine")),
        ("CLAP embedding, cosine (new)", precision_at_k(emb, genres, artists, kind="cosine")),
    ]
    n = table[0][1][1]
    out = [f"Precision@{K} for same-genre neighbours ({n} scored songs, same-artist excluded)\n",
           "| Method | Precision@5 |", "|---|---|"]
    out += [f"| {name} | {p:.3f} |" for name, (p, _) in table]
    text = "\n".join(out)
    print(text)
    open("eval_results.md", "w", encoding="utf-8").write(text + "\n")
    print("\nSaved to eval_results.md")


if __name__ == "__main__":
    main()
