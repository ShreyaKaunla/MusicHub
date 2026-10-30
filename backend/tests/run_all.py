"""Runs every test file in its own process (each needs its own config/env). Usage: python tests/run_all.py"""
import glob, os, subprocess, sys

here = os.path.dirname(os.path.abspath(__file__))
failed = []
for f in sorted(glob.glob(os.path.join(here, "test_*.py"))):
    print(f"\n=== {os.path.basename(f)} ===", flush=True)
    if subprocess.call([sys.executable, f]) != 0:
        failed.append(os.path.basename(f))
print("\n" + ("FAILED: " + ", ".join(failed) if failed else "ALL TEST FILES PASSED"))
sys.exit(1 if failed else 0)
