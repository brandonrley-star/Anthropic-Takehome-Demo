#!/usr/bin/env python3
"""
Compare two pipeline runs — typically the authored reference run against a
live-model run — on the things that actually matter commercially:

  * extraction quality (what Stage 1 could and could not classify)
  * which candidates Stage 2 generated and how it ranked them
  * which findings escalated, deprioritised or declined, and where the two
    runs disagree about the same candidate

Reads only run output directories. Does not touch corpus/ or eval/.

Usage:  python3 demo/compare_runs.py demo/reference_run demo/live_run
"""
import json, os, sys

BAR = "=" * 78


def load(d):
    def j(n):
        p = os.path.join(d, n)
        return json.load(open(p)) if os.path.exists(p) else None
    return {"manifest": j("run_manifest.json"),
            "candidates": j("candidates.json"),
            "findings": j("findings.json"),
            "name": os.path.basename(d.rstrip("/"))}


def ident(c):
    """Content identity for a candidate.

    candidate_id is assigned by materiality rank, so CAND-002 in one run is NOT
    the same cluster as CAND-002 in another. Comparing by id would silently
    align unrelated findings. Match on what the cluster IS instead.
    """
    return (c.get("kind", "?"), str(c.get("key", "")))


def verdicts(run):
    out = {}
    raw = run["findings"] or {}
    items = raw.values() if isinstance(raw, dict) else raw
    for f in items:
        c = f.get("candidate") or {}
        v = f.get("verdict") or {}
        out[ident(c)] = {"verdict": v.get("verdict"), "confidence": v.get("confidence"),
                         "headline": v.get("business_headline", ""),
                         "label": c.get("label", ""), "n": c.get("n", 0),
                         "cid": c.get("candidate_id", "?"),
                         "members": set(c.get("members") or [])}
    return out


def cand_index(run):
    return {ident(c): c for c in (run["candidates"] or [])}


def main(a_dir, b_dir):
    A, B = load(a_dir), load(b_dir)
    print(BAR); print(f"RUN COMPARISON — {A['name']}  vs  {B['name']}"); print(BAR)

    for tag, R in (("A", A), ("B", B)):
        m = R["manifest"] or {}
        q = m.get("extraction_quality", {})
        print(f"  [{tag}] {R['name']:<18} stage1={m.get('stage1_backend'):<10} "
              f"reasoning={m.get('reasoning_backend'):<10} model={m.get('model')}")
        print(f"       candidates {m.get('candidates_total')} generated / "
              f"{m.get('candidates_examined')} examined   "
              f"unclassified symptom {q.get('symptom_unclassified')} "
              f"({q.get('symptom_unclassified_pct')}%)")
        mix = q.get("outcome_mix", {})
        print(f"       outcome mix {mix}")
    print()

    print(BAR); print("STAGE 2 — CANDIDATE GENERATION"); print(BAR)
    ca, cb = cand_index(A), cand_index(B)
    ka, kb = set(ca), set(cb)
    print(f"  {A['name']}: {len(ka)} candidates    {B['name']}: {len(kb)} candidates")

    def bykind(c):
        d = {}
        for x in c.values():
            d[x.get("kind", "?")] = d.get(x.get("kind", "?"), 0) + 1
        return dict(sorted(d.items()))
    print(f"  by kind  A={bykind(ca)}")
    print(f"           B={bykind(cb)}")

    print("\n  TOP 15 BY MATERIALITY")
    ta = sorted(ca.values(), key=lambda c: -c.get("_materiality", 0))[:15]
    tb = sorted(cb.values(), key=lambda c: -c.get("_materiality", 0))[:15]
    print(f"  {'#':>2}  {A['name'][:32]:<34}{B['name'][:32]}")
    for i in range(15):
        la = f"{ta[i].get('kind','')[:14]} {str(ta[i].get('label',''))[:19]}" if i < len(ta) else ""
        lb = f"{tb[i].get('kind','')[:14]} {str(tb[i].get('label',''))[:19]}" if i < len(tb) else ""
        mark = "  " if la == lb else "* "
        print(f"  {i+1:>2}{mark}{la:<36}{lb}")

    print()
    print(BAR); print("STAGE 4 — VERDICT DIVERGENCE"); print(BAR)
    va, vb = verdicts(A), verdicts(B)
    both = sorted(set(va) & set(vb))
    print(f"  examined in both: {len(both)}   only in A: {len(set(va)-set(vb))}   "
          f"only in B: {len(set(vb)-set(va))}")
    if both:
        print(f"\n  {'A id':<10}{'B id':<10}{'A verdict':<15}{'B verdict':<15}{'agree':<7}cluster")
        for k in both:
            same = "yes" if va[k]["verdict"] == vb[k]["verdict"] else "NO"
            na, nb = va[k]["n"], vb[k]["n"]
            size = f"n {na}" if na == nb else f"n {na}->{nb}"
            print(f"  {va[k]['cid']:<10}{vb[k]['cid']:<10}{va[k]['verdict'] or '-':<15}"
                  f"{vb[k]['verdict'] or '-':<15}{same:<7}{size}  {va[k]['label'][:30]}")

    for tag, mine, other in (("A only", va, vb), ("B only", vb, va)):
        only = sorted(set(mine) - set(other))
        if only:
            print(f"\n  EXAMINED {tag.upper()} ({len(only)}):")
            for k in only:
                print(f"    {mine[k]['cid']:<10}{mine[k]['verdict']:<13} n={mine[k]['n']:<4} "
                      f"{k[0]:<20} {mine[k]['label'][:40]}")

    for tag, R, V in (("A", A, va), ("B", B, vb)):
        esc = [k for k, v in V.items() if v["verdict"] == "escalate"]
        print(f"\n  [{tag}] {R['name']} escalated {len(esc)}:")
        for k in esc:
            print(f"    {V[k]['cid']} [{k[0]}] {V[k]['headline'][:96]}")

    print()
    print(BAR); print("EFFICACY-DECAY AND SERIAL-COHORT CANDIDATES (the hard kinds)"); print(BAR)
    for tag, R, C, V in (("A", A, ca, va), ("B", B, cb, vb)):
        hard = [c for k, c in C.items() if k[0] in ("efficacy_decay", "serial_cohort")]
        hard.sort(key=lambda c: -c.get("_materiality", 0))
        print(f"\n  [{tag}] {R['name']}: {len(hard)} generated")
        rank = {ident(c): i for i, c in enumerate(
            sorted(C.values(), key=lambda c: -c.get("_materiality", 0)), 1)}
        for c in hard:
            k = ident(c)
            seen = V.get(k, {}).get("verdict", "not examined")
            print(f"    rank {rank[k]:>3}/{len(C)}  {c.get('kind'):<16} n={c.get('n'):<4} "
                  f"lift={c.get('lift', 0):<6.2f} mat={c.get('_materiality', 0):<8} "
                  f"{str(c.get('label'))[:38]}  -> {seen}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
