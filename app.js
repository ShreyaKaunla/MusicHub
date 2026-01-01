// LOCAL MUSIC HUB – front-end demo with Spotify-style bottom bar and mood radio

// Views
const views = {
  scan: document.getElementById('view-scan'),
  auto: document.getElementById('view-auto'),
  playlists: document.getElementById('view-playlists'),
  songs: document.getElementById('view-songs'),
  artists: document.getElementById('view-artists'),
  albums: document.getElementById('view-albums'),
  room: document.getElementById('view-room')
};



const tabButtons = Array.from(document.querySelectorAll('.tab-link'));
const globalSearch = document.getElementById('global-search');

// Player + sheet
const playerSheet = document.getElementById('player-sheet');
const sheetHandle = document.getElementById('sheet-handle');
const miniPlayer = document.getElementById('mini-player');

// Lists / grids
const songsList = document.getElementById('songs-list');
const autoGrid = document.getElementById('auto-playlist-grid');
const artistsList = document.getElementById('artists-list');
const artistSongsList = document.getElementById('artist-songs-list');
const albumsList = document.getElementById('albums-list');
const albumSongsList = document.getElementById('album-songs-list');

// Playlists panel DOM
const userPlaylistsList = document.getElementById('user-playlists-list');
const plDetailName = document.getElementById('pl-detail-name');
const plDetailMeta = document.getElementById('pl-detail-meta');
const plDetailSongs = document.getElementById('pl-detail-songs');
const btnNewPlaylist = document.getElementById('btn-new-playlist');
const btnSaveQueue = document.getElementById('btn-save-queue');
// Audio element for real playback
const audio = document.getElementById('audio-player');
console.log('audio element =', audio);

// Room queue
const roomQueueList = document.getElementById('room-queue-list');

// Player labels
const miniTitle = document.getElementById('mini-title');
const miniSub = document.getElementById('mini-sub');
const sheetTitle = document.getElementById('sheet-title');
const sheetSub = document.getElementById('sheet-sub');
const sheetTags = document.getElementById('sheet-tags');

// Buttons
const btnMoodPlaylist = document.getElementById('btn-mood-playlist');
const btnMoreArtist = document.getElementById('btn-more-artist');
const btnAddToRoom = document.getElementById('btn-add-to-room');
const btnFav = document.getElementById('btn-fav');
const btnLoop = document.getElementById('btn-loop');
const btnPlay = document.getElementById('btn-play');
const sheetPlay = document.getElementById('sheet-play');
const btnPrev = document.getElementById('btn-prev');
const btnNext = document.getElementById('btn-next');
const sheetPrev = document.getElementById('sheet-prev');
const sheetNext = document.getElementById('sheet-next');
// Folder scan input
const filePicker = document.getElementById('file-picker');
const btnScan = document.getElementById('btn-scan');


// Progress (visual only for now)
const miniProgressBar = document.getElementById('mini-progress-bar');
const progressFill = document.getElementById('progress-fill');
const sheetProgressBar = document.getElementById('sheet-progress-bar');
const sheetProgressFill = document.getElementById('sheet-progress-fill');

// Time labels
const currentTimeLabel = document.getElementById('current-time');
const totalTimeLabel = document.getElementById('total-time');
const sheetCurrentLabel = document.getElementById('sheet-current');
const sheetTotalLabel = document.getElementById('sheet-total');
const moodVectors = {
  happy:    [1, 0, 0, 0],
  sad:      [0, 1, 0, 0],
  chill:    [0, 0, 1, 0],
  energetic:[0, 0, 0, 1]
};
let trackEmbeddings = {}; // key: "title|artist" -> { album, embedding }

async function loadEmbeddings() {
  try {
    const res = await fetch('track_embeddings.json');
    if (!res.ok) {
      console.warn('No track_embeddings.json found or fetch failed');
      return;
    }
    trackEmbeddings = await res.json();
    console.log('Loaded embeddings for', Object.keys(trackEmbeddings).length, 'tracks');
  } catch (e) {
    console.error('Failed to load embeddings', e);
  }
}

function dot(a, b) {
  return a[0]*b[0] + a[1]*b[1] + a[2]*b[2] + a[3]*b[3];
}

function moodSimilarity(m1, m2) {
  const v1 = moodVectors[m1] || moodVectors.chill;
  const v2 = moodVectors[m2] || moodVectors.chill;
  return dot(v1, v2);
}

// Demo library
let library = {
  songs: [
    { id: 1, title: 'Midnight Drive', artist: 'Neon Echo', album: 'City Lights', duration: 214, mood: 'chill' },
    { id: 2, title: 'Skyline Run', artist: 'Neon Echo', album: 'City Lights', duration: 196, mood: 'energetic' },
    { id: 3, title: 'Rainy Window', artist: 'Lonely Byte', album: 'Late Night Codes', duration: 241, mood: 'sad' },
    { id: 4, title: 'Purple Nights', artist: 'Aurora Wave', album: 'Nebula Dreams', duration: 203, mood: 'happy' },
    { id: 5, title: 'City Lights Remix', artist: 'Neon Echo', album: 'City Lights (Deluxe)', duration: 260, mood: 'energetic' },
    { id: 6, title: 'Lo-Fi Nebula', artist: 'Aurora Wave', album: 'Nebula Dreams', duration: 188, mood: 'chill' }
  ],
  playlists: {
    happy: { id: 'happy', name: 'Happy Vibes', system: true, songs: [] },
    sad: { id: 'sad', name: 'Sad Hours', system: true, songs: [] },
    chill: { id: 'chill', name: 'Chill Nights', system: true, songs: [] },
    energetic: { id: 'energetic', name: 'Energetic / Workout', system: true, songs: [] }
  }
};
// Build songs from chosen folder
btnScan.addEventListener('click', () => {
  // open native folder picker
  if (filePicker.showPicker) {
    filePicker.showPicker(); // modern browsers[web:132]
  } else {
    filePicker.click();
  }
});

filePicker.addEventListener('change', async () => {  // <-- ASYNC here
  const files = Array.from(filePicker.files);
  if (!files.length) return;

  let idCounter = 1;
  const newSongs = [];

  for (const file of files) {
    if (!file.type.startsWith('audio/')) continue;

    const name = file.name.replace(/\.[^/.]+$/, "");
    const parts = name.split('-').map(p => p.trim());
    let artist = "Unknown Artist";
    let title = name;
    
    if (parts.length >= 2) {
      artist = parts[0];
      title = parts.slice(1).join(' - ');
    }
    
    const album = 'Local Files';
    
    // ML Backend call with try/catch
    let mood = 'chill';
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch('http://127.0.0.1:8002/embed', {
        method: 'POST',
        body: formData
      });
      const result = await response.json();
      mood = result.mood || 'chill';
      console.log(`✅ Backend mood for ${file.name}: ${mood}`);
    } catch (e) {
      console.warn(`❌ Backend failed for ${file.name}, using 'chill'`);
    }
    
    const url = URL.createObjectURL(file);  // blob URL for playback

// ✅ ADD embedding from backend (SAME response as mood)
let embedding = [0,0,0,0];
if (result && result.embedding) {
  embedding = result.embedding;
  console.log(`✅ ML embedding: ${file.name} [${embedding.length}]`);
}

newSongs.push({
  id: idCounter++,
  title,
  artist,
  album,
  duration: 0,
  mood,  // From backend
  url,
  embedding  // ✅ ML vector for vibe matching
});


    
    console.log(`Added song: ${title} (${mood})`);
  }

  if (!newSongs.length) {
    alert('No audio files found in that folder.');
    return;
  }

  library.songs = newSongs;
  filteredSongs = [...library.songs];
  renderSongs(filteredSongs);
  renderArtists();
  renderAlbums();
  renderAutoPlaylists();
  renderUserPlaylistsPanel();
  switchView('songs');
});



function cosineSim(a, b) {
  if (!a || !b) return 0;
  let dot = 0, na = 0, nb = 0;
  const len = Math.min(a.length, b.length);
  for (let i = 0; i < len; i++) {
    dot += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  if (!na || !nb) return 0;
  return dot / (Math.sqrt(na) * Math.sqrt(nb));
}
// NEW: Cosine similarity for embeddings (vibe matching)
function vibeDistance(emb1, emb2) {
  const dot = emb1.reduce((sum, a, i) => sum + a * emb2[i], 0);
  const norm1 = Math.sqrt(emb1.reduce((sum, a) => sum + a*a, 0));
  const norm2 = Math.sqrt(emb2.reduce((sum, a) => sum + a*a, 0));
  return Math.max(0, dot / (norm1 * norm2 || 1));  // 0-1 similarity
}

// Keep existing mood dot product
function dot(a, b) {
  return a[0]*b[0] + a[1]*b[1] + a[2]*b[2] + a[3]*b[3];
}

function scoreRelated(base, candidate, history) {
  if (base.id === candidate.id) return 9999;
  
  let score = 0;
  
  // 🔥 VIBE SIMILARITY = 70% weight (MFCC embeddings)
  if (base.embedding && candidate.embedding) {
    const vibeSim = vibeDistance(base.embedding, candidate.embedding);
    score += vibeSim * 70;
  }
  
  // Metadata = 30% weight
  if (base.artist === candidate.artist) score += 15;
  if (base.album === candidate.album) score += 10;
  score += moodSimilarity(base.mood, candidate.mood) * 5;
  
  // Title bonuses
  const bt = base.title.toLowerCase();
  const ct = candidate.title.toLowerCase();
  if (bt.split(' ')[0] === ct.split(' ')[0]) score += 3;
  if (bt.includes('remix') && ct.includes('remix')) score += 2;
  
  // History penalty
  const lastFew = history.slice(-5);
  if (lastFew.some(s => s.artist === candidate.artist)) score -= 10;
  
  // Randomness
  score += (Math.random() - 0.5) * 5;
  
  return score;
}

function buildRadioQueueFromSong(song) {
  const history = playerState.queue || [];
  const scored = library.songs.map(s => ({
    song: s,
    score: scoreRelated(song, s, history)
  }));
  scored.sort((a, b) => b.score - a.score);
  return scored.map(x => x.song);
}

const PLAYLISTS_KEY = 'localMusicHubPlaylistsV1';

// Player state
let playerState = {
  currentSong: null,
  queue: [],
  index: -1,
  isPlaying: false,
  loop: false,
  favourites: new Set()
};

function formatTime(sec) {
  if (!isFinite(sec)) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function switchView(target) {
  Object.entries(views).forEach(([key, el]) => {
    el.classList.toggle('active', key === target);
  });
  tabButtons.forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === target);
  });
}

/* ---------- bottom sheet behaviour ---------- */

function toggleSheet(forceOpen) {
  const isOpen = playerSheet.classList.contains('open');
  const shouldOpen = forceOpen !== undefined ? forceOpen : !isOpen;
  if (shouldOpen) playerSheet.classList.add('open');
  else playerSheet.classList.remove('open');
}

// click anywhere on bar toggles sheet
miniPlayer.addEventListener('click', () => toggleSheet());

// handle toggles without bubbling to bar
sheetHandle.addEventListener('click', e => {
  e.stopPropagation();
  toggleSheet();
});

/* ---------- list rendering ---------- */

let filteredSongs = [...library.songs];

function renderSongs(list) {
  songsList.innerHTML = '';
  list.forEach(song => {
    const li = document.createElement('li');
    li.className = 'list-item';
    li.dataset.songId = song.id;
    li.innerHTML = `
      <div class="song-main">
        <div class="song-title">${song.title}</div>
        <div class="song-sub">${song.artist} • ${song.album}</div>
      </div>
      <div class="song-actions">
        <div class="song-duration">${formatTime(song.duration)}</div>
        <button class="icon-btn add-to-queue-btn">＋</button>
      </div>
    `;

    // Play immediately on row click
    li.querySelector('.song-main').addEventListener('click', e => {
      e.stopPropagation();
      startRadioFromSong(song);
    });

    // Add to queue on plus button
    li.querySelector('.add-to-queue-btn').addEventListener('click', e => {
      e.stopPropagation();
      addToQueue(song);
    });

    songsList.appendChild(li);
  });
}

function addToQueue(song) {
  if (!song) return;

  // If no queue yet, start with this song
  if (!playerState.queue.length) {
    playerState.queue = [song];
    playerState.index = 0;
    playCurrentFromQueue();
    return;
  }

  // Otherwise, just push to end
  playerState.queue.push(song);
}

function scoreRelated(base, candidate, history = []) {
  if (base.id === candidate.id) return 9999;
  let score = 0;

  // Strong artist and mood bias
  if (base.artist === candidate.artist) score += 80;
  if (base.album === candidate.album) score += 40;
  if (base.mood === candidate.mood) score += 35;

  const bt = base.title.toLowerCase();
  const ct = candidate.title.toLowerCase();

  if (bt.split(' ')[0] && ct.includes(bt.split(' ')[0])) score += 10;
  if (bt.includes('remix') && ct.includes('remix')) score += 8;
  if (bt.includes('live') && ct.includes('live')) score += 8;

  // Penalize if candidate artist was just played
  const lastFew = history.slice(-5);
  if (lastFew.some(s => s.artist === candidate.artist)) score -= 25;

  // Small randomness to avoid fixed order
  score += Math.random() * 5;

  return score;
}



 


function classifyMoods() {
  ['happy', 'sad', 'chill', 'energetic'].forEach(m => {
    library.playlists[m].songs = [];
  });
  library.songs.forEach(s => {
    const bucket = library.playlists[s.mood] || library.playlists.chill;
    bucket.songs.push(s.id);
  });
}

function renderAutoPlaylists() {
  classifyMoods();
  autoGrid.innerHTML = '';

  ['happy', 'sad', 'chill', 'energetic'].forEach(mood => {
    const pl = library.playlists[mood];
    const count = pl.songs.length;
    const card = document.createElement('div');
    card.className = 'playlist-card';
    card.innerHTML = `
      <div class="playlist-name">${pl.name}</div>
      <div class="playlist-meta">Auto mood detection</div>
      <div class="playlist-count">${count} songs</div>
    `;
    card.addEventListener('click', () => {
      const songs = pl.songs.map(id => library.songs.find(s => s.id === id));
      renderSongs(songs);
      switchView('songs');
    });
    autoGrid.appendChild(card);
  });

  Object.values(library.playlists)
    .filter(pl => !pl.system)
    .forEach(pl => {
      const count = pl.songs.length;
      const card = document.createElement('div');
      card.className = 'playlist-card';
      card.innerHTML = `
        <div class="playlist-name">${pl.name}</div>
        <div class="playlist-meta">Your playlist</div>
        <div class="playlist-count">${count} songs</div>
      `;
      card.addEventListener('click', () => {
        const songs = pl.songs.map(id => library.songs.find(s => s.id === id));
        renderSongs(songs);
        switchView('songs');
      });
      autoGrid.appendChild(card);
    });
}

function renderArtists() {
  const map = new Map();
  library.songs.forEach(s => {
    if (!map.has(s.artist)) map.set(s.artist, []);
    map.get(s.artist).push(s);
  });

  artistsList.innerHTML = '';
  artistSongsList.innerHTML = '';
  let first = true;

  map.forEach((songs, artist) => {
    const li = document.createElement('li');
    li.className = 'master-item';
    li.innerHTML = `
      <span>${artist}</span>
      <span class="count-pill">${songs.length}</span>
    `;
    li.addEventListener('click', () => {
      Array.from(artistsList.children).forEach(x => x.classList.remove('active'));
      li.classList.add('active');
      renderArtistSongs(songs);
    });
    artistsList.appendChild(li);

    if (first) {
      li.classList.add('active');
      renderArtistSongs(songs);
      first = false;
    }
  });
}

function renderArtistSongs(songs) {
  artistSongsList.innerHTML = '';
  songs.forEach(song => {
    const li = document.createElement('li');
    li.className = 'list-item';
    li.innerHTML = `
      <div class="song-main">
        <div class="song-title">${song.title}</div>
        <div class="song-sub">${song.album}</div>
      </div>
      <div class="song-duration">${formatTime(song.duration)}</div>
    `;
    li.addEventListener('click', e => {
      e.stopPropagation();
      startRadioFromSong(song);
    });
    artistSongsList.appendChild(li);
  });
}

function renderAlbums() {
  const map = new Map();
  library.songs.forEach(s => {
    if (!map.has(s.album)) map.set(s.album, []);
    map.get(s.album).push(s);
  });

  albumsList.innerHTML = '';
  albumSongsList.innerHTML = '';
  let first = true;

  map.forEach((songs, album) => {
    const li = document.createElement('li');
    li.className = 'master-item';
    li.innerHTML = `
      <span>${album}</span>
      <span class="count-pill">${songs.length}</span>
    `;
    li.addEventListener('click', () => {
      Array.from(albumsList.children).forEach(x => x.classList.remove('active'));
      li.classList.add('active');
      renderAlbumSongs(songs);
    });
    albumsList.appendChild(li);

    if (first) {
      li.classList.add('active');
      renderAlbumSongs(songs);
      first = false;
    }
  });
}

function renderAlbumSongs(songs) {
  albumSongsList.innerHTML = '';
  songs.forEach(song => {
    const li = document.createElement('li');
    li.className = 'list-item';
    li.innerHTML = `
      <div class="song-main">
        <div class="song-title">${song.title}</div>
        <div class="song-sub">${song.artist}</div>
      </div>
      <div class="song-duration">${formatTime(song.duration)}</div>
    `;
    li.addEventListener('click', e => {
      e.stopPropagation();
      startRadioFromSong(song);
    });
    albumSongsList.appendChild(li);
  });
}

/* ---------- search ---------- */

function applySearch(query) {
  const q = query.trim().toLowerCase();
  if (!q) {
    filteredSongs = [...library.songs];
  } else {
    filteredSongs = library.songs.filter(s => {
      return (
        s.title.toLowerCase().includes(q) ||
        s.artist.toLowerCase().includes(q) ||
        s.album.toLowerCase().includes(q)
      );
    });
  }
  renderSongs(filteredSongs);
}

globalSearch.addEventListener('input', e => {
  applySearch(e.target.value);
  switchView('songs');
});

/* ---------- mood radio ---------- */

function scoreRelated(base, candidate, history = []) {
  if (base.id === candidate.id) return 9999;
  let score = 0;

  // Strong artist / album / mood relationship
  if (base.artist === candidate.artist) score += 80;
  if (base.album === candidate.album) score += 40;
  score += 50 * moodSimilarity(base.mood, candidate.mood);

  const bt = base.title.toLowerCase();
  const ct = candidate.title.toLowerCase();

  // Title similarity heuristics
  const baseWords = bt.split(/\s+/).filter(Boolean);
  baseWords.forEach(w => {
    if (w.length > 3 && ct.includes(w)) score += 5;
  });
  if (bt.includes('remix') && ct.includes('remix')) score += 10;
  if (bt.includes('live') && ct.includes('live')) score += 10;

  // Penalize recently played artists (diversity)
  const lastFew = history.slice(-5);
  if (lastFew.some(s => s.artist === candidate.artist)) score -= 30;

  // Tiny randomness to avoid deterministic order
  score += Math.random() * 5;

  return score;
}


function buildRadioQueueFromSong(song) {
  const scored = library.songs.map(s => ({
    song: s,
    score: scoreRelated(song, s)
  }));
  scored.sort((a, b) => b.score - a.score);
  return scored.map(x => x.song);
}

function startRadioFromSong(song) {
  playerState.queue = buildRadioQueueFromSong(song);
  playerState.index = playerState.queue.findIndex(s => s.id === song.id);
  if (playerState.index < 0) playerState.index = 0;
  playCurrentFromQueue();
}

/* ---------- visible queue helper ---------- */

function showQueueInPanel(label) {
  if (!playerState.queue.length) return;
  switchView('playlists');

  plDetailName.textContent = label;
  plDetailMeta.textContent = `${playerState.queue.length} songs in queue`;
  plDetailSongs.innerHTML = '';

  playerState.queue.forEach(song => {
    const li = document.createElement('li');
    li.className = 'list-item';
    li.innerHTML = `
      <div class="song-main">
        <div class="song-title">${song.title}</div>
        <div class="song-sub">${song.artist} • ${song.album}</div>
      </div>
      <div class="song-duration">${formatTime(song.duration)}</div>
    `;
    li.addEventListener('click', e => {
      e.stopPropagation();
      startRadioFromSong(song);
    });
    plDetailSongs.appendChild(li);
  });
}

/* ---------- player visuals ---------- */

function playCurrentFromQueue() {
  console.log('playCurrentFromQueue', playerState.index, playerState.queue[playerState.index]);

  const song = playerState.queue[playerState.index];
  if (!song) return;
  playerState.currentSong = song;

  // Update UI
  miniTitle.textContent = song.title;
  miniSub.textContent = `${song.artist} • ${song.album}`;
  sheetTitle.textContent = song.title;
  sheetSub.textContent = `${song.artist} • ${song.album}`;

  sheetTags.innerHTML = '';
  const tag = document.createElement('span');
  tag.className = 'tag-pill';
  tag.textContent =
    song.mood === 'happy'
      ? 'Happy Vibes'
      : song.mood === 'sad'
      ? 'Sad Hours'
      : song.mood === 'energetic'
      ? 'Energetic'
      : 'Chill Nights';
  sheetTags.appendChild(tag);

  progressFill.style.width = '0%';
  sheetProgressFill.style.width = '0%';
  currentTimeLabel.textContent = '0:00';
  sheetCurrentLabel.textContent = '0:00';

  // If no URL, cannot play
  if (!song.url) {
    audio.removeAttribute('src');
    playerState.isPlaying = false;
    btnPlay.textContent = '▶';
    sheetPlay.textContent = '▶';
    return;
  }

  // Point audio to this song and play
  audio.src = song.url;
  audio.currentTime = 0;
  audio.play().catch(() => {});
  playerState.isPlaying = true;
  btnPlay.textContent = '⏸';
  sheetPlay.textContent = '⏸';
}

// Update progress and time from real audio
audio.addEventListener('timeupdate', () => {
  if (!audio.duration || !isFinite(audio.duration)) return;
  const pct = (audio.currentTime / audio.duration) * 100;
  progressFill.style.width = `${pct}%`;
  sheetProgressFill.style.width = `${pct}%`;
  currentTimeLabel.textContent = formatTime(audio.currentTime);
  sheetCurrentLabel.textContent = formatTime(audio.currentTime);
  totalTimeLabel.textContent = formatTime(audio.duration);
  sheetTotalLabel.textContent = formatTime(audio.duration);
});

audio.addEventListener('ended', () => {
  if (playerState.loop) {
    audio.currentTime = 0;
    audio.play();
  } else {
    nextInQueue();
  }
});

function togglePlay() {
  if (!audio.src) return;
  if (audio.paused) {
    audio.play().catch(() => {});
    playerState.isPlaying = true;
  } else {
    audio.pause();
    playerState.isPlaying = false;
  }
  btnPlay.textContent = playerState.isPlaying ? '⏸' : '▶';
  sheetPlay.textContent = playerState.isPlaying ? '⏸' : '▶';
}

btnPlay.addEventListener('click', e => {
  e.stopPropagation();
  togglePlay();
});

sheetPlay.addEventListener('click', e => {
  e.stopPropagation();
  togglePlay();
});



function nextInQueue() {
  if (!playerState.queue.length) return;
  if (!playerState.loop) {
    playerState.index = (playerState.index + 1) % playerState.queue.length;
  }
  playCurrentFromQueue();
}

function prevInQueue() {
  if (!playerState.queue.length) return;
  if (!playerState.loop) {
    playerState.index = (playerState.index - 1 + playerState.queue.length) % playerState.queue.length;
  }
  playCurrentFromQueue();
}


/* ---------- progress (visual) ---------- */

function seekProgress(bar, fill, x) {
  if (!audio.duration || !isFinite(audio.duration)) return;
  const rect = bar.getBoundingClientRect();
  const ratio = (x - rect.left) / rect.width;
  const clamped = Math.max(0, Math.min(1, ratio));
  const pct = clamped * 100;
  fill.style.width = `${pct}%`;
  audio.currentTime = clamped * audio.duration;
}


miniProgressBar.addEventListener('click', e => {
  e.stopPropagation();
  seekProgress(miniProgressBar, progressFill, e.clientX);
});
sheetProgressBar.addEventListener('click', e => {
  e.stopPropagation();
  seekProgress(sheetProgressBar, sheetProgressFill, e.clientX);
});

/* ---------- play / pause + controls ---------- */



btnNext.addEventListener('click', e => {
  e.stopPropagation();
  nextInQueue();
});
sheetNext.addEventListener('click', e => {
  e.stopPropagation();
  nextInQueue();
});
btnPrev.addEventListener('click', e => {
  e.stopPropagation();
  prevInQueue();
});
sheetPrev.addEventListener('click', e => {
  e.stopPropagation();
  prevInQueue();
});

btnLoop.addEventListener('click', e => {
  e.stopPropagation();
  playerState.loop = !playerState.loop;
  btnLoop.style.color = playerState.loop ? '#a855f7' : '';
});

btnFav.addEventListener('click', e => {
  e.stopPropagation();
  if (!playerState.currentSong) return;
  const id = playerState.currentSong.id;
  if (playerState.favourites.has(id)) {
    playerState.favourites.delete(id);
    btnFav.style.color = '';
  } else {
    playerState.favourites.add(id);
    btnFav.style.color = '#fb7185';
  }
});

/* ---------- playlists storage ---------- */

let currentPlaylistId = null;

function loadUserPlaylists() {
  try {
    const raw = localStorage.getItem(PLAYLISTS_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    Object.entries(parsed).forEach(([id, pl]) => {
      library.playlists[id] = { ...pl, system: false };
    });
  } catch {
    // ignore
  }
}

function saveUserPlaylists() {
  const userPlaylists = {};
  Object.values(library.playlists)
    .filter(pl => !pl.system)
    .forEach(pl => {
      userPlaylists[pl.id] = {
        id: pl.id,
        name: pl.name,
        songs: pl.songs
      };
    });
  localStorage.setItem(PLAYLISTS_KEY, JSON.stringify(userPlaylists));
}

function renderUserPlaylistsPanel() {
  userPlaylistsList.innerHTML = '';
  const userPlaylists = Object.values(library.playlists).filter(pl => !pl.system);

  if (!userPlaylists.length) {
    const li = document.createElement('li');
    li.className = 'list-item';
    li.innerHTML = `<div class="song-main">
        <div class="song-title">No playlists yet</div>
        <div class="song-sub">Create one using "New Playlist"</div>
      </div>`;
    userPlaylistsList.appendChild(li);
    plDetailName.textContent = 'Select a playlist';
    plDetailMeta.textContent = 'No playlist selected';
    plDetailSongs.innerHTML = '';
    return;
  }

  userPlaylists.forEach(pl => {
    const li = document.createElement('li');
    li.className = 'list-item';
    li.dataset.playlistId = pl.id;
    li.innerHTML = `
      <div class="song-main">
        <div class="song-title">${pl.name}</div>
        <div class="song-sub">${pl.songs.length} songs</div>
      </div>
    `;
    li.addEventListener('click', () => selectPlaylist(pl.id));
    userPlaylistsList.appendChild(li);
  });

  if (currentPlaylistId && library.playlists[currentPlaylistId]) {
    selectPlaylist(currentPlaylistId);
  } else {
    selectPlaylist(userPlaylists[0].id);
  }
}

function selectPlaylist(id) {
  currentPlaylistId = id;
  const pl = library.playlists[id];
  if (!pl) return;

  Array.from(userPlaylistsList.children).forEach(li => {
    li.classList.toggle('active', li.dataset.playlistId === id);
  });

  plDetailName.textContent = pl.name;
  plDetailMeta.textContent = `${pl.songs.length} songs`;
  plDetailSongs.innerHTML = '';

  pl.songs.forEach(songId => {
    const s = library.songs.find(x => x.id === songId);
    if (!s) return;
    const li = document.createElement('li');
    li.className = 'list-item';
    li.innerHTML = `
      <div class="song-main">
        <div class="song-title">${s.title}</div>
        <div class="song-sub">${s.artist} • ${s.album}</div>
      </div>
      <div class="song-duration">${formatTime(s.duration)}</div>
    `;
    li.addEventListener('click', e => {
      e.stopPropagation();
      startRadioFromSong(s);
    });
    plDetailSongs.appendChild(li);
  });
}

function createManualPlaylist() {
  const name = prompt('Playlist name (e.g., My Mix):');
  if (!name) return;
  const id = `user_${Date.now()}`;
  library.playlists[id] = {
    id,
    name,
    system: false,
    songs: []
  };
  saveUserPlaylists();
  renderAutoPlaylists();
  renderUserPlaylistsPanel();
  switchView('playlists');
}

function saveCurrentMoodPlaylist() {
  if (!playerState.queue.length) {
    alert('Play a song first to build a mood queue.');
    return;
  }
  const base = playerState.currentSong || playerState.queue[0];
  const defaultName = `${base.title} – Radio`;
  const name = prompt('Save mood playlist as:', defaultName) || defaultName;
  const id = `mood_${Date.now()}`;
  library.playlists[id] = {
    id,
    name,
    system: false,
    songs: playerState.queue.map(s => s.id)
  };
  saveUserPlaylists();
  renderAutoPlaylists();
  renderUserPlaylistsPanel();
  switchView('playlists');
}

btnNewPlaylist.addEventListener('click', e => {
  e.stopPropagation();
  createManualPlaylist();
});

btnSaveQueue.addEventListener('click', e => {
  e.stopPropagation();
  saveCurrentMoodPlaylist();
});

/* ---------- mood playlist + more from artist buttons ---------- */

btnMoodPlaylist.addEventListener('click', e => {
  e.stopPropagation();
  if (!playerState.currentSong) {
    alert('Select a song first to build a mood playlist.');
    return;
  }

  // Build a new mood-only queue from current song
  const moodQueue = buildRadioQueueFromSong(playerState.currentSong);

  if (!moodQueue.length) return;

  playerState.queue = moodQueue;
  playerState.index = 0;          // start at first in new mood queue
  playCurrentFromQueue();         // plays queue[0]

  showQueueInPanel('Mood playlist');
});


btnMoreArtist.addEventListener('click', e => {
  e.stopPropagation();
  if (!playerState.currentSong) return;
  const artist = playerState.currentSong.artist;
  const songs = library.songs.filter(s => s.artist === artist);
  playerState.queue = songs;
  playerState.index = 0;
  playCurrentFromQueue();
  showQueueInPanel(`More from ${artist}`);
});

btnAddToRoom.addEventListener('click', e => {
  e.stopPropagation();
  if (!playerState.currentSong) {
    alert('Play something first, then add it to the room.');
    return;
  }
  const song = playerState.currentSong;
  const li = document.createElement('li');
  li.className = 'list-item';
  li.innerHTML = `
    <div class="song-main">
      <div class="song-title">${song.title}</div>
      <div class="song-sub">${song.artist} • ${song.album}</div>
    </div>
  `;
  roomQueueList.appendChild(li);
  switchView('room');
});

/* ---------- tabs ---------- */

tabButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    switchView(btn.dataset.view);
  });
});

/* ---------- init ---------- */

// init
loadUserPlaylists();
filteredSongs = [...library.songs];
renderSongs(filteredSongs);
renderAutoPlaylists();
renderArtists();
renderAlbums();
renderUserPlaylistsPanel();
switchView('scan');
loadEmbeddings();
