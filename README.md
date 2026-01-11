# MusicHub 

Local music player with AI-powered mood-based playlists. Parses MP3 filenames (artist/title), attaches ML embeddings, and generates vibe-matched queues.

## Features
- Scan local music folders 
- Auto-parse artist/title from filenames 
- ML embeddings for mood similarity
- Spotify-style UI: bottom player bar, auto-playlists
- Mood playlists: Party, Chill, Romantic, Energetic
- Local-only, privacy-focused

## Tech Stack
Frontend: HTML/CSS/JS
Backend: Flask + librosa (tempo, energy, MFCC13)
Key Files: index.html, app.js, main.py, requirements.txt

## Quick Start
git clone https://github.com/ShreyaKaunla/MusicHub.git
cd MusicHub
pip install -r requirements.txt
python main.py
Live Server index.html

## ML Pipeline
MP3 → librosa features → Mood classifier → Similarity scoring → Radio queue

## Future Work
- Playlist Room (multi-user queue)
- Cloud deploy
- Real NN classifier

BTech CSE 3rd Year | PTU Mohali
