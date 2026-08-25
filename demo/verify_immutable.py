#!/usr/bin/env python3
"""Assert demo/live_run is byte-identical to what git has committed.

Run it after using the demo UI, after a replay, or before recording. It reads
git's own object store, so it is independent of anything this repo's own code
believes about itself.

    python3 demo/verify_immutable.py
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = "demo/live_run"


def main():
    d = subprocess.run(["git", "status", "--porcelain", "--", TARGET],
                       cwd=ROOT, capture_output=True, text=True)
    if d.returncode:
        sys.exit(f"git failed: {d.stderr.strip()}")
    dirty = [l for l in d.stdout.splitlines() if l.strip()]
    n = subprocess.run(["git", "ls-files", "--", TARGET],
                       cwd=ROOT, capture_output=True, text=True).stdout.split()
    if dirty:
        print(f"  FAIL — {len(dirty)} change(s) under {TARGET}:")
        for l in dirty:
            print("   ", l)
        return 1
    print(f"  OK — all {len(n)} committed files under {TARGET} are unmodified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
