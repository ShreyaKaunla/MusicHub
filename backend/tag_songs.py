"""Gives Pixabay-style files (artist-title-ID.mp3) proper Title / Artist / Album / Genre tags.

  python tag_songs.py "C:\\path\\to\\folder"                  preview only: prints a table, writes song_metadata.csv
  python tag_songs.py "C:\\path\\to\\folder" --apply          writes the tags (uses song_metadata.csv if you edited it)
  python tag_songs.py "C:\\path\\to\\folder" --apply --update-db --remove-duplicates

What it can and can't know
  * Artist and title come from the file name (Pixabay names files  artist-title-words-ID).
  * Pixabay tracks have NO album, so the album (and genre) is GUESSED from words in the title
    ("rock", "lofi", "trap", "trailer"...). Tracks with no such word go to the album "Pixabay Mix".
    Use  --album artist  or  --album "Any name"  to choose differently, or edit song_metadata.csv
    (open it in Excel, fix any title/artist/album/genre, then run again with --apply).
  * --remove-duplicates moves files like "name (1).mp3" (same Pixabay ID) into a "_duplicates" folder
    (nothing is deleted). With --update-db their database rows are removed too.
  * --update-db updates songs already in your library database. Restart the server afterwards.
"""
import argparse
import csv
import re
import shutil
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

CSV_NAME = "song_metadata.csv"
FIELDS = ["file", "title", "artist", "album", "genre"]
SMALL = {"a", "an", "the", "of", "in", "on", "to", "and", "for", "at", "by", "with", "or"}
WORDS = {"amp": "&", "drumampbass": "Drum & Bass", "lofi": "Lo-fi", "dnb": "Drum & Bass"}
# (genre, album, trigger words); the first matching row wins, so order matters
CATEGORIES = [
    ("Hip-Hop", "Hip-Hop & Trap", {"hip", "hop", "trap", "drill", "phonk", "rap"}),
    ("Electronic", "Electronic & Beats", {"electronic", "edm", "techno", "house", "dubstep", "drumampbass", "cyberpunk",
                                          "digital", "future", "garage", "synth", "breakbeat"}),
    ("Rock", "Rock & Metal", {"rock", "metal", "fuzz", "indie", "punk", "guitar"}),
    ("Latin", "Latin & World", {"latin", "salsa", "reggaeton", "bossa"}),
    ("Pop", "Pop & Dance", {"pop", "dance", "fashion", "disco"}),
    ("Funk & Blues", "Funk & Blues", {"funk", "blues", "jazz", "soul", "groove"}),
    ("Chill", "Chill & Ambient", {"lofi", "chill", "ambient", "relax", "calm", "peace", "nature", "age", "lounge",
                                  "quiet", "sleep"}),
    ("Folk", "Folk & Acoustic", {"ukulele", "acoustic", "folk", "piano"}),
    ("Cinematic", "Cinematic & Action", {"epic", "cinematic", "trailer", "dramatic", "adventure", "orchestral",
                                          "percussion", "spooky", "halloween", "action", "sport", "motivation",
                                          "powerful", "energetic", "intense", "stomp", "strong"}),
    ("Fun", "Fun & Playful", {"comedy", "cartoon", "funny", "children", "kids"}),
]
NAME_RE = re.compile(r"^(?P<slug>.+)-(?P<id>\d{4,9})(?P<dup>\s*\(\d+\))?$")


def nice_title(tokens):
    out = []
    for i, w in enumerate(tokens):
        if w in WORDS:
            out.append(WORDS[w])
        elif i > 0 and w in SMALL:
            out.append(w)
        else:
            out.append(w.capitalize())
    return " ".join(out)


def parse_name(stem):
    """'kornevmusic-epic-478847' -> dict(artist, title, genre, album, id, dup) or None if not Pixabay-style."""
    m = NAME_RE.match(stem.strip())
    if not m or "-" not in m["slug"]:
        return None
    handle, _, rest = m["slug"].partition("-")
    tokens = [t for t in re.split(r"[-_\s]+", rest.lower()) if t]
    if tokens and tokens[-1] == handle.lower().replace("_", ""):      # "...-peace-mickeyscat" repeats the artist
        tokens = tokens[:-1]
    if "i" in tokens[2:]:                                            # a "|" in the original title became a lone "i"
        tokens = tokens[:tokens.index("i", 2)]
    if not tokens:
        return None
    genre, album = "Unknown", "Pixabay Mix"
    for g, a, trig in CATEGORIES:
        if trig & set(tokens):
            genre, album = g, a
            break
    return {"artist": " ".join(w.capitalize() for w in handle.split("_")), "title": nice_title(tokens),
            "genre": genre, "album": album, "id": m["id"], "dup": bool(m["dup"])}


def build_rows(files, album_mode):
    rows, skipped = [], []
    for f in files:
        p = parse_name(f.stem)
        if not p:
            skipped.append(f.name)
            continue
        album = p["album"] if album_mode == "category" else (p["artist"] if album_mode == "artist" else album_mode)
        rows.append({"file": f.name, "title": p["title"], "artist": p["artist"], "album": album, "genre": p["genre"],
                     "_id": p["id"], "_dup": p["dup"]})
    return rows, skipped


def find_duplicates(rows):
    """Same Pixabay ID twice: keep the file without '(1)', mark the others."""
    by_id = defaultdict(list)
    for r in rows:
        by_id[r["_id"]].append(r)
    dups = set()
    for group in by_id.values():
        if len(group) > 1:
            group.sort(key=lambda r: (r["_dup"], r["file"]))
            dups.update(r["file"] for r in group[1:])
    return dups


def write_tags(path, r):
    try:
        from mutagen.easyid3 import EasyID3
        from mutagen.id3 import ID3NoHeaderError
    except ImportError:
        sys.exit("The 'mutagen' package is missing: run  pip install mutagen  (it is in requirements.txt).")
    try:
        t = EasyID3(str(path))
    except ID3NoHeaderError:
        t = EasyID3()
    t["title"], t["artist"], t["album"], t["genre"] = r["title"], r["artist"], r["album"], r["genre"]
    t.save(str(path), v2_version=3)


def update_db(rows, moved):
    from config import DB_PATH
    c = sqlite3.connect(DB_PATH, timeout=30)
    base = lambda p: Path(str(p).replace("\\", "/")).name.lower()
    ids = {base(p): i for i, p in c.execute("SELECT id, file_path FROM tracks")}
    updated = removed = 0
    for r in rows:
        tid = ids.get(r["file"].lower())
        if tid is None:
            continue
        if r["file"] in moved:
            for sql in ("DELETE FROM tracks WHERE id=?", "DELETE FROM playlist_tracks WHERE track_id=?"):
                c.execute(sql, (tid,))
            try:
                c.execute("DELETE FROM likes WHERE track_id=?", (tid,))
            except sqlite3.OperationalError:
                pass
            removed += 1
        else:
            c.execute("UPDATE tracks SET title=?, artist=?, album=?, genre=? WHERE id=?",
                      (r["title"], r["artist"], r["album"], r["genre"], tid))
            updated += 1
    c.commit()
    c.close()
    return updated, removed


def main(argv=None):
    ap = argparse.ArgumentParser(description="Tag Pixabay-style MP3 files from their file names")
    ap.add_argument("folder")
    ap.add_argument("--apply", action="store_true", help="write the tags (default is preview only)")
    ap.add_argument("--album", default="category", help="category (default), artist, or any fixed album name")
    ap.add_argument("--update-db", action="store_true", help="also update songs already in your library database")
    ap.add_argument("--remove-duplicates", action="store_true", help='move "name (1).mp3" copies to _duplicates/')
    a = ap.parse_args(argv)

    folder = Path(a.folder)
    if not folder.is_dir():
        sys.exit(f"Folder not found: {folder}")
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".mp3")
    if not files:
        sys.exit(f"No .mp3 files in {folder}")
    csv_path = folder / CSV_NAME
    rows, skipped = build_rows(files, a.album)
    dups = find_duplicates(rows)

    if a.apply and csv_path.exists():                               # honour the edits you made in Excel
        edited = {r["file"]: r for r in csv.DictReader(open(csv_path, encoding="utf-8-sig", newline=""))}
        for r in rows:
            e = edited.get(r["file"])
            if e:
                r.update({k: (e.get(k) or r[k]).strip() for k in FIELDS[1:]})
        print(f"Using your {CSV_NAME} (edits included).")
    elif not a.apply:
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(FIELDS)
            for r in rows:
                w.writerow([r[k] for k in FIELDS])

    w = max((len(r["title"]) for r in rows), default=10)
    print(f"\n{'ARTIST':24s} {'TITLE':{w}s}  ALBUM / GENRE")
    for r in rows:
        mark = "  (duplicate)" if r["file"] in dups else ""
        print(f"{r['artist'][:24]:24s} {r['title']:{w}s}  {r['album']} / {r['genre']}{mark}")
    if skipped:
        print("\nNot Pixabay-style, left unchanged:", ", ".join(skipped))

    if not a.apply:
        print(f"\nPreview only: nothing changed. Fix anything wrong in {csv_path.name}, then add --apply.")
        return rows

    moved = set()
    if a.remove_duplicates and dups:
        (folder / "_duplicates").mkdir(exist_ok=True)
        for name in sorted(dups):
            shutil.move(str(folder / name), str(folder / "_duplicates" / name))
            moved.add(name)
        print(f"\nMoved {len(moved)} duplicate file(s) to _duplicates/")
    todo = [r for r in rows if r["file"] not in moved]
    for r in todo:
        write_tags(folder / r["file"], r)
    print(f"Tagged {len(todo)} files.")
    (folder / "CREDITS.md").write_text(
        "# Music credits\n\nTracks from Pixabay (Pixabay Content License).\n\n" +
        "\n".join(f'- "{r["title"]}" by {r["artist"]} via Pixabay' for r in sorted(todo, key=lambda r: r["artist"].lower())) + "\n",
        encoding="utf-8")
    if a.update_db:
        u, d = update_db(rows, moved)
        print(f"Database: updated {u} songs, removed {d} duplicate rows. Restart the server to see the changes.")
    elif not a.update_db:
        print("If these songs are already in your library, run again with --update-db (or tag them before the first scan).")
    return rows


if __name__ == "__main__":
    main()
