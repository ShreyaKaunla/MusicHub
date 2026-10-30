"""Public-demo behaviour: visitors are isolated; mood playlists are read-only; legacy DBs migrate."""
import os, sqlite3, sys, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="musichub_test_")
os.environ["SINGLE_USER"] = "0"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, ".."), HERE]

from fastapi import HTTPException
from config import DB_PATH
import _synth, identity, userdata

A, B = "visitor-aaaa1111", "visitor-bbbb2222"


def status_of(fn, *a, **k):
    try:
        fn(*a, **k)
        return 200
    except HTTPException as e:
        return e.status_code


def build_legacy_db():
    """The pre-multi-user desktop schema, with a user playlist, a mood playlist and likes."""
    _synth.make_library(DB_PATH)
    c = sqlite3.connect(DB_PATH)
    c.execute("CREATE TABLE user_playlists (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, is_mood INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE playlist_tracks (playlist_id INTEGER, track_id INTEGER, auto INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE mood_removed (playlist_id INTEGER, track_id INTEGER, PRIMARY KEY (playlist_id, track_id))")
    c.execute("CREATE TABLE liked_tracks (track_id INTEGER PRIMARY KEY)")
    c.execute("INSERT INTO user_playlists (name, is_mood) VALUES ('Gym', 0)")
    c.execute("INSERT INTO user_playlists (name, is_mood) VALUES ('Happy', 1)")
    c.executemany("INSERT INTO playlist_tracks (playlist_id, track_id) VALUES (?,?)", [(1, 1), (1, 2), (1, 3), (2, 4), (2, 5)])
    c.executemany("INSERT INTO liked_tracks VALUES (?)", [(7,), (8,)])
    c.commit(); c.close()


def test_migration():
    build_legacy_db()
    identity.ensure_owner_schema()
    identity.ensure_owner_schema()  # idempotent
    c = sqlite3.connect(DB_PATH)
    owners = dict(c.execute("SELECT name, owner FROM user_playlists"))
    assert owners == {"Gym": "local", "Happy": ""}, owners
    assert sorted(r[0] for r in c.execute("SELECT track_id FROM likes WHERE owner='local'")) == [7, 8]
    assert c.execute("SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id=1").fetchone()[0] == 3  # ids preserved
    assert c.execute("SELECT 1 FROM sqlite_master WHERE name='liked_tracks_migrated'").fetchone()
    c.close()
    print("ok  legacy DB migrates (playlists -> 'local', moods -> shared, likes copied, ids kept)")


def test_isolation():
    # visitors never see the desktop user's 'Gym' playlist
    assert [p["name"] for p in userdata.list_playlists(x_client_id=A)] == ["Happy"]
    pid = userdata.create_manual_playlist(userdata.CreateManualPlaylistRequest(playlist_name="Road trip", track_ids=[1, 2, 3, 999]), x_client_id=A)["id"]
    assert [p["name"] for p in userdata.list_playlists(x_client_id=A)] == ["Happy", "Road trip"]
    assert [p["name"] for p in userdata.list_playlists(x_client_id=B)] == ["Happy"]
    assert len(userdata.get_playlist_tracks(pid, x_client_id=A)) == 3  # unknown track id 999 was dropped
    # same name is fine for another visitor
    assert status_of(userdata.create_manual_playlist, userdata.CreateManualPlaylistRequest(playlist_name="Road trip", track_ids=[1]), x_client_id=B) == 200
    # B cannot see or touch A's playlist
    assert status_of(userdata.get_playlist_tracks, pid, x_client_id=B) == 404
    assert status_of(userdata.add_tracks, pid, userdata.IdsReq(track_ids=[5]), x_client_id=B) == 404
    assert status_of(userdata.remove_track, pid, 1, x_client_id=B) == 404
    assert status_of(userdata.delete_playlist, pid, x_client_id=B) == 404
    # duplicate name for the same visitor
    assert status_of(userdata.create_manual_playlist, userdata.CreateManualPlaylistRequest(playlist_name="Road trip", track_ids=[1]), x_client_id=A) == 400
    # A can edit and delete their own
    assert status_of(userdata.add_tracks, pid, userdata.IdsReq(track_ids=[5]), x_client_id=A) == 200
    assert len(userdata.get_playlist_tracks(pid, x_client_id=A)) == 4
    assert status_of(userdata.delete_playlist, pid, x_client_id=A) == 200
    print("ok  visitors are isolated (list / read / add / remove / delete / duplicate names)")


def test_moods_read_only():
    mood = next(p["id"] for p in userdata.list_playlists(x_client_id=A) if p["is_mood"])
    assert len(userdata.get_playlist_tracks(mood, x_client_id=A)) == 2         # readable
    assert status_of(userdata.add_tracks, mood, userdata.IdsReq(track_ids=[9]), x_client_id=A) == 403
    assert status_of(userdata.remove_track, mood, 4, x_client_id=A) == 403
    assert status_of(userdata.delete_playlist, mood, x_client_id=A) == 403
    print("ok  mood playlists are read-only for visitors")


def test_likes_and_ids():
    assert userdata.toggle_like(1, x_client_id=A) == {"liked": True}
    assert userdata.get_likes(x_client_id=A) == [1] and userdata.get_likes(x_client_id=B) == []
    assert userdata.toggle_like(1, x_client_id=A) == {"liked": False}
    for bad in (None, "", "short", "local", "has space in it!!", "x" * 65):
        assert status_of(identity.owner, bad) == 400, bad
    print("ok  likes are per visitor; malformed / reserved client ids are rejected")


def test_playlist_cap():
    have = len([p for p in userdata.list_playlists(x_client_id=B) if not p["is_mood"]])
    for i in range(userdata.MAX_PLAYLISTS - have):
        userdata.create_manual_playlist(userdata.CreateManualPlaylistRequest(playlist_name=f"p{i}", track_ids=[1]), x_client_id=B)
    n_b = len([p for p in userdata.list_playlists(x_client_id=B) if not p["is_mood"]])
    assert n_b == userdata.MAX_PLAYLISTS, n_b
    assert status_of(userdata.create_manual_playlist, userdata.CreateManualPlaylistRequest(playlist_name="one too many", track_ids=[1]), x_client_id=B) == 400
    print("ok  per-visitor playlist cap enforced")


def test_snapshot_handles_windows_paths():
    r = userdata.SaveQueueRequest(playlist_name="Queue", track_paths=["C:\\Users\\me\\Music\\s3.mp3", "s4.mp3", "s3.mp3", "nope.mp3"])
    userdata.snapshot_ai_queue(r, x_client_id=A)
    pid = next(p["id"] for p in userdata.list_playlists(x_client_id=A) if p["name"] == "Queue")
    assert sorted(t["id"] for t in userdata.get_playlist_tracks(pid, x_client_id=A)) == [3, 4]
    userdata.snapshot_ai_queue(r, x_client_id=A)  # saving again must not duplicate songs
    assert len(userdata.get_playlist_tracks(pid, x_client_id=A)) == 2
    print("ok  snapshot matches Windows paths, ignores unknown files, doesn't duplicate")


if __name__ == "__main__":
    test_migration(); test_isolation(); test_moods_read_only(); test_likes_and_ids()
    test_playlist_cap(); test_snapshot_handles_windows_paths()
    print("ALL USERDATA TESTS PASSED")
