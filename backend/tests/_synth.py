"""Synthetic library for tests: genres are directions in embedding space, 12 artists per genre."""
import sqlite3

import numpy as np


def make_library(db_path, n_genres=4, per_genre=60, dim=32, seed=0):
    rng = np.random.default_rng(seed)
    c = sqlite3.connect(db_path)
    c.execute("""CREATE TABLE IF NOT EXISTS tracks (id INTEGER PRIMARY KEY, file_path TEXT, title TEXT,
                 artist TEXT, album TEXT, genre TEXT, vector_data BLOB, cluster_id INTEGER, language TEXT,
                 embedding BLOB, embed_model TEXT)""")
    dirs = np.eye(dim)[:n_genres] * 4
    genre_of, tid = {}, 0
    for g in range(n_genres):
        for k in range(per_genre):
            tid += 1
            genre_of[tid] = g
            v = (rng.normal(0, 1, dim) + dirs[g]).astype(np.float32)
            c.execute("INSERT INTO tracks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (tid, f"s{tid}.mp3", f"Song {tid}", f"Artist{g}_{k % 12}", "Unknown", f"g{g}", None, g,
                       "Hindi" if g == 0 else "English", v.tobytes(), "synthetic"))
    c.commit()
    c.close()
    return genre_of
