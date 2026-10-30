"""Finishes the demo build WITHOUT the mood analysis (which crashed on this machine).
Run from the backend folder, after build_demo.py got through the embeddings:
    python finish_demo.py
"""
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MUSIC = ROOT / "demo_music"
DATA = ROOT / "demo_data"
os.environ["MUSIC_DIR"] = str(MUSIC)   # must be set before config is imported
os.environ["DATA_DIR"] = str(DATA)

from config import DB_PATH
from extras import ensure_extra_schema
from identity import ensure_owner_schema

if not os.path.exists(DB_PATH):
    raise SystemExit(f"{DB_PATH} not found. Run build_demo.py first.")

ensure_extra_schema()
ensure_owner_schema()

c = sqlite3.connect(DB_PATH)
for tid, p in c.execute("SELECT id, file_path FROM tracks").fetchall():  # portable: bare file names
    c.execute("UPDATE tracks SET file_path=? WHERE id=?", (os.path.basename(p.replace("\\", "/")), tid))
c.commit()
n = c.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
emb = c.execute("SELECT COUNT(*) FROM tracks WHERE embedding IS NOT NULL").fetchone()[0]
sample = c.execute("SELECT file_path FROM tracks LIMIT 3").fetchall()
missing = [f for (f,) in c.execute("SELECT file_path FROM tracks") if not (MUSIC / f).exists()]
c.execute("VACUUM")
c.close()

print(f"\n=== Demo catalogue ===\n{n} songs, {emb} with embeddings")
print("Sample paths:", [s[0] for s in sample])
print("Files missing from demo_music:", missing or "none")
print(f"Database: {DB_PATH}")
