#!/usr/bin/env python3
"""
Safe replay of the committed live run.

demo/live_run/ is IMMUTABLE. It holds the model outputs the whole project is
evidenced on, and it was damaged once already: a replay invoked with
`--out demo/live_run` overwrote run_manifest.json, replacing the real run time
with the replay's own 0.4s. The correct value was not recoverable from git,
only from archived stdout.

This wrapper is the supported way to replay. It:
  * always writes to a scratch directory, never to demo/live_run
  * seeds the pipeline cache from the committed responses so nothing is charged
  * verifies afterwards that demo/live_run is byte-identical

    python3 demo/replay.py                 # replay into a temp directory
    python3 demo/replay.py --out /tmp/x    # choose the scratch directory

Nothing here changes any analysis. It runs the committed responses back through
the same rendering path and checks that the source of truth is untouched.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_RUN = os.path.join(ROOT, "demo", "live_run")
CACHE = os.path.join(ROOT, ".pipeline_cache")


def fingerprint(d):
    """SHA-256 of every file under a directory, keyed by relative path."""
    out = {}
    for base, _dirs, files in os.walk(d):
        for f in sorted(files):
            p = os.path.join(base, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, d)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None,
                    help="scratch output directory (default: a temp directory)")
    a = ap.parse_args()

    out = a.out or tempfile.mkdtemp(prefix="live_run_replay_")
    if os.path.abspath(out).rstrip("/") == LIVE_RUN.rstrip("/"):
        sys.exit("refusing to write to demo/live_run — it is immutable")

    before = fingerprint(LIVE_RUN)

    os.makedirs(CACHE, exist_ok=True)
    src = os.path.join(LIVE_RUN, "cache")
    for f in os.listdir(src):
        if f.endswith(".jsonl"):
            shutil.copy2(os.path.join(src, f), os.path.join(CACHE, f))
    print(f"  cache seeded from committed responses ({len(before)} files under live_run)")

    cmd = [sys.executable, "-m", "pipeline.run",
           "--stage1-backend", "anthropic", "--backend", "anthropic",
           "--out", out]
    print("  " + " ".join(cmd) + "\n")
    r = subprocess.run(cmd, cwd=ROOT)

    after = fingerprint(LIVE_RUN)
    if before != after:
        changed = sorted(set(before) ^ set(after)) + \
                  sorted(k for k in before if k in after and before[k] != after[k])
        sys.exit(f"\n  FAIL — demo/live_run was modified: {changed}")
    print(f"\n  demo/live_run unchanged — {len(after)} files verified byte-identical")
    print(f"  replay written to {out}")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
