"""Learned ranker (step 4): fits the For-You scoring weights to ONE listener's own behaviour.

Training data: every 'complete' (label 1) and 'skip' (label 0) event. For each one, the features
are computed from the history BEFORE that event (no leakage):
    sim       cosine(track, taste vector)
    artist / genre / language   affinity of that track's artist / genre / language (0..1)
Model: logistic regression (NumPy, L2). Coefficients are clipped to >= 0 (negative weights make no sense
here) and rescaled to the same total as the defaults, so they drop straight into taste._score and the
noise / skip-penalty terms keep their meaning.

Guard rails: it only replaces the hand-picked defaults if, on the LATEST 30% of events (time split),
it beats them by more than chance (>= max(0.02, one null standard error of AUC)).
"""
import math
import sqlite3 as sql
import threading
import time

import numpy as np

import taste
from config import DB_PATH

FEATURES = ("sim", "artist", "genre", "language")
DEFAULT_W = np.array([1.0, taste.BONUS["artist"], taste.BONUS["genre"], taste.BONUS["language"]])
MIN_LABELS = 100
HOLDOUT = 0.30
MIN_GAIN = 0.02
MAX_LABELS = 1500

_lock = threading.Lock()
_running = set()


def _db():
    c = sql.connect(DB_PATH, timeout=30)
    c.execute("""CREATE TABLE IF NOT EXISTS ranker_weights (
        owner TEXT PRIMARY KEY, w_sim REAL, w_artist REAL, w_genre REAL, w_language REAL, n_labels INTEGER,
        auc_learned REAL, auc_default REAL, adopted INTEGER, trained_at REAL)""")
    return c


def _f(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


# ------------------------------------------------------------------ math
def fit_logreg(X, y, l2=1.0, iters=30):
    """Newton/IRLS logistic regression. Returns [coef..., intercept]."""
    Xb = np.hstack([X, np.ones((len(X), 1))])
    pen = np.r_[np.ones(Xb.shape[1] - 1), 0.0]
    w = np.zeros(Xb.shape[1])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(Xb @ w, -30, 30)))
        g = Xb.T @ (p - y) + l2 * pen * w
        H = (Xb.T * (p * (1 - p))) @ Xb + l2 * np.diag(pen) + 1e-6 * np.eye(len(w))
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-7:
            break
    return w


def auc(scores, y):
    y = np.asarray(y)
    n1 = int(y.sum())
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    scores = np.asarray(scores, dtype=float)
    order = np.argsort(scores, kind="mergesort")
    s = scores[order]
    ranks = np.empty(len(s))
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1
        i = j + 1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


SIM_FLOOR = 0.25  # share of the total weight that always stays on sound similarity


def _deployable(coef):
    """Clip to >= 0, rescale to the default total, and keep at least SIM_FLOOR on sound similarity.
    The floor matters because finish-vs-skip data mostly describes artists you already play; with
    sim at zero, songs by NEW artists would all tie and Discover would turn random."""
    v = np.clip(coef, 0.0, None)
    if v.sum() <= 1e-9:
        return None
    tot = DEFAULT_W.sum()
    v = v / v.sum() * tot
    floor = SIM_FLOOR * tot
    if v[0] < floor:
        rest = v[1:]
        rest = rest / rest.sum() * (tot - floor) if rest.sum() > 0 else rest
        v = np.r_[floor, rest]
    return v


def _clears_noise(auc_l, auc_d, n1, n0):
    se0 = math.sqrt((n1 + n0 + 1) / (12.0 * n1 * n0))  # std error of AUC when there is no signal
    return auc_l - auc_d >= max(MIN_GAIN, se0)


# ------------------------------------------------------------------ features
def _feature_rows(lib, ev):
    idx = lib["idx"]
    labelled = [k for k, (t, e, _, _) in enumerate(ev)
                if e in ("complete", "skip") and t in idx and lib["has"][idx[t]]]
    rows = []
    for k in labelled[-MAX_LABELS:]:
        t, e, _, ts = ev[k]
        sig = taste._signals_from(ev[:k], set(), ts)
        if sig["n_pos"] < 3:
            continue
        prof = taste._profile(lib, sig["net"])
        if prof is None:
            continue
        i = idx[t]
        x = [float(lib["mat"][i] @ prof["taste"])] + [prof["aff"][f].get(lib[f][i], 0.0)
                                                      for f in ("artist", "genre", "language")]
        rows.append((ts, x, 1.0 if e == "complete" else 0.0))
    return rows, len(labelled)


# ------------------------------------------------------------------ train / use
def train(who):
    lib = taste._library()
    ev, _ = taste._load_events(who)
    rows, n_db = _feature_rows(lib, ev)
    out = {"n_labels": n_db, "adopted": False, "auc_learned": None, "auc_default": None,
           "w": [float(v) for v in DEFAULT_W]}
    if len(rows) >= MIN_LABELS:
        X = np.array([r[1] for r in rows])
        y = np.array([r[2] for r in rows])
        cut = int(len(rows) * (1 - HOLDOUT))
        if 0 < y[:cut].mean() < 1 and 0 < y[cut:].mean() < 1:
            v_tr = _deployable(fit_logreg(X[:cut], y[:cut])[:4])   # score exactly as it would be deployed
            a_l = auc(X[cut:] @ v_tr, y[cut:]) if v_tr is not None else float("nan")
            a_d = auc(X[cut:] @ DEFAULT_W, y[cut:])
            out["auc_learned"], out["auc_default"] = _f(a_l), _f(a_d)
            n1 = int(y[cut:].sum())
            v_all = _deployable(fit_logreg(X, y)[:4])
            if v_all is not None and _clears_noise(a_l, a_d, n1, len(y[cut:]) - n1):
                out["w"], out["adopted"] = [float(v) for v in v_all], True
    c = _db()
    c.execute("INSERT OR REPLACE INTO ranker_weights VALUES (?,?,?,?,?,?,?,?,?,?)",
              (who, *out["w"], n_db, out["auc_learned"], out["auc_default"],
               int(out["adopted"]), time.time()))
    c.commit()
    c.close()
    return out


def _row(who):
    c = _db()
    r = c.execute("SELECT w_sim, w_artist, w_genre, w_language, n_labels, auc_learned, auc_default, adopted "
                  "FROM ranker_weights WHERE owner=?", (who,)).fetchone()
    c.close()
    return r


def get_weights(who):
    r = _row(who)
    return np.array(r[:4]) if r and r[7] else None


def status(who):
    r = _row(who)
    if not r:
        return {"adopted": False, "n_labels": 0, "auc_learned": None, "auc_default": None, "weights": None}
    return {"adopted": bool(r[7]), "n_labels": r[4], "auc_learned": _f(r[5]), "auc_default": _f(r[6]),
            "weights": dict(zip(FEATURES, r[:4])) if r[7] else None}


def _count_labels(who):
    c = sql.connect(DB_PATH, timeout=30)
    try:
        n = c.execute("SELECT COUNT(*) FROM listen_events WHERE client_id=? AND event IN ('complete','skip')",
                      (who,)).fetchone()[0]
    except sql.OperationalError:
        n = 0
    c.close()
    return n


def maybe_train_async(who):
    """Cheap check on every home load; the actual training runs in a background thread."""
    n = _count_labels(who)
    r = _row(who)
    last = r[4] if r else 0
    if n < MIN_LABELS or n < last + max(40, int(0.5 * last)):
        return
    with _lock:
        if who in _running:
            return
        _running.add(who)

    def work():
        try:
            train(who)
        except Exception as e:
            print(f"ranker training failed: {e}")
        finally:
            with _lock:
                _running.discard(who)

    threading.Thread(target=work, daemon=True).start()
