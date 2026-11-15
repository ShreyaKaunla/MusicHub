# 🎵 MusicHub

A local-first music player and recommender. MusicHub reads **your own** `.mp3` files, analyses how they sound with a
pretrained audio model (CLAP), and gives you a Spotify-style player with an endless "similar songs" queue, personalised
**For You** mixes, mood playlists, likes and custom playlists.

Everything runs on your computer: your music and listening history never leave it.

> **Try it instantly — no music files needed:** the hosted demo at **https://music-hub-demo.vercel.app** is seeded with
> demo songs and precomputed clusters, so you can explore the recommender without uploading anything. This repo is the
> local-first edition you run against your own library.

> **Desktop app:** run `build_desktop.bat` and `build_installer.bat` to produce `MusicHub-1.0.0-Setup.exe` — a regular
> Windows installer that friends can download and install. It scans their music folder, fingerprints every song and
> starts recommending out of the box.

---

## ✨ Features

**Player**
- Three-panel layout: your library on the left, the player in the middle, navigation on the right
- Previous, play/pause, next, like, and a seek bar you can drag
- Browse by album, artist, language or liked songs; search everywhere
- Pick your music folder from the app — new songs are picked up automatically

**Recommendations & For You**
- **✨ Recommended queue:** endless songs that sound like the one you're playing (audio-embedding similarity)
- **🏠 For You:** Daily Mixes, Discover, On Repeat and Rediscover shelves, unlocked after ~5 finished songs
- **🎭 Sort by mood:** auto-generated Happy / Sad / Soothing / Energetic / Motivational / Bollywood Party / Oldy playlists
- Likes, custom playlists, queue saving

---

## 🧠 How the recommender works

1. **CLAP audio embeddings** (LAION, trained on ~630k audio-text pairs): three 10-second clips per song → 512-dim
   vectors, L2-normalised. Two interchangeable inference backends produce the same vectors:
   - torch + transformers (dev machines), or
   - a bundled int8-quantised ONNX export (`backend/models/clap_audio_int8.onnx`) — no torch needed, ~50 MB
   - (a 128-value mel fingerprint is also stored as a fallback for corrupt/problematic files)
2. **K-Means** (from scratch, 20 clusters) over the fingerprints groups the library for cold-start "Explore".
3. **Similarity** = cosine over embeddings + small artist/genre/album bonuses; falls back to weighted
   mel-fingerprint distance when a song has no embedding.
4. **Taste profile:** listening events (play/complete/skip) + your likes decay over 14 days, are projected onto the
   embedding space, and drive the For You shelves with artist-diversity caps.
5. **Ranker (optional):** learns the feature weights from your own history once there's enough of it (`ranker.py`).

Re-generate the ONNX model on a dev machine with `python backend/export_clap_onnx.py` (needs torch + transformers).

---

## 🛠️ Tech stack

| Layer | Tools |
|---|---|
| Frontend | React, JavaScript (ES6+), Vite |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic |
| Audio / data | Librosa, NumPy, Mutagen, TinyTag, ONNX Runtime |
| Storage | SQLite3 |

---

## 📁 Project structure

```text
├── run.py                     # starts the backend on :8000
├── build_desktop.bat          # builds the UI + PyInstaller desktop bundle (dist\MusicHub)
├── build_installer.bat        # wraps the bundle into MusicHub-1.0.0-Setup.exe (Inno Setup)
├── installer.iss              # Inno Setup script
├── backend/
│   ├── main.py                # REST API: songs, streaming, covers, recommendations, playlists
│   ├── desktop_app.py         # desktop entry point (packaged app)
│   ├── scan.py                # folder scan, fingerprints, K-Means, embeddings orchestration
│   ├── embeddings.py          # CLAP embeddings (torch OR onnxruntime backends)
│   ├── clap_mel.py            # numpy-only mel front-end for the ONNX backend
│   ├── export_clap_onnx.py    # regenerates models/clap_audio_int8.onnx and verifies parity
│   ├── similarity.py / taste.py / ranker.py / extras.py / events.py / userdata.py / library.py
│   ├── MusicHub.spec          # PyInstaller spec
│   ├── models/clap_audio_int8.onnx
│   └── sql_db.db              # SQLite database (created automatically; not committed)
└── my-react-app/
    ├── dev.mjs                # `npm run dev` launcher: starts backend + Vite together
    ├── package.json
    └── src/ (App.jsx, …)
```

---

## ⚙️ Development setup

### Prerequisites
- Python **3.12** (`winget install Python.Python.3.12`) and Node.js 20+ (`winget install OpenJS.NodeJS.LTS`)
- FFmpeg recommended (fallback decoder for odd MP3s): `winget install Gyan.FFmpeg`

### One-time environment
```powershell
python -m venv build-env
build-env\Scripts\pip install -r backend\requirements.txt -r backend\requirements-ml.txt
```
(`requirements-ml.txt` = torch + transformers; without it the app runs with the mel-fingerprint recommender only.)

### Run it — one command
```cmd
cd my-react-app
npm install        (first time only)
npm run dev        → starts the Python backend AND the Vite dev server
```
Open **http://localhost:5173**. If a backend is already running on :8000 it is reused, not spawned twice.
You can also start the backend alone with `python run.py`.

### First use
1. Click **📁 Choose folder** and pick your music folder. The first scan fingerprints every song.
2. Play songs. After about five finished songs, **For You** unlocks your Daily Mixes.

Your library data lives next to the database (`backend/sql_db.db` in dev, `%LOCALAPPDATA%\MusicHub` for the installed app).

---

## 📦 Desktop build (for distribution)

```cmd
build_desktop.bat        → dist\MusicHub\MusicHub.exe   (green/portable folder)
build_installer.bat      → installer_output\MusicHub-1.0.0-Setup.exe
```
- The bundle includes the quantised ONNX CLAP model, so recommendations work with no extra downloads.
- The installed app stores data in `%LOCALAPPDATA%\MusicHub` and opens the UI in the default browser.
- `winget install JRSoftware.InnoSetup` is needed once for `build_installer.bat`.

---

## 🔌 API overview

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/songs` | All songs |
| GET | `/api/audio/{file}` | Stream a song (supports seeking) |
| GET | `/api/cover/{file}` | Cover art (embedded or generated placeholder) |
| POST | `/api/recommendations` | Similar songs for a track |
| POST | `/api/scan-folder` | Choose + scan a music folder |
| GET/POST | `/api/likes`, `/api/likes/{id}` | List likes / toggle a like |
| GET/POST/DELETE | `/api/user-playlists…` | Custom playlists |
| POST/GET | `/api/analyze-moods`, `/status` | Mood analysis |
| GET | `/api/home` | For You shelves |
| GET | `/api/library/status`, `/api/library/sync` | Auto-sync status / force a sync |
| GET | `/api/health` | Health check |

---

## ⚠️ Known limitations

- MP3 files only (`librosa` reads others, but the scanner looks for `.mp3`).
- A handful of corrupt MP3s can't be embedded; they still play and recommend via fingerprints.
- Mood sorting is a heuristic; use remove/move to correct it.

## License

Copyright (c) 2026 Shreya Kaunla - All Rights Reserved.

You may run MusicHub for personal use and read the code for learning.
Copying, redistributing, modifying, or any commercial use requires the
author's written permission - see [LICENSE](LICENSE).