# 🎵 MusicHub

A full-stack local music player and recommender. MusicHub reads your own `.mp3` files, analyses the audio, and gives you a Spotify-style player with an endless "similar songs" queue, mood playlists, likes and custom playlists.

---

## ✨ Features

**Player**
- Three-panel layout: your library on the left, the player in the middle, navigation on the right
- Click any song title to play it; long titles scroll across the screen
- Previous, play/pause, next, like, and a seek bar you can drag
- Quick-jump icons under the seek bar: album, artist, language, create playlist, likes (labels appear on hover)

**Queue**
- **✨ Recommended:** an endless queue built from songs that sound like the current one. It refills itself as you listen.
- **📋 Normal:** plays the list you started from (all songs, an album, a playlist…)
- Save the current queue as a playlist

**Library**
- Browse by album, artist, language or liked songs
- Search bar above every list
- Pick a music folder from the app and scan it

**Playlists**
- Mood playlists generated automatically: Happy, Sad, Soothing, Energetic, Motivational, Bollywood Party, Oldy
- Your own playlists: create from a song picker, add songs, remove songs, move songs between playlists, delete playlists
- Corrections you make to mood playlists are remembered when you re-sort

---

## 🧠 How it works

**Recommendations**
1. Each song is turned into a 128-value audio fingerprint (average log-mel spectrogram, computed with `librosa`).
2. Songs are grouped into up to 20 clusters with a K-Means implementation written from scratch (15 rounds).
3. Recommendations come from the current song's cluster, ranked by weighted distance, with a small bonus for matching genre, artist or album.

**Mood sorting** (🎭 Sort by mood)
- Analyses a 20-second clip of each song for tempo, loudness, brightness, rhythmic activity and major/minor key
- Runs on several CPU cores in the background, with a progress counter
- Scores are ranked within your own library, then rules assign songs to moods
- *Bollywood Party* and *Oldy* also use tags (genre, title, language, release year)
- This is a heuristic, not a trained model. Use remove/move to correct it.

---

## 🛠️ Tech stack

| Layer | Tools |
|---|---|
| Frontend | React, JavaScript (ES6+), Vite |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic |
| Audio / data | Librosa, NumPy, Mutagen, TinyTag |
| Storage | SQLite3 |

---

## 📁 Project structure

```text
├── main.py          # REST API: songs, audio streaming (with seeking), covers, recommendations, playlists
├── extras.py        # Likes, playlist editing, mood analysis and sorting
├── scan.py          # Folder scan, audio fingerprints, K-Means clustering
├── sql_db.db        # SQLite database (created automatically)
├── requirements.txt # Python dependencies
└── my-react-app/
    └── src/
        ├── App.jsx    # Player, library, playlists and queue
        ├── index.css  # Global styles
        └── main.jsx   # React entry point
```

---

## 📦 Python dependencies

All listed in `requirements.txt`:

| Package | Used for |
|---|---|
| `fastapi`, `uvicorn`, `pydantic` | REST API and server |
| `numpy`, `librosa` | Audio fingerprints, tempo, key and loudness analysis (`librosa` also installs `soundfile` and `numba`) |
| `mutagen` | Cover art from MP3 files |
| `tinytag` | Title, artist, album, genre and year tags |

---

## ⚙️ Setup

### Prerequisites
- Python **3.10 or newer** and Node.js (Python 3.12 is the most widely tested choice)
- **FFmpeg** (recommended: a fallback for MP3 files that `librosa` can't decode on its own)
  - Windows: `winget install Gyan.FFmpeg`
  - macOS: `brew install ffmpeg`

### 1. Backend (Windows PowerShell)
```powershell
python -m venv .env
.env\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```
The API runs on **http://127.0.0.1:8000**, which is the address the frontend expects.

- If PowerShell blocks the activation script, run `Set-ExecutionPolicy -Scope Process Bypass` first, then activate again.
- macOS / Linux: use `python3 -m venv .env`, then `source .env/bin/activate`.
- Add `.env/` to your `.gitignore` so the virtual environment isn't committed.

### 2. Frontend
```cmd
cd my-react-app
npm install
npm run dev
```
Open **http://localhost:5173**.

### 3. First use
1. Click **📁 Choose folder** and pick your music folder. It must be inside your `Music` folder. The first scan can take a while because every song is fingerprinted.
2. Click **🎭 Sort by mood** to fill the mood playlists.
3. Click any song to start playing.

---

## 🔌 API overview

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/songs` | All songs |
| GET | `/api/audio/{file}` | Stream a song (supports seeking) |
| GET | `/api/cover/{file}` | Cover art |
| POST | `/api/recommendations` | Similar songs for a track |
| POST | `/api/scan-folder` | Scan and fingerprint a folder |
| GET / POST | `/api/likes`, `/api/likes/{id}` | List likes / toggle a like |
| GET | `/api/user-playlists` | List playlists |
| POST | `/api/user-playlists/manual` | Create a playlist from chosen songs |
| POST | `/api/user-playlists/snapshot` | Save the current queue as a playlist |
| GET / POST | `/api/user-playlists/{id}/tracks` | List / add songs |
| DELETE | `/api/user-playlists/{id}/tracks/{track}` | Remove a song |
| DELETE | `/api/user-playlists/{id}` | Delete a playlist |
| POST | `/api/analyze-moods` | Start mood analysis |
| GET | `/api/analyze-moods/status` | Mood analysis progress |

---

## ⚠️ Known limitations

- The chosen music folder must be inside the user's `Music` directory.
- Language comes from the MP3's `TLAN` tag, so songs without it show as "Unknown".
- Every folder scan re-fingerprints the whole library.
- Recommendations compare how songs sound; they don't yet learn from what you play or skip.
- Mood sorting is approximate.

---

## 🗺️ Ideas for next steps

- Learn from listening behaviour (plays, skips, likes) to personalise the queue
- Language labels per artist
- Learn mood corrections from the songs you add and remove