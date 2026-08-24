#!/usr/bin/env python3
"""
DEMO 1 — Why raw counts are the wrong denominator.

The single most common way a fleet reliability conversation goes wrong is
ranking sites by ticket count. Ticket count is a function of how big a site is
and how long it has been under contract, and only then a function of how well
it is running. This script shows both rankings side by side on the same corpus.

It normalises by GW-months of contracted exposure using
pipeline.corpus_io.site_exposure_gw_months — deliberately the SAME function the
detection pipeline uses, so the demo and the detector cannot disagree.

Run:  python3 demo/01_naive_ranking.py
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import corpus_io                                    # noqa: E402


def main():
    wos, sites, _assets, _techs = corpus_io.load()

    raw = {name: 0 for name in sites}
    for w in wos:
        raw[w["site_name"]] = raw.get(w["site_name"], 0) + 1

    rows = []
    for name, site in sites.items():
        gwm = corpus_io.site_exposure_gw_months(site)
        rows.append({
            "site": name,
            "n": raw.get(name, 0),
            "mw": site["capacity_mwdc"],
            "months": corpus_io.coverage_months(site),
            "gw_months": gwm,
            "rate": (raw.get(name, 0) / gwm) if gwm else 0.0,
        })

    by_raw = sorted(rows, key=lambda r: -r["n"])
    by_rate = sorted(rows, key=lambda r: -r["rate"])
    rank_raw = {r["site"]: i for i, r in enumerate(by_raw, 1)}
    rank_rate = {r["site"]: i for i, r in enumerate(by_rate, 1)}

    bar = "=" * 78
    print(bar)
    print("SITE RANKING — RAW TICKET COUNT vs EXPOSURE-NORMALISED RATE")
    print(bar)
    print(f"{len(rows)} sites, {len(wos)} work orders, "
          f"{corpus_io.WINDOW_START} to {corpus_io.WINDOW_END}\n")

    print("  RAW COUNT (what a spreadsheet gives you)")
    print(f"  {'#':>2}  {'site':<26}{'tickets':>8}{'MWdc':>8}{'months':>8}")
    for i, r in enumerate(by_raw[:10], 1):
        print(f"  {i:>2}  {r['site']:<26}{r['n']:>8}{r['mw']:>8.0f}{r['months']:>8}")

    print("\n  EXPOSURE-NORMALISED (tickets per GW-month under contract)")
    print(f"  {'#':>2}  {'site':<26}{'rate':>8}{'tickets':>8}{'GW-mo':>8}"
          f"{'raw rank':>10}")
    for i, r in enumerate(by_rate[:10], 1):
        print(f"  {i:>2}  {r['site']:<26}{r['rate']:>8.1f}{r['n']:>8}"
              f"{r['gw_months']:>8.2f}{rank_raw[r['site']]:>10}")

    moved = sorted(rows, key=lambda r: -abs(rank_raw[r["site"]] - rank_rate[r["site"]]))
    print("\n  LARGEST RANK MOVES (raw -> normalised)")
    print(f"  {'site':<26}{'raw':>6}{'norm':>6}{'move':>8}   reading")
    for r in moved[:6]:
        a, b = rank_raw[r["site"]], rank_rate[r["site"]]
        note = ("understated by raw count" if b < a else
                "overstated by raw count" if b > a else "unchanged")
        print(f"  {r['site']:<26}{a:>6}{b:>6}{a - b:>+8}   {note}")

    top_raw, top_rate = by_raw[0], by_rate[0]
    print("\n" + "-" * 78)
    print(f"  Raw ranking puts {top_raw['site']} first with {top_raw['n']} tickets "
          f"across\n  {top_raw['mw']:.0f} MWdc and {top_raw['months']} contracted months.")
    print(f"  Normalised ranking puts {top_rate['site']} first at "
          f"{top_rate['rate']:.1f} tickets/GW-month\n  on {top_rate['mw']:.0f} MWdc — "
          f"rank {rank_raw[top_rate['site']]} of {len(rows)} by raw count.")
    print("\n  Every count in the detection pipeline is normalised on this basis.")
    print("-" * 78)


if __name__ == "__main__":
    main()
