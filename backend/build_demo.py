"""Builds the demo catalogue OFFLINE: scan -> fingerprints -> clusters -> CLAP embeddings -> mood playlists.

Usage:  python build_demo.py [path/to/demo_music]        (default: ./demo_music)
Needs the full toolchain:  pip install -r requirements-ml.txt
Output: demo_data/sql_db.db  <- commit it; the Docker image bakes it in next to demo_music/.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MUSIC = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "demo_music"
DATA = ROOT / "demo_data"
os.environ["MUSIC_DIR"] = str(MUSIC)   # must be set before config is imported
os.environ["DATA_DIR"] = str(DATA)


def main():
    if not MUSIC.is_dir() or not list(MUSIC.glob("*.mp3")):
        sys.exit(f"No .mp3 files in {MUSIC}. Put your Creative Commons tracks there first.")
    import sqlite3
    from config import DB_PATH
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)  # always a clean build; this folder holds only demo data
    from scan import ensure_schema_is_stable, run_scan, mel, clustering, embed_new
    from extras import ensure_extra_schema, _run_analysis, progress
    from identity import ensure_owner_schema

    ensure_schema_is_stable()
    ensure_extra_schema()
    run_scan()
    mel()
    clustering()
    embed_new()
    progress.update(running=True, done=0, total=0)
    _run_analysis()            # mood features + mood playlists
    ensure_owner_schema()

    c = sqlite3.connect(DB_PATH)
    for tid, p in c.execute("SELECT id, file_path FROM tracks").fetchall():  # portable: bare file names
        c.execute("UPDATE tracks SET file_path=? WHERE id=?", (os.path.basename(p.replace("\\", "/")), tid))
    c.commit()
    n = c.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    emb = c.execute("SELECT COUNT(*) FROM tracks WHERE embedding IS NOT NULL").fetchone()[0]
    moods = c.execute("""SELECT p.name, COUNT(pt.track_id) FROM user_playlists p
                         LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id
                         WHERE p.is_mood=1 GROUP BY p.id ORDER BY p.name""").fetchall()
    c.execute("VACUUM")
    c.close()

    mb = sum(f.stat().st_size for f in MUSIC.glob("*.mp3")) / 1e6
    print(f"\n=== Demo catalogue ===\n{n} songs, {emb} with embeddings, music folder {mb:.0f} MB")
    print("Mood playlists:", ", ".join(f"{m} ({k})" for m, k in moods))
    if emb < n:
        print(f"⚠️  {n - emb} songs have no embedding (corrupt files?). They fall back to the basic recommender.")
    if mb > 400:
        print("⚠️  Over 400 MB: consider prepare_demo.py to shrink the files, or removing some songs.")
    if not (ROOT / "LICENSES.md").exists():
        print("⚠️  No LICENSES.md: credit each artist/licence before publishing the demo.")
    print(f"Database: {DB_PATH}")


if __name__ == "__main__":
    main()
