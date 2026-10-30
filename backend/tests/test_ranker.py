"""Learned ranker: recovers a hidden preference, and refuses to learn from noise.

SYNTHETIC check of the method (not a claim about real listeners): the simulated listener cares much
more about familiar artists than the hand-picked default weights assume.
"""
import math, os, sqlite3, sys, tempfile, time
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="musichub_test_")
os.environ["SINGLE_USER"] = "0"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, ".."), HERE]

import numpy as np
from config import DB_PATH
import _synth, events, taste, ranker

_synth.make_library(DB_PATH)
events.ensure_events_schema()
lib = taste._library()
IDS, IDX = lib["ids"], lib["idx"]


def features(ev, t, ts):
    sig = taste._signals_from(ev, set(), ts)
    prof = taste._profile(lib, sig["net"]) if sig["n_pos"] >= 3 else None
    if prof is None:
        return None
    i = IDX[t]
    return [float(lib["mat"][i] @ prof["taste"])] + [prof["aff"][f].get(lib[f][i], 0.0) for f in ("artist", "genre", "language")]


def simulate(client, steps, prob, seed):
    """prob(track_id, features) -> P(listener finishes the song). features is None before a profile exists."""
    rng = np.random.default_rng(seed)
    t0, ev = time.time() - 86400 * 20, []
    c = sqlite3.connect(DB_PATH)
    for s in range(steps):
        t, ts = int(rng.choice(IDS)), t0 + s * 60
        x = features(ev, t, ts)
        p = 0.6 if x is None else prob(t, x)
        done = rng.random() < p
        ev.append((t, "complete" if done else "skip", 200 if done else 5, ts))
        c.execute("INSERT INTO listen_events (client_id, track_id, event, seconds, ts) VALUES (?,?,?,?,?)",
                  (client, t, ev[-1][1], ev[-1][2], ts))
    c.commit(); c.close()


def test_math():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2000, 3)); true = np.array([2.0, -1.0, 0.0])
    y = (rng.random(2000) < 1 / (1 + np.exp(-(X @ true)))).astype(float)
    w = ranker.fit_logreg(X, y, l2=0.1)
    assert np.allclose(w[:3], true, atol=0.25), w
    assert ranker.auc(np.array([1, 2, 3, 4]), np.array([0, 0, 1, 1])) == 1.0
    assert ranker.auc(np.array([1, 1, 1, 1]), np.array([0, 1, 0, 1])) == 0.5   # ties
    print("ok  logistic regression recovers known coefficients; AUC handles ties")


def test_learns_hidden_preference():
    # Loves 2 artists in EVERY genre, regardless of how they sound: sound similarity is a weak guide.
    favs = {f"Artist{g}_{k}" for g in range(4) for k in (0, 1)}
    simulate("sim_user", 700, lambda t, x: 0.9 if lib["artist"][IDX[t]] in favs else 0.25, seed=1)
    res = ranker.train("sim_user")
    print(f"    held-out AUC: learned {res['auc_learned']:.3f} vs default weights {res['auc_default']:.3f}; "
          f"weights sim/artist/genre/lang = {[round(v, 2) for v in res['w']]}")
    assert res["adopted"], res
    assert res["auc_learned"] > res["auc_default"] + 0.05
    assert res["w"][1] > res["w"][0], "should learn that artist matters more than sound for this listener"
    assert abs(sum(res["w"]) - ranker.DEFAULT_W.sum()) < 1e-6, "weights keep the default scale"
    assert res["w"][0] >= ranker.SIM_FLOOR * ranker.DEFAULT_W.sum() - 1e-9, "sound similarity keeps a floor"
    assert ranker.status("sim_user")["adopted"] and ranker.get_weights("sim_user") is not None
    print("ok  learns an artist-driven listener and beats the defaults on held-out events")


def test_keeps_defaults_when_they_are_fine():
    # Listener whose taste really is 'songs that sound like what I finished': the defaults already fit.
    simulate("sound_user", 700, lambda t, x: 1 / (1 + math.exp(-(6 * x[0] - 1.5))), seed=3)
    res = ranker.train("sound_user")
    print(f"    held-out AUC: learned {res['auc_learned']:.3f} vs default {res['auc_default']:.3f}, adopted={res['adopted']}")
    assert not res["adopted"], "no meaningful gain over the defaults, so it should not switch"
    print("ok  keeps the default weights when learning gives no real gain")


def test_refuses_noise():
    adopted = 0
    for k in range(6):
        simulate(f"noise{k}", 320, lambda t, x: 0.5, seed=100 + k)
        adopted += ranker.train(f"noise{k}")["adopted"]
    print(f"    adopted on pure noise: {adopted}/6 listeners")
    assert adopted <= 1, "guard rail too loose: it learns from noise"
    assert ranker.get_weights("noise0") is None or ranker.status("noise0")["adopted"]
    print("ok  does not adopt weights for listeners with no real signal")


def test_too_little_data():
    simulate("tiny", 60, lambda t, x: 0.5, seed=7)
    res = ranker.train("tiny")
    assert not res["adopted"] and res["auc_learned"] is None
    assert ranker.get_weights("tiny") is None
    print("ok  under 100 labelled events: keeps the defaults")


if __name__ == "__main__":
    test_math(); test_learns_hidden_preference(); test_keeps_defaults_when_they_are_fine()
    test_refuses_noise(); test_too_little_data()
    print("ALL RANKER TESTS PASSED")
