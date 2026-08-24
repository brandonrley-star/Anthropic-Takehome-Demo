"""
Guard against a narrative being attached to the wrong work order.

Checks that any asset tag appearing in the brief (inverter serial, combiner,
tracker row/zone, transformer, met station) also appears in the narrative OR
that the narrative names no conflicting tag of the same kind. A narrative that
names a DIFFERENT asset than its brief is almost certainly misaligned.
"""
import os as _os, sys as _sys
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.join(_ROOT, "generator"))

import re, sys
import narrate

TAG = re.compile(r"\b(?:[A-Z]{3}\d{2}-\d{4}[A-D]-\d{4}|CB-B\d{2}-\d{2}|TR-B\d{2}-R\d{3}|TR-Z\d{2}|XFMR-B\d{2}|MET-\d{2}|CX-R\d{2})\b")


def main():
    sites, assets, techs, wos = narrate.load_all()
    nar = narrate.load_narratives()
    bad = []
    for w in wos:
        t = nar.get(w["wo_id"])
        if not t:
            continue
        btags, ntags = set(TAG.findall(w["brief"])), set(TAG.findall(t))
        if btags and ntags and not (btags & ntags):
            bad.append((w["wo_id"], sorted(btags), sorted(ntags)))
    print(f"checked {len(nar)} narratives, {len(bad)} asset-tag conflicts")
    for wid, b, n in bad[:20]:
        print(f"  {wid}: brief={b} narrative={n}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
