// LOCAL MUSIC HUB – front-end demo with Spotify-style bottom bar and mood radio
document.addEventListener('DOMContentLoaded', function() {
  // LOCAL MUSIC HUB – front-end demo with Spotify-style bottom bar and mood radio
  
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
const filePicker = document.getElementById('filePicker');
const btnscan = document.getElementById('btnscan');


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
    party: [0.9, 0.8, 0.1, 0.2, 1.0, 0.3, 0.1],     // tempo, energy, centroid, mfcc0, rolloff, zcr, chroma
    sad: [0.1, 0.1, 0.9, 0.8, 0.2, 1.0, 0.4],
    chill: [0.3, 0.2, 0.7, 0.4, 0.3, 0.6, 0.9],
    happy: [0.8, 0.7, 0.3, 0.9, 0.6, 0.2, 0.8],
    romantic: [0.5, 0.4, 0.6, 0.7, 0.4, 0.5, 0.7],
    soothing: [0.1, 0.05, 0.8, 0.3, 0.1, 0.8, 0.6],
    angry: [0.2, 0.9, 0.4, 0.5, 1.0, 0.7, 0.3]
};

function cosineSimilarity(vecA, vecB) {
    if (!vecA || !vecB) return 0;
    let dotProduct = 0;
    let normA = 0;
    let normB = 0;
    for (let i = 0; i < vecA.length; i++) {
        dotProduct += vecA[i] * vecB[i];
        normA += vecA[i] * vecA[i];
        normB += vecB[i] * vecB[i];
    }
    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}

function getVibeSimilarity(songA, songB) {
    return cosineSimilarity(songA.vector, songB.vector);
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
    party: { id: 'party', name: 'Party Hits', system: true, songs: [] },
    sad: { id: 'sad', name: 'Sad Hours', system: true, songs: [] },
    chill: { id: 'chill', name: 'Chill Nights', system: true, songs: [] },
    happy: { id: 'happy', name: 'Happy Vibes', system: true, songs: [] },
    romantic: { id: 'romantic', name: 'Romantic Evenings', system: true, songs: [] },
    soothing: { id: 'soothing', name: 'Soothing Moments', system: true, songs: [] },
    angry: { id: 'angry', name: 'Angry Anthems', system: true, songs: [] }
},

};
// Build songs from chosen folder
btnscan.addEventListener('click', () => filePicker.click());

// ✅ SINGLE async handler with backend ML
filePicker.addEventListener('change', async (e) => {
    const files = Array.from(filePicker.files || []);
    if (!files.length) return;

    const newSongs = [];
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        // 1. Skip system files (like desktop.ini) to prevent backend crashes
        if (!file.type.startsWith('audio/')) continue;

        const formData = new FormData();
        formData.append('file', file);

        try {
            console.log(`Scanning ${i+1}/${files.length}: ${file.name}`);
            // 2. Request the 16-parameter embedding from your main.py
            const res = await fetch('http://127.0.0.1:8000/embed', { method: 'POST', body: formData });
            const data = await res.json();

            newSongs.push({
                id: Date.now() + i,
                title: file.name.replace(/\.[^/.]+$/, ""),
                artist: "Local Artist",
                album: "Local Folder",
                vector: data.vector, // The vibe DNA [3]
                mood: data.mood,     // The category (Party, Sad, etc.)
                url: URL.createObjectURL(file)
            });
        } catch (err) {
            console.error("Scanning failed for:", file.name, err);
        }
    }

    // 3. Update the app state
    library.songs = [...library.songs, ...newSongs];
    classifyMoods(); 
    renderAutoPlaylists(); 
    renderSongs(library.songs);
    console.log(`✅ Scan complete. Total library: ${library.songs.length} songs.`);
});

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
    songsList.innerHTML = ''; [15]
    list.forEach(song => {
        const li = document.createElement('li');
        li.className = 'list-item';
        li.addEventListener('click', () => startRadioFromSong(song)); // FIX: Song title click [23]
        li.innerHTML = `
            <div class="song-main">
                <div class="song-title">${song.title}</div>
                <div class="song-sub">${song.artist} • ${song.album}</div>
            </div>
            <div class="song-duration">${formatTime(song.duration)}</div>`;
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
    if (base.id === candidate.id) return -999;
    let score = 0;

    // Use the 16-parameter vector similarity
    const vibeSim = getVibeSimilarity(base, candidate);
    score += vibeSim * 150; // High weight for the "vibe"

    // Bonus for same artist/album
    if (base.artist === candidate.artist) score += 70;
    if (base.album === candidate.album) score += 40;

    // Penalty for recently played artists to keep it fresh
    const recentArtists = history.slice(-5).map(h => h.artist);
    if (recentArtists.includes(candidate.artist)) score -= 50;

    return score;
}



function buildRadioQueueFromSong(song) {
  // Step 1: pre‑filter by mood similarity
  const baseMood = song.mood || 'chill';
  const candidates = library.songs.filter(s => {
    if (s.id === song.id) return true; // always keep base song
    const sim = moodSimilarity(baseMood, s.mood || 'chill');
    return sim > 0; // keep only same/compatible mood
  });

  // Step 2: score within candidates
  const history = playerState.queue || [];
  const scored = candidates.map(s => ({
    song: s,
    score: scoreRelated(song, s, history)
  }));

  scored.sort((a, b) => b.score - a.score);
  return scored.map(x => x.song);
}


function classifyMoods() {
    const autoMoods = ['party', 'sad', 'chill', 'happy', 'romantic', 'soothing', 'angry']; [17]
    autoMoods.forEach(mood => {
        library.playlists[mood].songs = library.songs.filter(s => s.mood === mood).map(s => s.id);
    });
}

function renderAutoPlaylists() {
    classifyMoods();
    autoGrid.innerHTML = ''; [17]
    Object.values(library.playlists).filter(pl => pl.system).forEach(pl => {
        if (pl.songs.length === 0) return;
        const card = document.createElement('div');
        card.className = 'playlist-card'; // Style this in CSS
        card.innerHTML = `<h4>${pl.name}</h4><p>${pl.songs.length} tracks</p>`;
        card.addEventListener('click', () => {
            selectPlaylist(pl.id); [35]
            switchView('playlists'); [13]
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

function moodSimilarity(m1, m2, songA, songB) {
    // If the songs have the 16-D vectors, use the advanced math
    if (songA?.vector && songB?.vector) {
        return cosineSimilarity(songA.vector, songB.vector);
    }
    // Fallback to the static categories in your source
    const v1 = moodVectors[m1] || moodVectors.chill;
    const v2 = moodVectors[m2] || moodVectors.chill;
    return cosineSimilarity(v1, v2); 
}

// Then, in buildRadioQueueFromSong, lower the 0.8 threshold to 0.5

function scoreRelated(base, candidate, history) {
    if (base.id === candidate.id) return 10000;
    
    let score = moodSimilarity(base.mood, candidate.mood) * 60;
    
    // Tempo/energy match
    const tDiff = Math.abs((base.tempo || 100) - (candidate.tempo || 100));
    score += (30 - Math.min(tDiff, 30)) * 0.8;
    const eDiff = Math.abs((base.energy || 0.1) - (candidate.energy || 0.1));
    score += (25 - Math.min(eDiff*100, 25)) * 0.8;
    
    // Artist (YouTube huge bonus)
    if (base.artist === candidate.artist) score += 40;
    
    // MFCC timbre match
    const m0Diff = Math.abs((base.mfcc0 || 0) - (candidate.mfcc0 || 0));
    const m1Diff = Math.abs((base.mfcc1 || 0) - (candidate.mfcc1 || 0));
    score += (20 - m0Diff*2) + (15 - m1Diff*2);
    
    // Diversity penalty
    const recent = history.slice(-3);
    if (recent.some(h => h.artist === candidate.artist)) score -= 35;
    
    return score + Math.random()*4;
}



function buildRadioQueueFromSong(baseSong) {
    
    if (!baseSong) return [];

    // The filter below was causing the error because 'baseSong' 
    // needs to be the parameter name of the function.
    const candidates = library.songs.filter(s => 
        s.id !== baseSong.id && moodSimilarity(baseSong.mood, s.mood, baseSong, s) > 0.5
    );

    // 2. Score the candidates
    const scored = candidates.map(s => ({
        song: s,
        score: scoreRelated(baseSong, s, playerState.queue || [])
    }));

    scored.sort((a, b) => b.score - a.score);

    // 3. THE RETURN MUST BE LAST (This was line 510)
    return [baseSong, ...scored.slice(0, 19).map(x => x.song)];
    
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
  tag.textContent = {
  happy: "Happy Vibes", sad: "Sad Hours", chill: "Chill Nights",
  energetic: "Energetic", romantic: "Romantic", soothing: "Soothing", angry: "Angry"
  }[song.mood] || song.mood;

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
  playerState.queue = buildRadioQueueFromSong(playerState.currentSong);
  playerState.index = 0;
  playCurrentFromQueue();
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

loadUserPlaylists();
filteredSongs = [...library.songs];
renderSongs(filteredSongs);
renderAutoPlaylists();
renderArtists();
renderAlbums();
renderUserPlaylistsPanel();
switchView('scan');
});
