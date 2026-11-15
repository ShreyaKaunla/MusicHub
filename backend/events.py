"""Listening history. Events feed the taste profile for the "For You" home screen.

Events: play, skip, complete, like, unlike
`seconds` = how long the song was actually listened to (used to tell a skip from a real listen).
"""
import sqlite3 as sql
import time
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from config import DB_PATH
from identity import owner

router = APIRouter()
EVENT_TYPES = {"play", "skip", "complete", "like", "unlike"}
MAX_EVENTS_PER_OWNER = 20000  # safety valve against runaway event logging


def _db():
    return sql.connect(DB_PATH, timeout=30)


def ensure_events_schema():
    c = _db()
    c.execute("""CREATE TABLE IF NOT EXISTS listen_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id TEXT NOT NULL,
        track_id INTEGER NOT NULL,
        event TEXT NOT NULL,
        seconds REAL DEFAULT 0,
        ts REAL NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_events_client_ts ON listen_events (client_id, ts)")
    c.execute("PRAGMA journal_mode=WAL")  # many small writes from several visitors
    c.commit()
    c.close()


class EventReq(BaseModel):
    track_id: int
    event: str
    seconds: float = Field(default=0, ge=0, le=36000)


@router.post("/api/events")
def log_event(req: EventReq, x_client_id: Optional[str] = Header(default=None)):
    who = owner(x_client_id)
    if req.event not in EVENT_TYPES:
        raise HTTPException(400, f"event must be one of {sorted(EVENT_TYPES)}")
    c = _db()
    if c.execute("SELECT COUNT(*) FROM listen_events WHERE client_id=?", (who,)).fetchone()[0] >= MAX_EVENTS_PER_OWNER:
        c.close()
        raise HTTPException(429, "Event limit reached for this visitor")
    c.execute("INSERT INTO listen_events (client_id, track_id, event, seconds, ts) VALUES (?,?,?,?,?)",
              (who, req.track_id, req.event, req.seconds, time.time()))
    c.commit()
    c.close()
    return {"status": "ok"}


@router.get("/api/events/summary")
def events_summary(x_client_id: Optional[str] = Header(default=None)):
    """How many events this visitor has: the UI uses it for 'keep listening to unlock your mixes'."""
    who = owner(x_client_id)
    c = _db()
    rows = c.execute("SELECT event, COUNT(*) FROM listen_events WHERE client_id=? GROUP BY event",
                     (who,)).fetchall()
    c.close()
    counts = {e: n for e, n in rows}
    return {"counts": counts, "total": sum(counts.values())}
