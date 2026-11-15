"""Ownership: this is a desktop build, so everything belongs to one person, owner "local".

Also handles the one-time migration to per-owner data (idempotent).
"""
import sqlite3 as sql

from config import DB_PATH

LOCAL = "local"


def owner(_x_client_id=None):
    return LOCAL


def ensure_owner_schema():
    """Idempotent. Rebuilds user_playlists with an owner column and moves likes to a per-owner table."""
    c = sql.connect(DB_PATH, timeout=30)
    cur = c.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(user_playlists)")]
    if cols and "owner" not in cols:
        mood = "is_mood" if "is_mood" in cols else "0"
        cur.execute("""CREATE TABLE user_playlists_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            owner TEXT NOT NULL DEFAULT '', is_mood INTEGER DEFAULT 0, UNIQUE(owner, name))""")
        cur.execute(f"""INSERT INTO user_playlists_new (id, name, owner, is_mood)
                        SELECT id, name, CASE WHEN {mood}=1 THEN '' ELSE ? END, {mood} FROM user_playlists""",
                    (LOCAL,))
        cur.execute("DROP TABLE user_playlists")
        cur.execute("ALTER TABLE user_playlists_new RENAME TO user_playlists")

    cur.execute("CREATE TABLE IF NOT EXISTS likes (owner TEXT NOT NULL, track_id INTEGER NOT NULL, "
                "PRIMARY KEY (owner, track_id))")
    if cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='liked_tracks'").fetchone():
        cur.execute("INSERT OR IGNORE INTO likes (owner, track_id) SELECT ?, track_id FROM liked_tracks", (LOCAL,))
        cur.execute("ALTER TABLE liked_tracks RENAME TO liked_tracks_migrated")  # kept as a backup

    if cur.execute("SELECT 1 FROM sqlite_master WHERE name='listen_events'").fetchone():
        cur.execute("UPDATE listen_events SET client_id=? WHERE client_id<>?", (LOCAL, LOCAL))
    c.commit()
    c.close()
