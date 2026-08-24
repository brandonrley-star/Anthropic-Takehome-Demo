"""Print a seeded random sample of narratives with their structured fields."""
import os as _os, sys as _sys
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_sys.path.insert(0, _os.path.join(_ROOT, "generator"))
_sys.path.insert(0, _os.path.join(_ROOT, "eval", "audit"))

import sys, json, random
n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
seed = int(sys.argv[2]) if len(sys.argv) > 2 else 424242
with open(_os.path.join(_ROOT, "corpus", "work_orders.json")) as f:
    wos = json.load(f)
rng = random.Random(seed)
for i, w in enumerate(rng.sample(wos, n), 1):
    lost = w["estimated_lost_production_mwh"]
    print(f"[{i:2d}] {w['wo_id']}  {w['site_name']}  ({w['date_opened']}"
          f"{' → ' + w['date_closed'] if w['date_closed'] else ' → OPEN'})")
    print(f"     {w['wo_type']}/{w['priority']}  {w['technician_id']}  "
          f"asset={w['asset_id'] or '—'}  {w['labor_hours']}h  "
          f"res={w['resolution_code']}  parts={w['parts_used'] or '—'}  "
          f"lost={lost if lost is not None else '—'}")
    print(f"     \"{w['narrative']}\"")
    print()
