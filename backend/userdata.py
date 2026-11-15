"""Per-owner likes and playlists (moved out of main.py/extras.py so ownership is enforced in one place)."""
import os
import sqlite3 as sql
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from config import DB_PATH
from identity import owner

router = APIRouter()
MAX_IDS = 2000


def _db():
    return sql.connect(DB_PATH, timeout=30)


def _base(path):
    return os.path.basename(str(path).replace("\\", "/"))


def _check_name(name):
    name = (name or "").strip()
    if not name or len(name) > 80:
        raise HTTPException(400, "Playlist name must be 1-80 characters.")
    return name


def _playlist(cur, pid, who, edit=False):
    """Returns is_mood. 404 if it isn't visible to `who`; 403 if visible but read-only."""
    row = cur.execute("SELECT owner, is_mood FROM user_playlists WHERE id=?", (pid,)).fetchone()
    if not row or row[0] not in ("", who):
        raise HTTPException(404, "Playlist not found")
    if edit and row[0] != who and not row[1]:  # auto-generated mood playlists are read-only
        raise HTTPException(403, "This playlist is read-only")
    return bool(row[1])


# ------------------------------------------------------------------ likes
@router.get("/api/likes")
def get_likes(x_client_id: Optional[str] = Header(default=None)):
    who = owner(x_client_id)
    c = _db()
    rows = c.execute("SELECT track_id FROM likes WHERE owner=?", (who,)).fetchall()
    c.close()
    return [r[0] for r in rows]


@router.post("/api/likes/{track_id}")
def toggle_like(track_id: int, x_client_id: Optional[str] = Header(default=None)):
    who = owner(x_client_id)
    c = _db()
    cur = c.cursor()
    if cur.execute("SELECT 1 FROM likes WHERE owner=? AND track_id=?", (who, track_id)).fetchone():
        cur.execute("DELETE FROM likes WHERE owner=? AND track_id=?", (who, track_id))
        liked = False
    else:
        cur.execute("INSERT INTO likes (owner, track_id) VALUES (?,?)", (who, track_id))
        liked = True
    c.commit()
    c.close()
    return {"liked": liked}


# ------------------------------------------------------------------ playlists
class IdsReq(BaseModel):
    track_ids: List[int]


class CreateManualPlaylistRequest(BaseModel):
    playlist_name: str
    track_ids: List[int]


class SaveQueueRequest(BaseModel):
    playlist_name: str
    track_paths: List[str]


@router.get("/api/user-playlists")
def list_playlists(x_client_id: Optional[str] = Header(default=None)):
    who = owner(x_client_id)
    c = _db()
    rows = c.execute("SELECT id, name, is_mood FROM user_playlists WHERE owner IN ('', ?) "
                     "ORDER BY is_mood DESC, name", (who,)).fetchall()
    c.close()
    return [{"id": r[0], "name": r[1], "is_mood": bool(r[2])} for r in rows]


@router.post("/api/user-playlists/manual")
def create_manual_playlist(request: CreateManualPlaylistRequest, x_client_id: Optional[str] = Header(default=None)):
    who = owner(x_client_id)
    name = _check_name(request.playlist_name)
    c = _db()
    cur = c.cursor()
    try:
        valid = {r[0] for r in cur.execute("SELECT id FROM tracks")}
        ids = [t for t in dict.fromkeys(request.track_ids) if t in valid][:MAX_IDS]
        cur.execute("INSERT INTO user_playlists (name, owner) VALUES (?, ?)", (name, who))
        pid = cur.lastrowid
        cur.executemany("INSERT INTO playlist_tracks (playlist_id, track_id) VALUES (?, ?)", [(pid, t) for t in ids])
        c.commit()
        return {"status": "success", "id": pid}
    except sql.IntegrityError:
        raise HTTPException(400, "A playlist with that exact name already exists.")
    finally:
        c.close()


@router.post("/api/user-playlists/snapshot")
def snapshot_ai_queue(request: SaveQueueRequest, x_client_id: Optional[str] = Header(default=None)):
    who = owner(x_client_id)
    name = _check_name(request.playlist_name)
    if len(request.track_paths) < 1:
        raise HTTPException(400, "The queue is empty.")
    c = _db()
    cur = c.cursor()
    try:
        by_name = {_base(p): i for i, p in cur.execute("SELECT id, file_path FROM tracks")}
        ids = [by_name[n] for n in dict.fromkeys(_base(p) for p in request.track_paths[:MAX_IDS]) if n in by_name]
        row = cur.execute("SELECT id FROM user_playlists WHERE owner=? AND name=?", (who, name)).fetchone()
        if row:
            pid = row[0]
        else:
            cur.execute("INSERT INTO user_playlists (name, owner) VALUES (?, ?)", (name, who))
            pid = cur.lastrowid
        have = {r[0] for r in cur.execute("SELECT track_id FROM playlist_tracks WHERE playlist_id=?", (pid,))}
        cur.executemany("INSERT INTO playlist_tracks (playlist_id, track_id) VALUES (?, ?)",
                        [(pid, t) for t in ids if t not in have])
        c.commit()
        return {"status": "success", "message": f"Saved queue into '{name}'"}
    finally:
        c.close()


@router.get("/api/user-playlists/{pid}/tracks")
def get_playlist_tracks(pid: int, x_client_id: Optional[str] = Header(default=None)):
    who = owner(x_client_id)
    c = _db()
    cur = c.cursor()
    try:
        _playlist(cur, pid, who)
        rows = cur.execute("""SELECT t.id, t.file_path, t.title, t.artist, t.album, t.genre FROM tracks t
                              JOIN playlist_tracks pt ON t.id = pt.track_id
                              WHERE pt.playlist_id = ? ORDER BY pt.rowid""", (pid,)).fetchall()
    finally:
        c.close()
    return [{"id": r[0], "file_path": r[1], "title": r[2], "artist": r[3], "album": r[4], "genre": r[5]} for r in rows]


@router.post("/api/user-playlists/{pid}/tracks")
def add_tracks(pid: int, req: IdsReq, x_client_id: Optional[str] = Header(default=None)):
    who = owner(x_client_id)
    c = _db()
    cur = c.cursor()
    try:
        _playlist(cur, pid, who, edit=True)
        valid = {r[0] for r in cur.execute("SELECT id FROM tracks")}
        have = {r[0] for r in cur.execute("SELECT track_id FROM playlist_tracks WHERE playlist_id=?", (pid,))}
        for t in dict.fromkeys(req.track_ids[:MAX_IDS]):
            if t in valid and t not in have:
                cur.execute("INSERT INTO playlist_tracks (playlist_id, track_id, auto) VALUES (?,?,0)", (pid, t))
            cur.execute("DELETE FROM mood_removed WHERE playlist_id=? AND track_id=?", (pid, t))
        c.commit()
    finally:
        c.close()
    return {"status": "success"}


@router.delete("/api/user-playlists/{pid}/tracks/{tid}")
def remove_track(pid: int, tid: int, x_client_id: Optional[str] = Header(default=None)):
    who = owner(x_client_id)
    c = _db()
    cur = c.cursor()
    try:
        is_mood = _playlist(cur, pid, who, edit=True)
        cur.execute("DELETE FROM playlist_tracks WHERE playlist_id=? AND track_id=?", (pid, tid))
        if is_mood:  # remember removals so re-sorting never puts the song back
            cur.execute("INSERT OR IGNORE INTO mood_removed VALUES (?,?)", (pid, tid))
        c.commit()
    finally:
        c.close()
    return {"status": "success"}


@router.delete("/api/user-playlists/{pid}")
def delete_playlist(pid: int, x_client_id: Optional[str] = Header(default=None)):
    who = owner(x_client_id)
    c = _db()
    cur = c.cursor()
    try:
        if _playlist(cur, pid, who, edit=True):
            raise HTTPException(400, "Mood playlists can't be deleted")
        cur.execute("DELETE FROM playlist_tracks WHERE playlist_id=?", (pid,))
        cur.execute("DELETE FROM user_playlists WHERE id=?", (pid,))
        c.commit()
    finally:
        c.close()
    return {"status": "success"}
