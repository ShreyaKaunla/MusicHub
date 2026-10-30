# Deploying MusicHub (public demo)

Frontend on **Vercel**, backend on **Render** (Docker, free plan). The demo library is ~50-80
Creative Commons songs baked into the image with a **precomputed** database, so the server only
serves audio and runs NumPy lookups (no librosa/torch on the host).

Assumed repo layout:
```
repo-root/
├── render.yaml            <- from this package
├── .gitignore             <- merge the lines from this package's .gitignore
├── backend/               <- all the .py files, Dockerfile, .dockerignore, requirements*.txt, tests/
│   ├── demo_music/        <- the Creative Commons .mp3 files (committed)
│   ├── demo_data/         <- sql_db.db built by build_demo.py (committed)
│   └── LICENSES.md        <- artist, title, licence, source URL for every song
└── my-react-app/
```

## 1. Collect the songs (you, ~1 hour)
Download 50-80 tracks from Jamendo or the Free Music Archive. Prefer **CC0 / CC BY / CC BY-SA**;
skip NonCommercial and NoDerivs. Put them in `backend/demo_music_src/` and note each licence in
`backend/LICENSES.md`. **Never put your personal music here: everything in `demo_music/` is public.**

## 2. Shrink them (optional but recommended)
```cmd
python prepare_demo.py demo_music_src demo_music
```
90 s at 96 kbps mono, about 1 MB each. Skip it if you want full-length songs and your repo can take
the size (GitHub blocks single files over 100 MB; keep the total under ~500 MB).

## 3. Build the catalogue (offline, once)
```cmd
pip install -r requirements-ml.txt
python build_demo.py
```
Prints a summary (songs, embeddings, mood playlist sizes). Re-run it whenever you change the songs.

## 4. Test locally with Docker (if installed)
```cmd
docker build -t musichub-api .
docker run -p 8000:8000 -e CORS_ORIGINS=http://localhost:5173 musichub-api
```
Open http://localhost:8000/api/health (should say ok) and http://localhost:8000/api/songs.
Then in `my-react-app`: `set VITE_API_URL=http://localhost:8000` and `npm run dev`.

## 5. Push to GitHub
Check `git status` first: **no personal `.mp3` files and no personal `sql_db.db`**.
```cmd
git add . && git commit -m "Deployable demo" && git push
```

## 6. Backend on Render
New > **Blueprint** > pick the repo (it reads `render.yaml`). Free plan. After the first deploy copy
the URL, e.g. `https://musichub-api.onrender.com`. Check `/api/health`.

## 7. Frontend on Vercel
Import the repo. Root directory `my-react-app`, framework Vite. Add the environment variable
`VITE_API_URL = https://musichub-api.onrender.com` (no trailing slash). Deploy, copy the URL.

## 8. Allow the frontend to call the backend
Render > the service > Environment: `CORS_ORIGINS = https://your-app.vercel.app`
(optional `CORS_ORIGIN_REGEX = https://your-app.*\.vercel\.app` for preview URLs). It redeploys.

## 9. Verify (use a private window as a second visitor)
- First load after idle shows "Waking up the demo server..." for up to a minute: normal on the free plan.
- Songs play, seeking works, covers load, Recommended queue fills.
- Finish ~5 songs, open **For You**: Daily Mixes appear. Like a song and create a playlist.
- In a different browser or private window: your likes and playlists must NOT be there.
- 🎭 Sort by mood and 📁 Choose folder buttons should be hidden.

## Known limits (say them in your README)
- **Visitor data is not durable.** The free plan has no persistent disk, so likes, playlists and
  history reset when the server restarts or redeploys. Fine for a demo; a real product would use
  Postgres (Neon/Supabase free tiers).
- The layout is desktop-first (three fixed columns); phones are not optimised yet.
- Taste profiles need ~5 finished songs, and the learned ranker needs 100+ finish/skip events, so a
  short demo visit uses the hand-tuned weights. The ranker is for the desktop build with real history.

## Put on your portfolio / README
Live link, a 20-second GIF, the metric table from `eval_results.md`, a one-paragraph architecture
note (offline precompute, NumPy-only server, per-visitor data, guarded learned ranker), and credit
for the songs. Run `python tests/run_all.py` before pushing.
