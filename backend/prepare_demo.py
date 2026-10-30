"""OPTIONAL: shrink downloaded Creative Commons tracks for hosting.

Keeps a 90 s excerpt (from 30 s in, so you skip intros) at 96 kbps mono: about 1 MB per song, which
keeps the repo, the Docker image and the bandwidth small. Cover art is kept.
Only do this for licences that allow modification (CC0, CC BY, CC BY-SA); skip it for "NoDerivs".

Usage:  python prepare_demo.py demo_music_src [demo_music]      (needs ffmpeg on your PATH)
"""
import shutil
import subprocess
import sys
from pathlib import Path


def encode(src, dst, start):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-t", "90", "-i", str(src),
           "-map", "0:a:0", "-map", "0:v?", "-c:v", "copy", "-ac", "1", "-b:a", "96k",
           "-id3v2_version", "3", "-map_metadata", "0", str(dst)]
    return subprocess.run(cmd, capture_output=True, text=True)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found. Install it first (Windows: winget install Gyan.FFmpeg).")
    src, dst = Path(sys.argv[1]), Path(sys.argv[2] if len(sys.argv) > 2 else "demo_music")
    dst.mkdir(parents=True, exist_ok=True)
    files = sorted(src.glob("*.mp3"))
    if not files:
        sys.exit(f"No .mp3 files in {src}")
    total = 0
    for f in files:
        out = dst / f.name
        r = encode(f, out, 30)
        if r.returncode != 0 or not out.exists() or out.stat().st_size < 50_000:  # short song: start at 0
            r = encode(f, out, 0)
        if r.returncode != 0 or not out.exists():
            print(f"  skipped {f.name}: {r.stderr.strip()[:120]}")
            continue
        total += out.stat().st_size
        print(f"  {f.name}: {out.stat().st_size / 1e6:.1f} MB")
    print(f"\nDone: {len(files)} songs -> {dst} ({total / 1e6:.0f} MB). Next: python build_demo.py")


if __name__ == "__main__":
    main()
