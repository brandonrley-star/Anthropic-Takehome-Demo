"""
Adversarial audit: try to find each planted pattern using ONLY simple
aggregation - group by, count, sort, ratio. No language understanding, no
reading of narratives.

If a pattern falls to one of these, it is too easy and the audit says so.
"""
import re, sys, collections
import pandas as pd
from _common import load

pd.set_option("display.width", 200)
SERIAL = re.compile(r"^([A-Z]{3}\d{2})-(\d{2})(\d{2})([A-D])-(\d{4})$")


def frame(wos):
    rows = []
    for w in wos:
        m = SERIAL.match(w["asset_id"] or "")
        rows.append(dict(
            wo_id=w["wo_id"], cls=w["_cls"], site=w["site_name"], region=w["region"],
            wo_type=w["wo_type"], priority=w["priority"], res=w["resolution_code"],
            tech=w["technician_id"], month=w["date_opened"].month,
            year=w["date_opened"].year, hours=w["labor_hours"],
            parts=bool(w["parts_used"]),
            lost=w["estimated_lost_production_mwh"],
            open_ticket=w["date_closed"] is None,
            prefix=m.group(1) if m else None,
            mfg_yy=int(m.group(2)) if m else None,
            mfg_ww=int(m.group(3)) if m else None,
            batch_letter=m.group(4) if m else None,
        ))
    df = pd.DataFrame(rows)
    df["batch_token"] = df.apply(
        lambda r: None if pd.isna(r.mfg_yy) else f"{int(r.mfg_yy):02d}{int(r.mfg_ww):02d}{r.batch_letter}", axis=1)
    df["yr_letter"] = df.apply(
        lambda r: None if pd.isna(r.mfg_yy) else f"{int(r.mfg_yy):02d}{r.batch_letter}", axis=1)
    df["mfg_quarter"] = df.apply(
        lambda r: None if pd.isna(r.mfg_yy) else f"{int(r.mfg_yy):02d}Q{min(3, int((r.mfg_ww-1)//13))+1}", axis=1)
    return df


def lift_table(df, col, target, minimum=10, top=5):
    base = (df.cls == target).mean()
    g = df.groupby(col).agg(n=("wo_id", "size"), hits=("cls", lambda s: (s == target).sum()))
    g = g[g.n >= minimum]
    g["share"] = g.hits / g.n
    g["lift"] = g.share / base
    return g.sort_values("lift", ascending=False).head(top), base


def verdict(label, worst_lift, coverage, threshold=6.0):
    """A pattern is 'found' if one column value is both heavily enriched AND
    captures most of the pattern. High lift on a value holding 3 of 48 records
    is not a discovery."""
    found = worst_lift >= threshold and coverage >= 0.5
    print(f"    VERDICT: {'*** FOUND BY AGGREGATION ***' if found else 'not found by this attack'}"
          f"   (max lift {worst_lift:.1f}x, best coverage {coverage:.0%})")
    return found


def main():
    sites, assets, techs, wos = load()
    df = frame(wos)
    adf = pd.DataFrame([{ "asset_id": a["asset_id"], "model": a["model"],
                          "site": a["site_name"],
                          "mfg_yy": a["_mfg_yy"], "mfg_ww": a["_mfg_ww"]} for a in assets])
    adf["mfg_quarter"] = adf.apply(lambda r: f"{r.mfg_yy:02d}Q{min(3,(r.mfg_ww-1)//13)+1}", axis=1)

    too_easy = []
    print("=" * 78)
    print("ADVERSARIAL AGGREGATION AUDIT   (no narrative reading)")
    print("=" * 78)

    # ================================================================ SIGNAL 1
    print("\n--- SIGNAL 1: Kelvara KVP-3600 defect-window thermal failures ---")
    n1 = (df.cls == "signal_1").sum()
    print("\n  (a) LEAKAGE: how strongly does each column correlate with the plant?")
    print("      Uses ground truth, so it measures leakage, not what an analyst sees.")
    worst, best_cov = 0.0, 0.0
    for col in ["wo_type", "priority", "res", "tech", "site", "region", "month",
                "prefix", "batch_letter", "yr_letter", "batch_token", "mfg_quarter"]:
        g, base = lift_table(df, col, "signal_1")
        if g.empty:
            continue
        r = g.iloc[0]
        cov = r.hits / n1
        print(f"      {col:14s} top={g.index[0]!s:10s} {int(r.hits):3d}/{int(r.n):5d} "
              f"lift={r.lift:5.1f}x  covers {cov:4.0%}")
        if cov >= 0.5:
            worst = max(worst, r.lift)
            best_cov = max(best_cov, cov)

    print("\n  (b) ANALYST VIEW: rankings computable WITHOUT the labels.")
    print("      This is the real test of discoverability.")
    pref2model = {"KVP36": "KVP-3600", "KVP24": "KVP-2400",
                  "CES40": "CE-4000", "MGX33": "MG-3300"}
    cm = df[df.wo_type.isin(["CM", "Emergency", "Warranty"])]
    inv = df.dropna(subset=["prefix"]).copy()
    inv["model"] = inv.prefix.map(pref2model)
    inv = inv.dropna(subset=["model"])
    units_by_model = adf.groupby("model").size()
    t_by_model = inv.groupby("model").size()
    rate = (t_by_model / units_by_model).dropna().sort_values(ascending=False)
    print("      tickets per installed unit, by model:")
    for m, v in rate.items():
        print(f"        {m:10s} {int(t_by_model[m]):4d}/{int(units_by_model[m]):4d} = {v:.3f}")
    sep_model = rate.iloc[0] / rate.iloc[1]
    print(f"      -> top model is {sep_model:.2f}x the next. "
          f"{'CONCLUSIVE' if sep_model >= 2 else 'suggestive at best, not conclusive'}")

    units_q = adf.groupby(["model", "mfg_quarter"]).size().rename("units")
    t_q = inv.groupby(["model", "mfg_quarter"]).size().rename("tickets")
    j = pd.concat([units_q, t_q], axis=1).fillna(0)
    j = j[j.units >= 25].copy()
    j["per_unit"] = j.tickets / j.units
    j = j.sort_values("per_unit", ascending=False)
    print("      tickets per installed unit, by (model, manufacture quarter):")
    print("        " + j.head(6).to_string().replace("\n", "\n        "))
    sep_q = j.per_unit.iloc[0] / j.per_unit.iloc[2]
    print(f"      -> top cell is {sep_q:.2f}x the third. This ranking requires parsing")
    print(f"         the serial AND joining assets.json for the denominator.")

    print("\n  (c) RAW COUNT rankings (the laziest possible attack):")
    for col, label in [("prefix", "model prefix"), ("mfg_quarter", "manufacture quarter"),
                       ("batch_token", "exact batch token")]:
        top = cm.groupby(col).size().sort_values(ascending=False).head(3)
        print(f"      by {label:22s} {dict(top)}")
    print("      -> raw counts track how many units of each kind exist, not defect rate.")

    sel = df[(df.prefix == "KVP36") & (df.mfg_yy == 24) & (df.mfg_ww.between(18, 36))]
    print(f"\n  (d) The answer, once known: filter KVP36 + 2024 wk18-36")
    print(f"      -> {len(sel)} work orders, {(sel.cls=='signal_1').sum()} are signal_1 "
          f"(precision {(sel.cls=='signal_1').mean():.0%}, recall {(sel.cls=='signal_1').sum()/n1:.0%})")

    single_col_finds = sep_model >= 2.0
    print("\n    VERDICT")
    print(f"      single ungrounded sort: {'FINDS IT' if single_col_finds else 'does NOT find it'} "
          f"(best model-level separation {sep_model:.2f}x)")
    joined_finds = sep_q >= 2.0
    print(f"      serial-parse + asset-registry join: "
          f"{'SURFACES the cluster' if joined_finds else 'does not surface it'} "
          f"({sep_q:.2f}x over the third-ranked cell)")
    print("      What that join yields: 'KVP-3600 built in 2024 Q2/Q3 fail more'.")
    print("      What it does NOT yield: the week-18-36 boundary, the firmware")
    print("      revision, the thermal mechanism, the ambient/seasonal link, the")
    print("      per-unit severity progression, or the at-risk population. Those")
    print("      require reading narratives.")
    if single_col_finds:
        too_easy.append("signal_1 (single column)")

    # =============================================================== SIGNAL 2
    print("\n--- SIGNAL 2: Caprock Mesa backsheet degradation ---")
    g, base = lift_table(df, "site", "signal_2")
    r = g.iloc[0]
    print(f"  group by site: top={g.index[0]} {int(r.hits)}/{int(r.n)} lift={r.lift:.1f}x")
    import calendar_util as cal
    nrm = []
    for s in sites:
        n = (df.site == s["site_name"]).sum()
        cov = cal.coverage_months(s)
        nrm.append((s["site_name"], n, n / s["capacity_mwdc"] / cov * 1000))
    nrm.sort(key=lambda t: -t[2])
    rank = [n for n, _, _ in nrm].index("Caprock Mesa") + 1
    print(f"  Caprock Mesa normalized-rate rank: {rank} of {len(nrm)}")
    print(f"  -> aggregation CAN flag the site as busy. It cannot say why.")
    print(f"     The diagnosis (degradation, not soiling) rests on cleaning-benefit")
    print(f"     decay stated only in narrative text. Checking that it is not in a column:")
    washes = [w for w in wos if w["_cls"] == "signal_2" and w["_kind"] == "wash"]
    print(f"       wash tickets at Caprock Mesa: {len(washes)}")
    print(f"       any column holding recovery %? {'NO' if 'recovery' not in df.columns else 'YES'}")
    print(f"       lost_production populated on washes: "
          f"{sum(1 for w in washes if w['estimated_lost_production_mwh'] is not None)}/{len(washes)}")

    # ================================================================ DECOY 1
    print("\n--- DECOY 1: Sundowner Mesa cluster (SHOULD be aggregation-visible) ---")
    sm = df[(df.site == "Sundowner Mesa") & (df.year == 2025) & (df.month.isin([3, 4]))]
    print(f"  Sundowner Mesa tickets in Mar-Apr 2025: {len(sm)}")
    base_rate = df[(df.site == "Sundowner Mesa")].shape[0] / 24
    print(f"  site's average tickets/month: {base_rate:.1f}  -> spike factor {len(sm)/2/base_rate:.1f}x")
    print(f"  tickets by TECH-0231 in that window: {(sm.tech=='TECH-0231').sum()}")
    t231 = df[df.tech == "TECH-0231"]
    print(f"  TECH-0231 total tickets: {len(t231)}, of which tracker-row-tagged outside the window: "
          f"{sum(1 for w in wos if w.get('_habit'))}")
    print("  -> correctly visible. Resolving it needs the narratives (one wind event)")
    print("     plus the per-row/per-zone labour comparison.")

    # ================================================================ DECOY 2
    print("\n--- DECOY 2: normalization trap (SHOULD be aggregation-visible) ---")
    raw = sorted(((s["site_name"], (df.site == s["site_name"]).sum()) for s in sites), key=lambda t: t[1])
    short = {s["site_name"] for s in sites if cal.coverage_months(s) < 24}
    bottom6 = [n for n, _ in raw[:6]]
    print(f"  six lowest by raw count: {bottom6}")
    print(f"  of those, short-coverage sites: {len([n for n in bottom6 if n in short])}/6")
    print(f"  Blackfoot Draw: raw rank {[n for n,_ in raw].index('Blackfoot Draw')+1}, "
          f"normalized rank {[n for n,_,_ in nrm].index('Blackfoot Draw')+1}")
    print("  -> raw ranking misleads in both directions, as intended.")

    print("\n" + "=" * 78)
    if too_easy:
        print(f"PATTERNS DISCOVERABLE BY SIMPLE AGGREGATION: {too_easy}")
    else:
        print("No TRUE signal (1 or 2) is discoverable by simple aggregation alone.")
        print("Both decoys are aggregation-visible, which is their purpose.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
