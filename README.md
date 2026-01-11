# MusicHub 🎵

**Local music player with AI-powered mood-based playlists.** Parses MP3 filenames (artist/title), attaches ML embeddings, and generates vibe-matched queues.

## Features
- **📁 Scan local music folders** (drag/drop or file picker)
- **Auto-parse artist/title** from filenames (e.g., "Artist - Song.mp3")
- **ML embeddings for mood similarity** (cosine distance scoring)
- **Spotify-style UI**: bottom player bar, auto-playlists, artists/albums views
- **Mood playlists**: Party, Chill, Romantic, Energetic (from embeddings + heuristics)
- **Local-only**—no streaming, privacy-focused
- **Playlist Room** (upcoming): Shared queue mode for collaborative sessions

## Tech Stack
Frontend: HTML/CSS/JS (Vanilla)
Backend: Flask + librosa (tempo, energy, MFCC13, Chroma, ZCR)
ML Pipeline: Audio → Features → Rule Classifier → Similarity Scoring
Key Files:
├── index.html UI Structure
├── app.js Scan + Embed Matching + Radio Queue
├── main.py Flask API (/embed endpoint)
├── requirements.txt
└── style.css Spotify-inspired

**Live Demo**: Backend `python main.py` → Frontend Live Server `index.html`

## 🚀 Quick Start
```
git clone https://github.com/ShreyaKaunla/MusicHub.git
cd MusicHub

pip install -r requirements.txt
python main.py          # Backend: localhost:8000

# Frontend: VS Code → index.html → Open with Live Server
```

**Flow**: Scan folder → Auto mood playlists!

## 🧠 ML Pipeline
MP3 File → librosa.load() → Features (tempo, RMS, MFCC13)

↓
Rule Classifier:
  tempo>130 | energy>0.15 → party
  tempo<105 | energy<0.12 → chill  
  105≤tempo≤125 | energy<0.14 → romantic
  
↓
Frontend: mood*cosine + tempo_bucket + artist_bonus - repeat_penalty

↓
Radio Queue (20 songs, YouTube-style diversity)

## Future Work
**Playlist Room**: Multi-user shared queue (WebSocket sync)
**Cloud deploy (Render/Vercel)**
**Real NN classifier (train on Spotify dataset)**

##BTech CSE 3rd Year | PTU Mohali | Full-stack ML project
