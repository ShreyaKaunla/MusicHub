# MusicHub 🎵

Local music player with AI-powered mood-based playlists. Parses MP3 filenames (artist/title), attaches ML embeddings, and generates vibe-matched queues.

## Features
- Scan local music folders (drag/drop or file picker)
- Auto-parse artist/title from filenames (e.g., "Artist - Song.mp3")
- ML embeddings for mood similarity (cosine distance scoring)
- Spotify-style UI: bottom player bar, auto-playlists, artists/albums views
- Mood playlists: Chill, energetic, sad (from embeddings + heuristics)
- Local-only—no streaming, privacy-focused

## Tech Stack
- **Frontend**: HTML/CSS/JavaScript (Vanilla JS)
- **Key Files**:
  | File | Description |
  |------|-------------|
  | `index.html` | Main UI structure |
  | `style.css` | Spotify-inspired styling |
  | `app.js` | Core logic: scan, parse, embed matching, playlists |
  | `track_embeddings.json` | Pre-computed ML vectors for songs |
- **ML**: Embeddings (likely TensorFlow/Colab-generated), loaded client-side
- **Runs**: Browser-only (localhost), no server needed post-setup

## Quick Start
1. Open `index.html` in browser (Chrome/Firefox)
2. **Scan Folder**: Click file picker > select MP3s
3. Console logs: "✅ ML: song.mp3 → embedding"
4. Play track → Auto-generates mood playlist (vibe queue)

Demo: Local MP3s → Embed match → "Ishq Bulaava" → Similar chill tracks queue.

## Setup Embeddings
- Train in Colab (audio features → vectors)
- Export `track_embeddings.json` format:
