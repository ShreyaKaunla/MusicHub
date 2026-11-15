import React, { useEffect, useState, useRef, useLayoutEffect } from 'react';

// Dev: the Vite server talks to the backend on :8000. Packaged/desktop builds: the UI is served BY
// the backend itself, so a relative "/api" is correct (no origin hard-coded into the bundle).
const API = (import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '')) + '/api';
const apiFetch = (url, opts = {}) => fetch(url, opts);
const JSON_H = { 'Content-Type': 'application/json' };
const FIELD = { albums: 'album', artists: 'artist', languages: 'language' };
const cover = (s) => `${API}/cover/${encodeURIComponent(s.file_path)}`;
const fmt = (t) => {
  if (!t || isNaN(t)) return '0:00';
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${m}:${s < 10 ? '0' : ''}${s}`;
};
const C = { bg: '#121212', card: '#181818', hover: '#242424', green: '#1db954', dim: '#b3b3b3' };
const btn = { padding: '12px 16px', borderRadius: 10, border: 'none', background: C.card, color: '#fff',
  fontWeight: 'bold', cursor: 'pointer', textAlign: 'left', fontSize: 14 };

const css = `
@keyframes marq { from { transform: translateX(100%); } to { transform: translateX(-100%); } }
.marq { animation: marq linear infinite; }
@keyframes marqr { from { transform: translateX(-100%); } to { transform: translateX(100%); } }
.marqr { animation: marqr linear infinite; }
.row:hover { background:#242424 !important; }
.card { padding:10px; border-radius:10px; cursor:pointer; background:#181818; transition:background .15s; flex-shrink:0; }
.card:hover { background:#242424; }
.cv { content-visibility:auto; contain-intrinsic-size:auto 44px; }
.mi { display:block; width:100%; text-align:left; background:none; border:none; color:#fff; padding:8px 10px; border-radius:6px; cursor:pointer; font-size:13px; }
.mi:hover { background:#3a3a3a; }
.opts { display:flex; gap:8px; justify-content:center; margin-top:18px; }
.slot { position:relative; width:48px; height:48px; }
.opt { position:absolute; left:50%; top:0; transform:translateX(-50%); display:flex; align-items:center; justify-content:center;
  width:48px; height:48px; overflow:hidden; white-space:nowrap; border:none; border-radius:12px; background:#181818; color:#fff;
  cursor:pointer; padding:0; transition:width .2s, opacity .15s, background .2s; }
.opt .ic { font-size:18px; min-width:48px; text-align:center; }
.opt .lb { font-weight:bold; font-size:13px; max-width:0; opacity:0; transition:max-width .2s, opacity .2s; }
.opts:hover .slot:not(:hover) .opt { opacity:0; pointer-events:none; }
.slot:hover .opt { width:170px; background:#242424; z-index:3; }
.slot:hover .opt .ic { min-width:40px; }
.slot:hover .opt .lb { max-width:120px; opacity:1; }
`;

// Always ONE line. If the text is wider than its box it scrolls (reverse = left to right).
function Marquee({ text, style, reverse = false }) {
  const t = String(text ?? '');
  const box = useRef(), inner = useRef();
  const [scroll, setScroll] = useState(false);
  useLayoutEffect(() => { setScroll(inner.current.scrollWidth > box.current.clientWidth); }, [t]);
  return (
    <div ref={box} style={{ overflow: 'hidden', whiteSpace: 'nowrap', ...style }}>
      <span ref={inner} className={scroll ? (reverse ? 'marqr' : 'marq') : ''}
        style={{ display: 'inline-block', animationDuration: `${Math.max(6, t.length * 0.3)}s` }}>{t}</span>
    </div>
  );
}

// Own component so the 4x/second time updates don't re-render the whole app
function Seek({ audioRef, fluid = false }) {
  const dur = (a) => (a && isFinite(a.duration) && a.duration > 0 ? a.duration : 0);
  const [t, setT] = useState(0), [d, setD] = useState(() => dur(audioRef.current));
  useEffect(() => {
    const a = audioRef.current;
    if (!a) return;
    const u = () => setT(a.currentTime), m = () => setD(dur(a));
    m();
    a.addEventListener('timeupdate', u); a.addEventListener('loadedmetadata', m); a.addEventListener('durationchange', m);
    return () => { a.removeEventListener('timeupdate', u); a.removeEventListener('loadedmetadata', m); a.removeEventListener('durationchange', m); };
  }, [audioRef]);
  return (
    <div style={{ ...(fluid ? { flex: 1, minWidth: 0 } : { width: 320 }), display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: C.dim }}>
      <span>{fmt(t)}</span>
      <input type="range" min="0" max={d} step="0.1" value={Math.min(t, d)} disabled={!d} style={{ flex: 1, accentColor: C.green }}
        onChange={(e) => { const v = parseFloat(e.target.value); if (!d || isNaN(v)) return; audioRef.current.currentTime = v; setT(v); }} />
      <span>{fmt(d)}</span>
    </div>
  );
}

const Opt = ({ icon, label, onClick }) => (
  <div className="slot"><button className="opt" onClick={onClick}><span className="ic">{icon}</span><span className="lb">{label}</span></button></div>
);

const SongRow = React.memo(function SongRow({ song, active, open, removable, inPl, ctx, act }) {
  const [sub, setSub] = useState(false);
  useEffect(() => { if (!open) setSub(false); }, [open]);
  const a = act.current;
  return (
    <li className={open ? 'row' : 'row cv'} style={{ display: 'flex', alignItems: 'center', background: C.card, borderRadius: 8, marginBottom: 6,
      outline: active ? `1px solid ${C.green}` : 'none' }}>
      <div onClick={() => a.play(song, ctx)} style={{ flex: 1, padding: 10, cursor: 'pointer', overflow: 'hidden' }}>
        <div style={{ fontSize: 14, fontWeight: 600, whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>{song.title}</div>
        <div style={{ fontSize: 12, color: C.dim }}>{song.artist}</div>
      </div>
      <div className="menu-wrap" style={{ position: 'relative' }}>
        <button onClick={() => a.menu(open ? null : `${ctx}:${song.id}`)}
          style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', fontSize: 18, padding: '8px 12px' }}>⋮</button>
        {open && (
          <div style={{ position: 'absolute', right: 8, top: '100%', zIndex: 20, background: '#2a2a2a', borderRadius: 8, padding: 6,
            minWidth: 180, boxShadow: '0 6px 16px rgba(0,0,0,.6)' }}>
            <button className="mi" onClick={() => a.like(song)}>{a.liked.has(song.id) ? '♥ Unlike' : '♡ Like'}</button>
            <button className="mi" onClick={() => setSub(sub === 'add' ? false : 'add')}>＋ Add to playlist ▸</button>
            {inPl && <button className="mi" onClick={() => setSub(sub === 'move' ? false : 'move')}>↪ Move to playlist ▸</button>}
            {sub && (() => {
              const targets = a.pls.filter((p) => p.id !== a.plId);
              return targets.length
                ? targets.map((p) => <button key={p.id} className="mi" style={{ paddingLeft: 22 }}
                    onClick={() => (sub === 'move' ? a.move(p.id, song) : a.addTo(p.id, song))}>{p.name}</button>)
                : <div style={{ padding: '6px 22px', fontSize: 12, color: C.dim }}>No other playlists</div>;
            })()}
            {removable && <button className="mi" onClick={() => a.remove(song)}>🗑 Remove from here</button>}
          </div>
        )}
      </div>
    </li>
  );
});

const Collage = ({ list }) => (
  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', width: 150, height: 150, borderRadius: 10, overflow: 'hidden', background: '#282828' }}>
    {list.slice(0, 4).map((s) => (
      <img key={s.id} src={cover(s)} alt="" loading="lazy" onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
    ))}
  </div>
);

const Tile = ({ icon }) => (
  <div style={{ width: 150, height: 150, borderRadius: 10, background: 'linear-gradient(135deg,#2a3a31,#1a1a1a)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 48 }}>{icon}</div>
);
const MOOD_ICON = { Happy: '😊', Sad: '😢', Soothing: '🌙', Energetic: '⚡', Motivational: '💪', 'Bollywood Party': '🎉', Oldy: '📻' };
const BAR_H = 84; // height of the popped-down player bar

// The "For You" home: shelves built by the backend from your listening history
function ForYou({ home, byId, onPlay }) {
  if (!home) return <div style={{ color: C.dim, margin: 'auto' }}>Loading your mixes…</div>;
  if (home.error || !home.sections?.length)
    return <div style={{ color: C.dim, margin: 'auto' }}>Pick a song from the left to start playing 🎶</div>;
  const toSongs = (ids) => (ids || []).map((id) => byId.get(id)).filter(Boolean);
  const Shelf = ({ title, children }) => (
    <section style={{ marginBottom: 26 }}>
      <h3 style={{ margin: '0 0 10px' }}>{title}</h3>
      <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 8 }}>{children}</div>
    </section>
  );
  const label = { width: 150, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' };
  return (
    <div style={{ width: '100%', minWidth: 0 }}>
      <h2 style={{ marginTop: 0 }}>Good to see you 👋</h2>
      {!home.unlocked && (
        <div style={{ background: '#1f3d2b', borderRadius: 10, padding: '10px 14px', marginBottom: 20, fontSize: 14 }}>
          ✨ Keep listening to unlock your personal mixes{home.needed ? ` — ${home.needed} more song${home.needed === 1 ? '' : 's'} to go` : ''}.
          They learn from what you finish, like and skip.
        </div>
      )}
      {home.unlocked && home.ranker?.adopted && (
        <div style={{ fontSize: 12, color: C.dim, marginBottom: 16 }}>
          🎯 Ranking tuned to your listening (held-out AUC {home.ranker.auc_learned?.toFixed(2)} vs {home.ranker.auc_default?.toFixed(2)} for the default weights).
        </div>
      )}
      {home.sections.map((sec) => {
        if (sec.kind === 'playlists') {
          const items = sec.items.map((it) => ({ ...it, list: toSongs(it.track_ids) })).filter((it) => it.list.length >= 3);
          if (!items.length) return null;
          return (
            <Shelf key={sec.id} title={sec.title}>
              {items.map((it) => (
                <div key={it.id} className="card" onClick={() => onPlay(it.list, 0)}>
                  <Collage list={it.list} />
                  <div style={{ ...label, fontWeight: 700, marginTop: 8 }}>{it.title}</div>
                  <div style={{ ...label, fontSize: 12, color: C.dim }}>{it.subtitle}</div>
                </div>
              ))}
            </Shelf>
          );
        }
        const list = toSongs(sec.track_ids);
        if (list.length < 3) return null;
        return (
          <Shelf key={sec.id} title={sec.title}>
            {list.map((song, i) => (
              <div key={song.id} className="card" onClick={() => onPlay(list, i)}>
                <img src={cover(song)} alt="" loading="lazy" onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }}
                  style={{ width: 130, height: 130, borderRadius: 8, objectFit: 'cover', background: '#282828', display: 'block' }} />
                <div style={{ ...label, width: 130, fontWeight: 600, marginTop: 8, fontSize: 13 }}>{song.title}</div>
                <div style={{ ...label, width: 130, fontSize: 12, color: C.dim }}>{song.artist}</div>
              </div>
            ))}
          </Shelf>
        );
      })}
    </div>
  );
}

export default function App() {
  const [songs, setSongs] = useState([]);
  const [search, setSearch] = useState('');
  const [view, setView] = useState({ page: 'home', group: null, pl: null });
  const [queue, setQueue] = useState([]);
  const [qIdx, setQIdx] = useState(0);
  const [mode, setMode] = useState('rec'); // 'rec' = recommendation queue, 'normal' = the list you played from
  const [isPlaying, setIsPlaying] = useState(false);
  const [liked, setLiked] = useState(new Set());
  const [userPls, setUserPls] = useState([]);
  const [plSongs, setPlSongs] = useState([]);
  const [picker, setPicker] = useState(null); // {} = new playlist, {pl} = add songs to pl
  const [newName, setNewName] = useState('');
  const [pickQ, setPickQ] = useState('');
  const [picked, setPicked] = useState(new Set());
  const [menuId, setMenuId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [an, setAn] = useState({ running: false, done: 0, total: 0 });
  const [home, setHome] = useState(null);
  const [sheetOpen, setSheetOpen] = useState(false); // the player: popped up (true) or popped down (false)
  const [drag, setDrag] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [bq, setBq] = useState('');                  // search box of the middle (browse) area
  const [gridLimit, setGridLimit] = useState(120);
  const [lib, setLib] = useState(null);              // library auto-sync status

  const audioRef = useRef(null);
  const folderRef = useRef(null);
  const songsRef = useRef([]);
  const shownRef = useRef({});
  const ctxRef = useRef([]);
  const extending = useRef(false);
  const version = useRef(0);
  const act = useRef({});
  const listenRef = useRef(null);
  const dragRef = useRef(null);
  const prevLib = useRef(null);
  songsRef.current = songs;
  const current = queue[qIdx];

  const loadSongs = () => apiFetch(`${API}/songs`).then((r) => r.json()).then((d) => setSongs(d || [])).catch(console.error);
  const loadLikes = () => apiFetch(`${API}/likes`).then((r) => r.json()).then((d) => setLiked(new Set(d))).catch(() => {});
  const loadUserPls = () => apiFetch(`${API}/user-playlists`).then((r) => r.json()).then(setUserPls).catch(() => {});
  const loadHome = () => apiFetch(`${API}/home`).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(setHome).catch(() => setHome({ error: true, sections: [] }));

  useEffect(() => {
    loadSongs(); loadLikes(); loadUserPls();
    apiFetch(`${API}/analyze-moods/status`).then((r) => r.json()).then(setAn).catch(() => {});
    const close = (e) => { if (!e.target.closest('.menu-wrap')) setMenuId(null); };
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, []);

  useEffect(() => {
    if (!an.running) return;
    const t = setInterval(async () => {
      const s = await apiFetch(`${API}/analyze-moods/status`).then((r) => r.json()).catch(() => null);
      if (s) { setAn(s); if (!s.running) loadUserPls(); }
    }, 3000);
    return () => clearInterval(t);
  }, [an.running]);

  useEffect(() => {
    if (audioRef.current && current) {
      audioRef.current.load();
      if (isPlaying) audioRef.current.play().catch(() => {});
    }
  }, [current?.id]);

  // ---- recommendation queue: endless ----
  const fetchRecs = async (song, exclude) => {
    try {
      const r = await apiFetch(`${API}/recommendations`, { method: 'POST', headers: JSON_H, body: JSON.stringify({ file_path: song.file_path }) });
      const j = await r.json();
      return (j.sdata || []).map((x) => songsRef.current.find((s) => s.file_path.endsWith(x.file_name))).filter((s) => s && !exclude.has(s.id));
    } catch { return []; }
  };

  useEffect(() => {
    if (mode !== 'rec' || !queue.length || queue.length - qIdx > 3 || extending.current) return;
    extending.current = true;
    const v = version.current, last = queue[queue.length - 1];
    (async () => {
      let recs = await fetchRecs(last, new Set(queue.map((s) => s.id)));
      if (!recs.length) recs = await fetchRecs(last, new Set([last.id]));
      if (recs.length && v === version.current) setQueue((q) => [...q, ...recs]);
      extending.current = false;
    })();
  }, [queue.length, qIdx, mode]);

  const resetQueue = () => { version.current += 1; extending.current = false; };

  // ---- listening history: feeds the taste profile ----
  const logEvent = (song, event, seconds = 0) => {
    apiFetch(`${API}/events`, { method: 'POST', headers: JSON_H, body: JSON.stringify({ track_id: song.id, event, seconds }) }).catch(() => {});
  };
  // Ends the current listen. Leaving after 85% of the song counts as finished, earlier counts as a skip.
  const closeListen = (kind) => {
    const l = listenRef.current, a = audioRef.current;
    if (!l || !a) return;
    listenRef.current = null;
    const t = a.currentTime || 0, d = isFinite(a.duration) ? a.duration : 0;
    const done = kind === 'complete' || (d > 0 && t / d > 0.85);
    logEvent(l.song, done ? 'complete' : 'skip', Math.round(done && d ? d : t));
  };
  useEffect(() => {
    if (!current || listenRef.current?.song.id === current.id) return;
    listenRef.current = { song: current };
    logEvent(current, 'play');
  }, [current?.id]);
  // Home = For You. Refresh it whenever you come back to it (your listening changed the mixes).
  useEffect(() => { if (view.page === 'home' && !sheetOpen) loadHome(); }, [view.page, sheetOpen]);
  useEffect(() => {
    if (!sheetOpen) return;
    const esc = (e) => { if (e.key === 'Escape') setSheetOpen(false); };
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [sheetOpen]);

  // Library auto-sync: the server watches the music folder; the UI just shows progress and reloads on change.
  const refreshLib = async () => {
    const st = await apiFetch(`${API}/library/status`).then((r) => r.json()).catch(() => null);
    if (!st) return;
    setLib(st);
    const p = prevLib.current;
    prevLib.current = st;
    if (p && ((p.running && !st.running) || p.counts?.tracks !== st.counts?.tracks)) { loadSongs(); loadUserPls(); loadHome(); }
  };
  useEffect(() => {
    refreshLib();
    const t = setInterval(refreshLib, 6000);
    return () => clearInterval(t);
  }, []);

  // Plays a whole shelf (Daily Mix, Discover, ...) as the normal queue
  const playShelf = (list, i = 0) => {
    if (!list.length) return;
    if (!current || list[i].id !== current.id) closeListen('skip');
    resetQueue(); ctxRef.current = list; setMode('normal'); setQueue(list); setQIdx(i); setIsPlaying(true);
    setMenuId(null);
  };

  const playSong = (song, list) => {
    if (!current || song.id !== current.id) closeListen('skip');
    resetQueue();
    ctxRef.current = list || [song];
    if (mode === 'normal') {
      const i = ctxRef.current.findIndex((s) => s.id === song.id);
      setQueue(ctxRef.current); setQIdx(Math.max(0, i));
    } else { setQueue([song]); setQIdx(0); }
    setIsPlaying(true); setMenuId(null);
  };

  const switchMode = (m) => {
    if (m === mode) return;
    resetQueue(); setMode(m);
    if (!current) return;
    if (m === 'rec') { setQueue([current]); setQIdx(0); return; }
    const list = ctxRef.current.length ? ctxRef.current : [current];
    const i = list.findIndex((s) => s.id === current.id);
    if (i < 0) { setQueue([current]); setQIdx(0); } else { setQueue(list); setQIdx(i); }
  };

  const togglePlay = () => {
    if (!audioRef.current || !current) return;
    if (isPlaying) { audioRef.current.pause(); setIsPlaying(false); }
    else { audioRef.current.play().catch(() => {}); setIsPlaying(true); }
  };
  const advance = () => { setQIdx((i) => (i < queue.length - 1 ? i + 1 : 0)); setIsPlaying(true); };
  const next = () => { closeListen('skip'); advance(); };
  const prev = () => {
    if (audioRef.current.currentTime > 3 || qIdx === 0) { audioRef.current.currentTime = 0; return; }
    closeListen('skip'); setQIdx(qIdx - 1); setIsPlaying(true);
  };

  const toggleLike = async (song) => {
    setMenuId(null);
    const was = liked.has(song.id);
    const flip = (on) => setLiked((p) => { const n = new Set(p); on ? n.add(song.id) : n.delete(song.id); return n; });
    flip(!was); // optimistic
    try {
      const r = await apiFetch(`${API}/likes/${song.id}`, { method: 'POST' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      logEvent(song, was ? 'unlike' : 'like');
    } catch (e) { flip(was); alert(`Could not save like (${e.message}). Is the backend running with extras.py loaded?`); }
  };

  const pickFolder = async (e) => {
    const f = e.target.files;
    if (!f.length) return;
    setBusy(true);
    try {
      const r = await apiFetch(`${API}/scan-folder`, { method: 'POST', headers: JSON_H, body: JSON.stringify({ folder_name: f[0].webkitRelativePath.split('/')[0] }) });
      if (!r.ok) alert((await r.json().catch(() => ({}))).detail || 'Could not use that folder (it must be inside your Music folder).');
      await loadSongs(); await refreshLib();
    } catch (err) { console.error(err); }
    setBusy(false); e.target.value = '';
  };

  const startAnalysis = async () => {
    await apiFetch(`${API}/analyze-moods`, { method: 'POST' });
    setAn((a) => ({ ...a, running: true }));
  };

  const go = (page, group = null, pl = null) => {
    setView({ page, group, pl }); setPicker(null); setMenuId(null); setPickQ(''); setBq(''); setGridLimit(120);
    setSheetOpen(false); // navigating pops the player down so you can see where you went
  };

  const openPlaylist = async (pl) => {
    const list = await apiFetch(`${API}/user-playlists/${pl.id}/tracks`).then((r) => r.json());
    setPlSongs(list.map((t) => songsRef.current.find((s) => s.id === t.id) || t));
    go('playlists', null, pl);
  };

  const addTo = async (pid, song) => {
    setMenuId(null);
    const r = await apiFetch(`${API}/user-playlists/${pid}/tracks`, { method: 'POST', headers: JSON_H, body: JSON.stringify({ track_ids: [song.id] }) });
    if (!r.ok) alert('Could not add song');
    else if (view.pl?.id === pid) setPlSongs((l) => (l.some((s) => s.id === song.id) ? l : [...l, song]));
  };

  const removeSong = async (song) => {
    setMenuId(null);
    if (view.page === 'likes') return toggleLike(song);
    if (view.pl) {
      await apiFetch(`${API}/user-playlists/${view.pl.id}/tracks/${song.id}`, { method: 'DELETE' });
      setPlSongs((l) => l.filter((s) => s.id !== song.id));
    }
  };

  const deletePlaylist = async () => {
    if (!window.confirm(`Delete playlist "${view.pl.name}"?`)) return;
    await apiFetch(`${API}/user-playlists/${view.pl.id}`, { method: 'DELETE' });
    await loadUserPls(); go('playlists');
  };

  const savePicker = async () => {
    if (!picked.size) return;
    if (picker.pl) {
      await apiFetch(`${API}/user-playlists/${picker.pl.id}/tracks`, { method: 'POST', headers: JSON_H, body: JSON.stringify({ track_ids: [...picked] }) });
      await openPlaylist(picker.pl);
    } else {
      if (!newName.trim()) { alert('Give the playlist a name first'); return; }
      const r = await apiFetch(`${API}/user-playlists/manual`, { method: 'POST', headers: JSON_H,
        body: JSON.stringify({ playlist_name: newName.trim(), track_ids: [...picked] }) });
      if (!r.ok) { alert((await r.json()).detail); return; }
      await loadUserPls(); go('playlists');
    }
    setPicked(new Set()); setNewName('');
  };

  const saveQueueAsPlaylist = async () => {
    const name = window.prompt('Name for this playlist:');
    if (!name || !name.trim()) return;
    await apiFetch(`${API}/user-playlists/snapshot`, { method: 'POST', headers: JSON_H,
      body: JSON.stringify({ playlist_name: name.trim(), track_paths: queue.slice(0, 100).map((s) => s.file_path) }) });
    loadUserPls();
  };

  const moveTo = async (pid, song) => {
    setMenuId(null);
    const r = await apiFetch(`${API}/user-playlists/${pid}/tracks`, { method: 'POST', headers: JSON_H, body: JSON.stringify({ track_ids: [song.id] }) });
    if (!r.ok) { alert('Could not move song'); return; }
    await apiFetch(`${API}/user-playlists/${view.pl.id}/tracks/${song.id}`, { method: 'DELETE' });
    setPlSongs((l) => l.filter((s) => s.id !== song.id));
  };

  act.current = { play: (s, ctx) => playSong(s, shownRef.current[ctx]), pls: userPls, liked, menu: setMenuId, like: toggleLike, addTo, remove: removeSong,
    move: moveTo, plId: view.pl?.id };

  // ---------- shared bits ----------
  const match = (s, q) => [s.title, s.artist, s.album].some((v) => v && v.toLowerCase().includes(q.toLowerCase()));
  const renderList = (list, removable = false, ctx = 'left', inPl = false) => {
    shownRef.current[ctx] = list;
    return (
      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {list.length === 0 ? <p style={{ color: C.dim }}>Nothing here yet.</p>
          : list.map((s) => <SongRow key={s.id} song={s} active={current?.id === s.id} open={menuId === `${ctx}:${s.id}`}
              removable={removable} inPl={inPl} ctx={ctx} act={act} />)}
      </ul>
    );
  };
  const Back = (to, label) => <button onClick={to} style={{ ...btn, marginBottom: 12, padding: '8px 14px' }}>← {label}</button>;
  const field = { width: '100%', boxSizing: 'border-box', padding: '10px 14px', borderRadius: 20, border: 'none', background: C.hover, color: '#fff', marginBottom: 8, outline: 'none' };
  const box = (ph, value, set) => <input value={value} onChange={(e) => set(e.target.value)} placeholder={ph} style={field} />;
  const grid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: 14 };
  const label150 = { width: 150, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' };
  const byId = new Map(songs.map((s) => [s.id, s]));

  const renderPicker = () => {
    const have = picker.pl ? new Set(plSongs.map((s) => s.id)) : new Set();
    const list = songs.filter((s) => !have.has(s.id) && match(s, pickQ));
    return (
      <>
        <div style={{ position: 'sticky', top: 0, background: C.bg, paddingBottom: 8, zIndex: 5 }}>
          {Back(() => (picker.pl ? setPicker(null) : go('playlists')), 'Back')}
          {!picker.pl && <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Playlist name" style={field} />}
          <input value={pickQ} onChange={(e) => setPickQ(e.target.value)} placeholder="Search songs…" style={field} />
          <button onClick={savePicker} style={{ ...btn, background: C.green, width: '100%', textAlign: 'center' }}>
            {picker.pl ? 'Add to playlist' : 'Create playlist'} ({picked.size} selected)</button>
        </div>
        {list.map((s) => (
          <label key={s.id} className="cv" style={{ display: 'flex', gap: 8, padding: 6, fontSize: 14, cursor: 'pointer' }}>
            <input type="checkbox" checked={picked.has(s.id)}
              onChange={() => setPicked((p) => { const n = new Set(p); n.has(s.id) ? n.delete(s.id) : n.add(s.id); return n; })} />
            {s.title} <span style={{ color: C.dim }}>· {s.artist}</span>
          </label>
        ))}
      </>
    );
  };

  // ---------- left: always your whole library ----------
  const renderLeft = () => (
    <>
      <h3>🎧 Your Songs</h3>
      {box('Search tracks, artists, albums...', search, setSearch)}
      {renderList(songs.filter((s) => match(s, search)), false, 'left')}
    </>
  );

  // ---------- middle: browse area (For You, album/artist/language cards, playlists) ----------
  const renderDetail = ({ kind, title, list, back, actions = null, removable = false, inPl = false, ph = 'Search songs…' }) => {
    const shown = list.filter((s) => match(s, bq));
    return (
      <div style={{ width: '100%', minWidth: 0 }}>
        {back && Back(back[0], back[1])}
        <div style={{ display: 'flex', gap: 20, alignItems: 'flex-end', marginBottom: 18, flexWrap: 'wrap' }}>
          <Collage list={list} />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 12, color: C.dim, textTransform: 'uppercase' }}>{kind}</div>
            <h2 style={{ margin: '4px 0' }}>{title}</h2>
            <div style={{ color: C.dim, marginBottom: 12 }}>{list.length} song{list.length === 1 ? '' : 's'}</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button disabled={!list.length} onClick={() => playShelf(list, 0)} style={{ ...btn, background: C.green, padding: '8px 18px' }}>▶ Play all</button>
              {actions}
            </div>
          </div>
        </div>
        {box(ph, bq, setBq)}
        {renderList(shown, removable, 'mid', inPl)}
      </div>
    );
  };

  const renderBrowse = () => {
    const { page, group, pl } = view;
    if (page === 'home') return <ForYou home={home} byId={byId} onPlay={playShelf} />;
    if (FIELD[page]) {
      const f = FIELD[page];
      if (group !== null)
        return renderDetail({ kind: page.slice(0, -1), title: group, list: songs.filter((s) => (s[f] || 'Unknown') === group),
          back: [() => go(page), `All ${page}`] });
      const groups = {};
      for (const s of songs) { const k = s[f] || 'Unknown'; (groups[k] = groups[k] || []).push(s); }
      const entries = Object.entries(groups).filter(([k]) => k.toLowerCase().includes(bq.toLowerCase())).sort((a, b) => a[0].localeCompare(b[0]));
      return (
        <div style={{ width: '100%', minWidth: 0 }}>
          <h2 style={{ marginTop: 0, textTransform: 'capitalize' }}>{page}</h2>
          {box(`Search ${page}…`, bq, setBq)}
          <div style={grid}>
            {entries.slice(0, gridLimit).map(([k, l]) => (
              <div key={k} className="card" onClick={() => go(page, k)}>
                <Collage list={l} />
                <div style={{ ...label150, fontWeight: 700, marginTop: 8 }}>{k}</div>
                <div style={{ ...label150, fontSize: 12, color: C.dim }}>{l.length} song{l.length === 1 ? '' : 's'}</div>
              </div>
            ))}
          </div>
          {entries.length > gridLimit && (
            <button onClick={() => setGridLimit((n) => n + 120)} style={{ ...btn, margin: '16px auto', display: 'block' }}>
              Show more ({entries.length - gridLimit} left)</button>
          )}
        </div>
      );
    }
    if (page === 'likes')
      return renderDetail({ kind: 'Playlist', title: '♥ Liked songs', list: songs.filter((s) => liked.has(s.id)), removable: true, ph: 'Search liked songs…' });
    if (picker) return <div style={{ width: '100%', minWidth: 0 }}>{renderPicker()}</div>;
    if (pl)
      return renderDetail({
        kind: pl.is_mood ? 'Mood playlist' : 'Playlist', title: pl.name, list: plSongs, back: [() => go('playlists'), 'Playlists'],
        removable: true, inPl: true, ph: 'Search this playlist…',
        actions: (
          <>
            <button onClick={() => { setPicker({ pl }); setPicked(new Set()); }} style={{ ...btn, padding: '8px 14px', background: '#2a2a2a' }}>＋ Add songs</button>
            {!pl.is_mood && <button onClick={deletePlaylist} style={{ ...btn, padding: '8px 14px', background: '#5a1d1d' }}>🗑 Delete</button>}
          </>
        ),
      });
    const byName = (p) => p.name.toLowerCase().includes(bq.toLowerCase());
    const moods = userPls.filter((p) => p.is_mood && byName(p)), mine = userPls.filter((p) => !p.is_mood && byName(p));
    const plCard = (p) => (
      <div key={p.id} className="card" onClick={() => openPlaylist(p)}>
        <Tile icon={MOOD_ICON[p.name] || '🎵'} />
        <div style={{ ...label150, fontWeight: 700, marginTop: 8 }}>{p.name}</div>
        <div style={{ ...label150, fontSize: 12, color: C.dim }}>{p.is_mood ? 'Mood playlist' : 'Your playlist'}</div>
      </div>
    );
    return (
      <div style={{ width: '100%', minWidth: 0 }}>
        <h2 style={{ marginTop: 0 }}>Playlists</h2>
        {box('Search playlists…', bq, setBq)}
        <div style={{ color: C.dim, fontSize: 12, margin: '12px 0' }}>🎭 MOOD PLAYLISTS</div>
        {moods.length ? <div style={grid}>{moods.map(plCard)}</div>
          : <p style={{ color: C.dim, fontSize: 13 }}>Not sorted yet. Use "Sort by mood" at the top.</p>}
        <div style={{ color: C.dim, fontSize: 12, margin: '22px 0 12px' }}>YOUR PLAYLISTS</div>
        <div style={grid}>
          {mine.map(plCard)}
          <div className="card" onClick={() => { setPicker({}); setPicked(new Set()); setNewName(''); }}>
            <Tile icon="＋" />
            <div style={{ ...label150, fontWeight: 700, marginTop: 8 }}>Create playlist</div>
          </div>
        </div>
      </div>
    );
  };

  // ---------- player: popped-down bar + popped-up sheet ----------
  const circle = { background: '#fff', border: 'none', width: 56, height: 56, borderRadius: '50%', cursor: 'pointer', fontSize: 20, color: '#000' };
  const ico = { background: 'none', border: 'none', color: '#fff', fontSize: 30, cursor: 'pointer' };
  const pill = (m, label) => (
    <button onClick={() => switchMode(m)} style={{ flex: 1, padding: '7px 4px', border: 'none', borderRadius: 16, cursor: 'pointer', fontSize: 12, fontWeight: 'bold',
      background: mode === m ? C.green : C.hover, color: '#fff' }}>{label}</button>
  );
  const stop = (fn) => (e) => { e.stopPropagation(); fn(e); }; // controls must not pop the player up

  // Clicking ANYWHERE on this bar pops the player up (the controls only do their own job).
  const renderMiniBar = () => (
    <div onClick={() => setSheetOpen(true)} title="Open player"
      style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: BAR_H, background: C.card, borderTop: '1px solid #282828', zIndex: 20,
        display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(260px,420px) minmax(0,1fr)', alignItems: 'center', gap: 16, padding: '0 20px',
        cursor: 'pointer', boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
        <img src={cover(current)} alt="" style={{ width: 56, height: 56, borderRadius: 8, objectFit: 'cover', background: '#282828', flexShrink: 0 }} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <Marquee text={current.title} style={{ fontSize: 14, fontWeight: 700 }} />
          <Marquee text={current.artist || 'Unknown'} reverse style={{ fontSize: 12, color: C.dim, marginTop: 2 }} />
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, minWidth: 0 }}>
        <button onClick={stop(togglePlay)} style={{ ...circle, width: 38, height: 38, fontSize: 15 }}>{isPlaying ? '⏸' : '▶'}</button>
        <div onClick={(e) => e.stopPropagation()} style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', cursor: 'default' }}>
          <button onClick={stop(prev)} style={{ ...ico, fontSize: 20 }}>⏮</button>
          <Seek key={current.id} audioRef={audioRef} fluid />
          <button onClick={stop(next)} style={{ ...ico, fontSize: 20 }}>⏭</button>
        </div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button onClick={stop(() => toggleLike(current))} style={{ ...ico, fontSize: 22, color: liked.has(current.id) ? C.green : '#fff' }}>
          {liked.has(current.id) ? '♥' : '♡'}</button>
      </div>
    </div>
  );

  // Slide-down handle: drag it down (or click it) to pop the player down.
  const onHandleDown = (e) => { dragRef.current = { y: e.clientY, moved: false }; setDragging(true); e.currentTarget.setPointerCapture(e.pointerId); };
  const onHandleMove = (e) => {
    if (!dragRef.current) return;
    const dy = Math.max(0, e.clientY - dragRef.current.y);
    if (dy > 4) dragRef.current.moved = true;
    setDrag(dy);
  };
  const onHandleUp = () => {
    const d = dragRef.current;
    dragRef.current = null; setDragging(false);
    if (d && (!d.moved || drag > 90)) setSheetOpen(false);
    setDrag(0);
  };

  const renderSheet = () => {
    const upcoming = queue.slice(qIdx, qIdx + 30);
    return (
      <div aria-hidden={!sheetOpen}
        style={{ position: 'absolute', inset: 0, zIndex: 30, background: C.bg, display: 'flex', flexDirection: 'column', overflowY: 'auto',
          transform: sheetOpen ? `translateY(${drag}px)` : 'translateY(100%)', transition: dragging ? 'none' : 'transform .3s ease',
          pointerEvents: sheetOpen ? 'auto' : 'none', boxShadow: sheetOpen ? '0 -10px 30px rgba(0,0,0,.6)' : 'none', borderRadius: '16px 16px 0 0' }}>
        <div onPointerDown={onHandleDown} onPointerMove={onHandleMove} onPointerUp={onHandleUp} onPointerCancel={onHandleUp} title="Drag down or click to close"
          style={{ padding: '12px 0 10px', cursor: 'grab', touchAction: 'none', display: 'flex', justifyContent: 'center', flexShrink: 0 }}>
          <div style={{ width: 48, height: 5, borderRadius: 3, background: '#666' }} />
        </div>
        <div style={{ display: 'flex', gap: 24, padding: '0 24px 24px', flex: 1, minHeight: 0 }}>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 320 }}>
            <img src={cover(current)} alt="cover" style={{ width: 280, height: 280, borderRadius: 12, objectFit: 'cover', background: '#282828' }} />
            <Marquee text={current.title} style={{ width: 300, textAlign: 'center', fontSize: 20, fontWeight: 700, marginTop: 14 }} />
            <Marquee text={current.artist || 'Unknown'} reverse style={{ width: 300, textAlign: 'center', color: C.dim, marginTop: 4 }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 24, margin: '16px 0 8px' }}>
              <button onClick={prev} style={ico}>⏮</button>
              <button onClick={togglePlay} style={circle}>{isPlaying ? '⏸' : '▶'}</button>
              <button onClick={next} style={ico}>⏭</button>
              <button onClick={() => toggleLike(current)} style={{ ...ico, color: liked.has(current.id) ? C.green : '#fff' }}>
                {liked.has(current.id) ? '♥' : '♡'}</button>
            </div>
            <Seek key={current.id} audioRef={audioRef} />
            <div className="opts">
              <Opt icon="💿" label="Go to album" onClick={() => go('albums', current.album || 'Unknown')} />
              <Opt icon="🎙️" label="Go to artist" onClick={() => go('artists', current.artist || 'Unknown')} />
              <Opt icon="🌐" label="Go to language" onClick={() => go('languages', current.language || 'Unknown')} />
              <Opt icon="➕" label="Create playlist" onClick={saveQueueAsPlaylist} />
              <Opt icon="♥" label="Go to likes" onClick={() => go('likes')} />
            </div>
          </div>
          <div style={{ width: 260, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ display: 'flex', gap: 6, margin: '0 0 10px' }}>{pill('normal', '📋 Normal queue')}{pill('rec', '✨ Recommended')}</div>
            <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
              {upcoming.map((s, k) => (
                <div key={`${s.id}-${qIdx + k}`} onClick={() => { if (k > 0) closeListen('skip'); setQIdx(qIdx + k); setIsPlaying(true); }} className="row"
                  style={{ padding: '7px 10px', background: k === 0 ? '#1f3d2b' : C.card, borderRadius: 6, marginBottom: 4, cursor: 'pointer', fontSize: 12 }}>
                  <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.title}</div>
                  <div style={{ color: C.dim, display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.artist}</span>
                    <span style={{ color: C.green, flexShrink: 0 }}>{k === 0 ? 'Playing' : k === 1 ? 'Up next' : ''}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const NAV = [['home', '🏠 Home'], ['albums', '💿 Albums'], ['artists', '🎙️ Artists'], ['languages', '🌐 Languages'], ['likes', '♥ Liked'], ['playlists', '📋 Playlists']];
  const inDetail = view.group !== null || !!view.pl || !!picker;

  let sync = null;
  if (lib?.running) sync = [`⟳ ${lib.stage === 'embedding' ? 'Analysing' : lib.stage === 'moods' ? 'Sorting moods for' : 'Adding'} new songs…${lib.total ? ` ${lib.done}/${lib.total}` : ''}`, C.dim];
  else if (lib?.error) sync = [`⚠ ${lib.error}`, '#e0a050'];
  else if (lib && lib.auto_sync && !lib.folder_configured) sync = ['📁 Choose your music folder to turn on automatic syncing', '#e0a050'];

  return (
    <div style={{ height: '100vh', background: C.bg, color: '#fff', fontFamily: '"Segoe UI", Roboto, sans-serif', display: 'flex', flexDirection: 'column' }}>
      <style>{css}</style>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 24px', borderBottom: '1px solid #282828' }}>
        <h2 style={{ margin: 0 }}>MusicHub</h2>
        <div style={{ display: 'flex', gap: 10, minWidth: 0 }}>
          {sync && <span title={sync[0]} style={{ fontSize: 12, color: sync[1], alignSelf: 'center', maxWidth: 420, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sync[0]}</span>}
          <button onClick={startAnalysis} disabled={an.running} style={{ ...btn, borderRadius: 20, background: '#2a2a2a' }}>
            {an.running ? `Analysing ${an.done}/${an.total}…` : '🎭 Sort by mood'}</button>
          <input ref={folderRef} type="file" webkitdirectory="" directory="" multiple onChange={pickFolder} style={{ display: 'none' }} />
          <button onClick={() => folderRef.current.click()} disabled={busy} style={{ ...btn, background: C.green, borderRadius: 20 }}>
            {busy ? 'Scanning…' : '📁 Choose folder'}</button>
        </div>
      </div>
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '360px 1fr 190px', minHeight: 0 }}>
        <aside style={{ padding: 16, overflowY: 'auto', borderRight: '1px solid #282828' }}>{renderLeft()}</aside>
        <main style={{ position: 'relative', overflow: 'hidden', minWidth: 0 }}>
          <div style={{ height: '100%', overflowY: 'auto', display: 'flex', padding: 24, paddingBottom: current ? BAR_H + 24 : 24, boxSizing: 'border-box' }}>
            {renderBrowse()}
          </div>
          {current && renderMiniBar()}
          {current && renderSheet()}
        </main>
        <nav style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10, borderLeft: '1px solid #282828' }}>
          {NAV.filter(([p]) => p !== view.page || inDetail).map(([p, label]) => <button key={p} onClick={() => go(p)} style={btn}>{label}</button>)}
        </nav>
      </div>
      <audio ref={audioRef} src={current ? `${API}/audio/${encodeURIComponent(current.file_path)}` : ''} onEnded={() => { closeListen('complete'); advance(); }} />
    </div>
  );
}
