"""Taste profile + auto-playlists for the "For You" home screen.

Pipeline:  listen_events -> decayed per-track signal -> taste vector + artist/genre/language affinity
           -> score every track -> diversity-capped picks -> shelves (Daily Mix, Discover, ...)

Signals per event:  complete +1, like +2, unlike -2, early skip (<30s) -1, late skip -0.3.
Each signal fades with a 14-day half-life, so the profile follows your current taste.
"""
import datetime
import hashlib
import sqlite3 as sql
import threading
import time
from collections import Counter, defaultdict
from typing import Optional

import numpy as np
from fastapi import APIRouter, Header, HTTPException

from config import DB_PATH
from identity import owner

router = APIRouter()

HALF_LIFE_DAYS = 14.0
MIN_SIGNALS = 5          # positive listens needed before personal mixes unlock
MIN_SHELF = 5            # shelves with fewer tracks are hidden
BONUS = {"artist": 0.05, "genre": 0.03, "language": 0.03}
UNKNOWN = {None, "", "unknown", "Unknown", "Unknown Artist"}

_lock = threading.Lock()
_lib = None
_sig = None


def invalidate():
    global _lib, _sig
    with _lock:
        _lib, _sig = None, None


def _signature():
    c = sql.connect(DB_PATH, timeout=30)
    try:
        return c.execute("SELECT COUNT(*), COUNT(embedding), COUNT(vector_data), MAX(id) FROM tracks").fetchone()
    except sql.OperationalError:
        return None
    finally:
        c.close()


# ------------------------------------------------------------------ library (cached)
def _build_library():
    c = sql.connect(DB_PATH, timeout=30)
    try:
        rows = c.execute("SELECT id, title, artist, album, genre, language, cluster_id, embedding, vector_data "
                         "FROM tracks").fetchall()
    except sql.OperationalError:  # older DB without language/embedding columns
        rows = [r + (None, None) for r in c.execute(
            "SELECT id, title, artist, album, genre, NULL, cluster_id FROM tracks").fetchall()]
    c.close()
    n = len(rows)
    lib = {"n": n, "ids": [r[0] for r in rows], "title": [r[1] for r in rows], "artist": [r[2] for r in rows],
           "album": [r[3] for r in rows], "genre": [r[4] for r in rows], "language": [r[5] for r in rows],
           "cluster": [r[6] for r in rows], "idx": {r[0]: i for i, r in enumerate(rows)}}
    emb = [np.frombuffer(r[7], np.float32) if r[7] else None for r in rows]
    dims = Counter(v.shape[0] for v in emb if v is not None)
    if dims and sum(dims.values()) >= 0.5 * n:           # prefer pretrained embeddings
        dim, src = dims.most_common(1)[0][0], "embedding"
        vecs = [v if v is not None and v.shape[0] == dim else None for v in emb]
    else:                                                # fall back to the mel fingerprint
        vecs = [np.frombuffer(r[8], np.float32) if r[8] else None for r in rows]
        dim, src = 128, "mel"
        vecs = [v if v is not None and v.shape[0] == dim else None for v in vecs]
    has = np.array([v is not None for v in vecs], dtype=bool)
    mat = np.zeros((n, dim), dtype=np.float32)
    for i, v in enumerate(vecs):
        if v is not None:
            mat[i] = v
    if src == "mel" and has.any():                       # raw dB vectors need standardising first
        mat[has] = (mat[has] - mat[has].mean(0)) / (mat[has].std(0) + 1e-9)
    mat /= (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
    lib.update(mat=mat, has=has, source=src)
    return lib


def _library():
    global _lib, _sig
    sig = _signature()
    with _lock:
        if _lib is None or sig != _sig:
            _lib, _sig = _build_library(), sig
        return _lib


# ------------------------------------------------------------------ signals + profile
def _load_events(client_id):
    c = sql.connect(DB_PATH, timeout=30)
    try:
        ev = c.execute("SELECT track_id, event, seconds, ts FROM listen_events WHERE client_id=? ORDER BY ts",
                       (client_id,)).fetchall()
    except sql.OperationalError:
        ev = []
    seeds = set()
    try:  # your existing likes count as taste signals too
        seeds = {r[0] for r in c.execute("SELECT track_id FROM likes WHERE owner=?", (client_id,))}
    except sql.OperationalError:
        pass
    c.close()
    return ev, seeds


def _signals_from(ev, seeds, now):
    """Pure function: an event list -> decayed per-track signals as of time `now`."""
    decay = lambda ts: 0.5 ** ((now - ts) / 86400.0 / HALF_LIFE_DAYS)
    net = defaultdict(float)
    last_pos, last_played, liked, n_pos = {}, {}, set(), 0
    for t, e, sec, ts in ev:
        if e == "play":
            last_played[t] = max(last_played.get(t, 0), ts)
            continue
        if e == "complete":
            w = 1.0
        elif e == "like":
            w = 2.0
            liked.add(t)
        elif e == "unlike":
            w = -2.0
            liked.discard(t)
        elif e == "skip":
            w = -1.0 if sec < 30 else -0.3
        else:
            continue
        net[t] += w * decay(ts)
        last_played[t] = max(last_played.get(t, 0), ts)
        if w > 0:
            last_pos[t] = max(last_pos.get(t, 0), ts)
            n_pos += 1
    already = {t for t, e, _, _ in ev if e in ("like", "unlike")}
    for t in seeds - already:
        ts = now - 7 * 86400
        net[t] += 2.0 * decay(ts)
        liked.add(t)
        last_pos[t] = max(last_pos.get(t, 0), ts)
        n_pos += 1
    return dict(net=net, last_pos=last_pos, last_played=last_played, liked=liked, n_pos=n_pos)


def _signals(client_id):
    ev, seeds = _load_events(client_id)
    return _signals_from(ev, seeds, time.time())


def _profile(lib, net):
    idx, has, mat = lib["idx"], lib["has"], lib["mat"]
    pos = [(idx[t], w) for t, w in net.items() if w > 0 and t in idx and has[idx[t]]]
    neg = [(idx[t], -w) for t, w in net.items() if w < 0 and t in idx and has[idx[t]]]
    if not pos:
        return None
    taste = sum(w * mat[i] for i, w in pos)
    taste = taste / (np.linalg.norm(taste) + 1e-9)
    if neg:
        bad = sum(w * mat[i] for i, w in neg)
        taste = taste - 0.5 * bad / (np.linalg.norm(bad) + 1e-9)
        taste = taste / (np.linalg.norm(taste) + 1e-9)
    aff = {}
    for f in BONUS:
        d = defaultdict(float)
        for t, w in net.items():
            if w > 0 and t in idx and lib[f][idx[t]] not in UNKNOWN:
                d[lib[f][idx[t]]] += w
        m = max(d.values(), default=1.0)
        aff[f] = {k: v / m for k, v in d.items()}
    return {"taste": taste, "aff": aff, "pos": pos}


# ------------------------------------------------------------------ scoring + picking
def _score(lib, vec, aff, net, noise, w=None):
    """w = (sim, artist, genre, language) weights: hand-picked defaults, or learned by ranker.py."""
    ws = w if w is not None else (1.0, BONUS["artist"], BONUS["genre"], BONUS["language"])
    s = ws[0] * (lib["mat"] @ vec)
    for f, b in zip(("artist", "genre", "language"), ws[1:]):
        s = s + b * np.array([aff[f].get(v, 0.0) for v in lib[f]], dtype=np.float32)
    for t, w in net.items():                       # songs you tend to skip sink
        if w < 0 and t in lib["idx"]:
            s[lib["idx"][t]] -= min(0.3, 0.15 * -w)
    s = s + noise
    s[~lib["has"]] = -np.inf
    return s


def _pick(lib, scores, n=25, per_artist=3, exclude=(), rel_floor=0.0):
    """Greedy top-n with an artist cap. rel_floor drops anything scoring below that fraction of the best."""
    finite = scores[np.isfinite(scores)]
    floor = rel_floor * finite.max() if len(finite) and finite.max() > 0 else -np.inf
    out, cnt = [], Counter()
    for i in np.argsort(-scores):
        if len(out) >= n or not np.isfinite(scores[i]) or scores[i] < floor:
            break
        if i in exclude:
            continue
        a = lib["artist"][i]
        if a not in UNKNOWN:
            if cnt[a] >= per_artist:
                continue
            cnt[a] += 1
        out.append(int(i))
    return out


def _kmeans(X, w, k, iters=8):
    chosen = [int(np.argmax(w))]
    while len(chosen) < k:
        chosen.append(int(np.argmin((X @ X[chosen].T).max(axis=1))))
    C = X[chosen].copy()
    for _ in range(iters):
        lab = (X @ C.T).argmax(1)
        for j in range(k):
            m = lab == j
            if m.any():
                v = (X[m] * w[m, None]).sum(0)
                C[j] = v / (np.linalg.norm(v) + 1e-9)
    return C, (X @ C.T).argmax(1)


def _ids(lib, picks):
    return [lib["ids"][i] for i in picks]


def _subtitle(lib, picks):
    names = [a for a, _ in Counter(lib["artist"][i] for i in picks if lib["artist"][i] not in UNKNOWN).most_common(3)]
    return (", ".join(names) + " and more") if names else "Made for you"


# ------------------------------------------------------------------ home builder
def build_home(client_id):
    lib = _library()
    if not lib["n"]:
        return {"unlocked": False, "needed": MIN_SIGNALS, "source": None, "sections": []}
    sig = _signals(client_id)
    prof = _profile(lib, sig["net"])
    unlocked = prof is not None and sig["n_pos"] >= MIN_SIGNALS
    today = datetime.date.today().isoformat()
    rng = np.random.default_rng(int(hashlib.md5(f"{client_id}-{today}".encode()).hexdigest()[:8], 16))
    noise = rng.normal(0, 0.02, lib["n"]).astype(np.float32)
    sections = []

    if not unlocked:  # cold start: one random song from each audio cluster
        by_cluster = defaultdict(list)
        for i in range(lib["n"]):
            by_cluster[lib["cluster"][i]].append(i)
        picks = [int(rng.choice(v)) for _, v in sorted(by_cluster.items(), key=lambda kv: str(kv[0]))]
        rng.shuffle(picks)
        sections.append({"id": "explore", "title": "Explore your library", "kind": "songs",
                         "track_ids": _ids(lib, picks[:24])})
        return {"unlocked": False, "needed": max(0, MIN_SIGNALS - sig["n_pos"]), "source": lib["source"],
                "sections": sections}

    taste, aff, net, idx = prof["taste"], prof["aff"], sig["net"], lib["idx"]
    played = {idx[t] for t in sig["last_played"] if t in idx}
    import ranker  # lazy: ranker imports this module
    w = ranker.get_weights(client_id)      # None until it has proven itself on held-out data
    ranker.maybe_train_async(client_id)
    base = _score(lib, taste, aff, net, noise, w)

    # --- Daily Mixes: cluster the songs you like, one mix per cluster
    pos_i = np.array([i for i, _ in prof["pos"]])
    pos_w = np.array([w for _, w in prof["pos"]], dtype=np.float32)
    top = np.argsort(-pos_w)[:200]
    pos_i, pos_w = pos_i[top], pos_w[top]
    k = 1 if len(pos_i) < 6 else min(5, len(pos_i) // 3)
    if k > 1:
        C, lab = _kmeans(lib["mat"][pos_i], pos_w, k)
        order = sorted(range(k), key=lambda j: -pos_w[lab == j].sum())
        cents = [C[j] for j in order]
    else:
        cents = [taste]
    used, mixes = set(), []
    for n_, cvec in enumerate(cents, 1):
        picks = _pick(lib, _score(lib, cvec, aff, net, noise, w), n=30, exclude=used, rel_floor=0.6)
        if len(picks) >= MIN_SHELF:
            used.update(picks)
            mixes.append({"id": f"mix-{n_}", "title": f"Daily Mix {n_}", "subtitle": _subtitle(lib, picks),
                          "track_ids": _ids(lib, picks)})
    if mixes:
        sections.append({"id": "made-for-you", "title": "Made for you", "kind": "playlists", "items": mixes})

    # --- On Repeat / Discover / Rediscover
    picks_items = []
    cutoff = time.time() - 30 * 86400
    rep = [t for t, w in sorted(net.items(), key=lambda kv: -kv[1])
           if w > 0 and t in idx and sig["last_pos"].get(t, 0) >= cutoff][:20]
    if len(rep) >= MIN_SHELF:
        picks_items.append({"id": "on-repeat", "title": "On Repeat", "subtitle": "Songs you keep coming back to",
                            "track_ids": rep})
    disc = _pick(lib, base, n=25, exclude=played, rel_floor=0.5)
    if len(disc) >= MIN_SHELF:
        picks_items.append({"id": "discover", "title": "Discover", "subtitle": "New to you, close to your taste",
                            "track_ids": _ids(lib, disc)})
    old = [t for t in sig["liked"] if t in idx and sig["last_played"].get(t, 0) < cutoff]
    old.sort(key=lambda t: -float(noise[idx[t]]))
    if len(old) >= MIN_SHELF:
        picks_items.append({"id": "rediscover", "title": "Rediscover", "subtitle": "Liked songs you haven't played lately",
                            "track_ids": old[:25]})
    if picks_items:
        sections.append({"id": "your-picks", "title": "Jump back in", "kind": "playlists", "items": picks_items})

    # --- Because you played X
    recent = sorted((t for t in sig["last_pos"] if t in idx and lib["has"][idx[t]]), key=lambda t: -sig["last_pos"][t])
    if recent:
        i = idx[recent[0]]
        sim = lib["mat"] @ lib["mat"][i]
        sim[i] = -np.inf
        sim[~lib["has"]] = -np.inf
        picks = _pick(lib, sim, n=20)
        if len(picks) >= MIN_SHELF:
            sections.append({"id": "because", "title": f"Because you played {lib['title'][i]}", "kind": "songs",
                             "track_ids": _ids(lib, picks)})

    # --- More from your top artist / top language
    for field, label in (("artist", "More from {}"), ("language", "Your {} picks")):
        ranked = sorted(aff[field].items(), key=lambda kv: -kv[1])
        if not ranked:
            continue
        name = ranked[0][0]
        members = np.array([lib[field][i] == name for i in range(lib["n"])])
        if members.sum() < (MIN_SHELF if field == "artist" else 8):
            continue
        s = np.where(members, base, -np.inf)
        picks = _pick(lib, s, n=25, per_artist=25 if field == "artist" else 3)
        if len(picks) >= MIN_SHELF:
            sections.append({"id": f"top-{field}", "title": label.format(name), "kind": "songs",
                             "track_ids": _ids(lib, picks)})

    return {"unlocked": True, "needed": 0, "source": lib["source"], "sections": sections,
            "ranker": ranker.status(client_id)}


@router.get("/api/home")
def home(x_client_id: Optional[str] = Header(default=None)):
    return build_home(owner(x_client_id))


@router.get("/api/ranker")
def ranker_status(x_client_id: Optional[str] = Header(default=None)):
    """Is the learned ranker active for this listener, and how did it score on held-out data?"""
    import ranker
    return ranker.status(owner(x_client_id))
