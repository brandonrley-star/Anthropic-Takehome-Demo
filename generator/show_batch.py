import os as _os, sys as _sys
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.join(_ROOT, "generator"))

import sys, json
import narrate
sites, assets, techs, wos = narrate.load_all()
b = int(sys.argv[1])
rows = narrate.dump_batch(wos, techs, b)
nb, done = narrate.status(wos)
sys.stderr.write(f"batch {b} of {nb} ({len(rows)} WOs); completed: {len(done)}\n")
for r in rows:
    print(json.dumps(r, ensure_ascii=False))
