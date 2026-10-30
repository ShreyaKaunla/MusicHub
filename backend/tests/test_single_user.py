"""Desktop behaviour (SINGLE_USER=1): one owner, mood playlists editable, old events re-labelled."""
import os, sqlite3, sys, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="musichub_test_")
os.environ["SINGLE_USER"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, ".."), HERE]

from config import DB_PATH
import _synth, events, identity, userdata


def main():
    _synth.make_library(DB_PATH)
    c = sqlite3.connect(DB_PATH)
    c.execute("CREATE TABLE user_playlists (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, is_mood INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE playlist_tracks (playlist_id INTEGER, track_id INTEGER, auto INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE mood_removed (playlist_id INTEGER, track_id INTEGER, PRIMARY KEY (playlist_id, track_id))")
    c.execute("INSERT INTO user_playlists (name, is_mood) VALUES ('Happy', 1)")
    c.commit(); c.close()
    events.ensure_events_schema()
    c = sqlite3.connect(DB_PATH)
    c.execute("INSERT INTO listen_events (client_id, track_id, event, seconds, ts) VALUES ('old-browser-id', 1, 'complete', 200, 1)")
    c.commit(); c.close()

    identity.ensure_owner_schema()
    assert identity.owner(None) == identity.owner("anything") == "local"
    c = sqlite3.connect(DB_PATH)
    assert c.execute("SELECT client_id FROM listen_events").fetchone()[0] == "local"
    c.close()
    mood = userdata.list_playlists()[0]["id"]
    userdata.add_tracks(mood, userdata.IdsReq(track_ids=[3]))      # desktop users may correct mood playlists
    userdata.remove_track(mood, 3)
    c = sqlite3.connect(DB_PATH)
    assert c.execute("SELECT 1 FROM mood_removed WHERE playlist_id=? AND track_id=3", (mood,)).fetchone()
    c.close()
    print("ok  single-user: one owner, mood playlists editable (removals remembered), old events re-labelled")
    print("ALL SINGLE-USER TESTS PASSED")


if __name__ == "__main__":
    main()
