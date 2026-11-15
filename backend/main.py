import hashlib
import os
import urllib.parse
import sqlite3 as sql
from contextlib import asynccontextmanager
from typing import List

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
from pydantic import BaseModel

from config import DB_PATH, CORS_ORIGINS, get_active_music_folder, set_active_music_folder
from scan import ensure_schema_is_stable
from extras import router, ensure_extra_schema
from events import router as events_router, ensure_events_schema
import library
import similarity
import taste
from identity import ensure_owner_schema
from userdata import router as user_router


def _clean(name: str) -> str:
    """Bare file name from a URL part or a path of either OS."""
    return os.path.basename(urllib.parse.unquote(str(name)).replace("\\", "/"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_schema_is_stable()
        ensure_extra_schema()
        ensure_owner_schema()
        ensure_events_schema()
        library.adopt_folder_from_db()
        library.start_watcher()
        print("🎉 Web app server ready for incoming explicit folder requests!")
    except Exception as e:
        print(f"⚠️ Startup problem: {e}")
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(router)  # likes, playlist editing, mood sorting (from extras.py)
app.include_router(events_router)  # listening history (from events.py)
app.include_router(user_router)  # per-owner likes + playlists (from userdata.py)
app.include_router(library.router)  # auto-sync status + manual sync (from library.py)
app.include_router(taste.router)  # taste profile + auto playlists (from taste.py)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- folder scan
class FolderScanRequest(BaseModel):
    folder_name: str


@app.post("/api/scan-folder")
def client_trigger_scan(request: FolderScanRequest):
    name = request.folder_name
    target_path = name if os.path.isabs(name) else os.path.join(os.path.expanduser("~"), "Music", name)
    if not os.path.isdir(target_path):
        raise HTTPException(status_code=404, detail=f"Folder not found: {target_path}")
    set_active_music_folder(target_path)   # remembered across restarts
    print(f"✨ Music folder set to: {target_path}")
    started = library.start_sync()        # scan + fingerprints + clusters + embeddings, in the background
    return {"status": "started" if started else "already running",
            "message": "Syncing your library in the background; progress shows at the top."}


# (likes and playlists live in userdata.py)


# ---------------------------------------------------------------- recommender
def legacy_recommender(clean_target_name: str):
    conn = sql.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT file_path, cluster_id, vector_data, genre, album, artist
        FROM tracks WHERE file_path LIKE ?
    """, (f"%{clean_target_name}",))
    target = cursor.fetchone()

    if not target or target[0] is None or target[1] is None or target[2] is None:
        conn.close()
        return []

    target_path, target_cluster, target_bytes = target[0], target[1], target[2]
    target_genre, target_album, target_artist = target[3], target[4], target[5]

    target_vector = np.frombuffer(target_bytes, dtype=np.float32)
    # NOTE: the vector is 128 mel bands, so these slices are just three frequency ranges,
    # not real mel/chroma/centroid features. Step 2 (pretrained embeddings) replaces this.
    target_mel = target_vector[0:64]
    target_chroma = target_vector[64:96]
    target_centroid = target_vector[96:128]

    cursor.execute("""
        SELECT file_path, vector_data, genre, album, artist
        FROM tracks
        WHERE file_path != ? AND cluster_id = ? AND vector_data IS NOT NULL
    """, (target_path, target_cluster))
    neighborhood = cursor.fetchall()
    conn.close()

    matches = []
    for path, vec_bytes, genre, album, artist in neighborhood:
        vec = np.frombuffer(vec_bytes, dtype=np.float32)
        if vec.shape != target_vector.shape:
            continue
        dist_mel = np.sqrt(np.sum((target_mel - vec[0:64]) ** 2))
        dist_chroma = np.sqrt(np.sum((target_chroma - vec[64:96]) ** 2))
        dist_centroid = np.sqrt(np.sum((target_centroid - vec[96:128]) ** 2))
        acoustic_score = 0.50 * dist_mel + 0.30 * dist_chroma + 0.20 * dist_centroid

        meta_multiplier = 1.0
        if genre == target_genre and target_genre not in [None, "unknown", "Unknown"]:
            meta_multiplier *= 0.85
        if artist == target_artist and target_artist not in [None, "unknown", "Unknown"]:
            meta_multiplier *= 0.85
        if album == target_album and target_album not in [None, "unknown", "Unknown"]:
            meta_multiplier *= 0.85
        matches.append({"path": path, "score": acoustic_score * meta_multiplier})

    matches = sorted(matches, key=lambda x: x["score"])
    return matches[:10]


def recommender(clean_target_name: str):
    """Pretrained-embedding similarity when available, else the legacy mel/cluster method."""
    try:
        results = similarity.similar(clean_target_name, 10)
        if results:
            return results
    except Exception as e:
        print(f"Embedding recommender failed, using legacy: {e}")
    return legacy_recommender(clean_target_name)


class RecommendationRequest(BaseModel):
    file_path: str


@app.post("/api/recommendations")
def get_music_recommendations(request: RecommendationRequest):
    clean_target_name = _clean(request.file_path)
    try:
        raw_results = recommender(clean_target_name)
        formatted = []
        for rank, track in enumerate(raw_results, start=1):
            formatted.append({
                "rank": rank,
                "file_name": os.path.basename(track["path"]),
                "full_path": track["path"],
                "score": float(track["score"]),
            })
        return {"status": "success", "sdata": formatted, "recommendations": formatted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation engine error: {str(e)}")


# ---------------------------------------------------------------- songs, audio, covers
@app.get("/api/songs")
def get_all_songs():
    conn = sql.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, file_path, title, artist, album, language FROM tracks")
        rows = cursor.fetchall()
    except sql.OperationalError:
        try:  # older database without the language column
            cursor.execute("SELECT id, file_path, title, artist, album, NULL FROM tracks")
            rows = cursor.fetchall()
        except sql.OperationalError:
            conn.close()
            return []
    conn.close()
    return [{"id": r[0], "file_path": r[1], "title": r[2], "artist": r[3],
             "album": r[4], "language": r[5] or "Unknown"} for r in rows]


@app.get("/api/audio/{filename:path}")
def stream_audio(filename: str, request: Request):
    clean_name = _clean(filename)
    full_audio_path = os.path.join(get_active_music_folder(), clean_name)
    if not os.path.exists(full_audio_path):
        raise HTTPException(status_code=404, detail=f"Audio file not found: {clean_name}")

    size = os.path.getsize(full_audio_path)
    headers = {"Accept-Ranges": "bytes"}
    rng = request.headers.get("range")
    if rng and rng.startswith("bytes="):
        # Browsers ask for a byte range when you drag the seek bar
        start_s, _, end_s = rng[6:].partition("-")
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else min(start + 4 * 1024 * 1024 - 1, size - 1)
        end = min(end, size - 1)
        if start >= size or start > end:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        with open(full_audio_path, "rb") as f:
            f.seek(start)
            data = f.read(end - start + 1)
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        return Response(content=data, status_code=206, media_type="audio/mpeg", headers=headers)
    return FileResponse(full_audio_path, media_type="audio/mpeg", headers=headers)


def _placeholder_cover(name: str) -> Response:
    """Songs without embedded artwork get a generated gradient cover, colour picked from the file name."""
    h = hashlib.md5(name.encode("utf-8", "ignore")).digest()
    hue1, hue2 = h[0] * 360 // 256, (h[0] * 360 // 256 + 40 + h[1] % 60) % 360
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">'
           '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
           f'<stop offset="0" stop-color="hsl({hue1},55%,38%)"/>'
           f'<stop offset="1" stop-color="hsl({hue2},60%,22%)"/></linearGradient></defs>'
           '<rect width="200" height="200" fill="url(#g)"/>'
           '<text x="100" y="125" font-size="90" text-anchor="middle" fill="rgba(255,255,255,.55)" '
           'font-family="Segoe UI Symbol,Arial,sans-serif">&#9834;</text></svg>')
    return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/cover/{filename:path}")
def get_cover_art(filename: str):
    clean_name = _clean(filename)
    full_audio_path = os.path.join(get_active_music_folder(), clean_name)
    if not os.path.exists(full_audio_path):
        return _placeholder_cover(clean_name)
    try:
        audio = MP3(full_audio_path, ID3=ID3)
        if audio.tags:
            for tag in audio.tags.values():
                if isinstance(tag, APIC):
                    return Response(content=tag.data, media_type=tag.mime)
    except Exception as e:
        print(f"Cover extraction skipped for {filename}: {e}")
    return _placeholder_cover(clean_name)


# ---------------------------------------------------------------- health + client config
@app.get("/api/health")
def health():
    return {"status": "ok"}


# ------------------------------------------------------------------ packaged UI (built by build_web.bat)
from pathlib import Path

from fastapi.staticfiles import StaticFiles

_WEB = Path(__file__).resolve().parent / "web"
if _WEB.is_dir():  # dev mode has no web/ folder and serves the UI from Vite instead
    app.mount("/", StaticFiles(directory=_WEB, html=True), name="web")