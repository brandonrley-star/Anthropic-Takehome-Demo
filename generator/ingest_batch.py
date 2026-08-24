"""Ingest authored narratives for one batch: TAB-separated wo_id<TAB>narrative."""
import os as _os, sys as _sys
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.join(_ROOT, "generator"))

import sys, os
import narrate

b = int(sys.argv[1]); src = sys.argv[2]
sites, assets, techs, wos = narrate.load_all()
expected = {w["wo_id"] for w in wos if w["_batch"] == b}

mapping, dupes, bad = {}, [], []
with open(src) as f:
    for line in f:
        line = line.rstrip("\n")
        if not line.strip():
            continue
        if "\t" not in line:
            bad.append(line[:60]); continue
        wid, text = line.split("\t", 1)
        wid = wid.strip(); text = text.strip()
        if wid in mapping:
            dupes.append(wid)
        mapping[wid] = text

missing = expected - set(mapping)
extra = set(mapping) - expected
if bad:     print(f"MALFORMED {len(bad)}: {bad[:3]}")
if dupes:   print(f"DUPLICATE {len(dupes)}: {dupes[:5]}")
if extra:   print(f"NOT IN BATCH {len(extra)}: {sorted(extra)[:5]}")
if missing: print(f"MISSING {len(missing)}: {sorted(missing)[:8]}")
if bad or extra or missing:
    print("REJECTED - batch not saved"); sys.exit(1)

h = narrate.save_batch(b, mapping)
wl = [len(t.split()) for t in mapping.values()]
print(f"batch {b} saved: {len(mapping)} narratives, sha {h[:16]}, "
      f"words min={min(wl)} med={sorted(wl)[len(wl)//2]} max={max(wl)}")
