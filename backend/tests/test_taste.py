"""Taste profile + shelves on a synthetic library with a known listener."""
import os, sqlite3, sys, tempfile, time
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="musichub_test_")
os.environ["SINGLE_USER"] = "0"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, ".."), HERE]

from collections import Counter
import numpy as np
from config import DB_PATH
import _synth, events, taste


def main():
    genre_of = _synth.make_library(DB_PATH)
    events.ensure_events_schema()
    now = time.time()
    g0 = [t for t in genre_of if genre_of[t] == 0]
    g3 = [t for t in genre_of if genre_of[t] == 3]
    c = sqlite3.connect(DB_PATH)
    ins = "INSERT INTO listen_events (client_id, track_id, event, seconds, ts) VALUES ('u1',?,?,?,?)"
    for t in g0[:10]: c.execute(ins, (t, "complete", 200, now - 3600))
    for t in g3[:5]: c.execute(ins, (t, "skip", 5, now - 1800))
    c.execute(ins, (g0[0], "like", 0, now - 3000))
    c.commit(); c.close()

    h = taste.build_home("u1")
    lib = taste._library()
    assert h["unlocked"] and h["source"] == "embedding"
    mixes = next(s for s in h["sections"] if s["id"] == "made-for-you")["items"]
    for m in mixes:
        assert np.mean([genre_of[t] == 0 for t in m["track_ids"]]) > 0.8, f'{m["title"]} drifted off-taste'
    disc = next(i for s in h["sections"] if s["id"] == "your-picks" for i in s["items"] if i["id"] == "discover")["track_ids"]
    assert not set(disc) & set(g0[:10]), "Discover must exclude already-played songs"
    assert not any(genre_of[t] == 3 for t in disc), "skipped genre must not appear in Discover"
    for s in h["sections"]:
        for it in (s.get("items") or [s]):
            top = Counter(lib["artist"][lib["idx"][t]] for t in it["track_ids"]).most_common(1)[0][1]
            assert top <= 3 or it["id"] == "top-artist" or s["id"] == "top-artist" or it.get("id") == "top-artist", it["title"]
    cold = taste.build_home("brand-new-visitor")
    assert not cold["unlocked"] and cold["needed"] == 5 and cold["sections"][0]["id"] == "explore"
    print("ok  taste: mixes on-taste, Discover excludes played/skipped, artist cap holds, cold start works")
    print("ALL TASTE TESTS PASSED")


if __name__ == "__main__":
    main()
