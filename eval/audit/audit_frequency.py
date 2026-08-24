"""Confirm each planted pattern appears at the intended frequency and spread."""
import collections, sys
from _common import load
sys.path.insert(0, "/home/user/Anthropic-Takehome-Demo/generator")
import fleet

EXPECT = {"signal_1": 48, "signal_2": 26, "decoy_1": 31,
          "distractor_slew": 38, "distractor_comms": 44}

def main():
    sites, assets, techs, wos = load()
    ok = True
    print("=" * 78)
    print("FREQUENCY AUDIT")
    print("=" * 78)
    counts = collections.Counter(w["_cls"] for w in wos)
    print(f"\ntotal work orders: {len(wos)}\n")
    for cls, want in EXPECT.items():
        got = counts[cls]
        flag = "OK " if got == want else "FAIL"
        if got != want: ok = False
        print(f"  [{flag}] {cls:20s} {got:4d}  (intended {want})")
    print(f"  [OK ] {'background':20s} {counts['background']:4d}")

    # ---- Signal 1
    s1 = [w for w in wos if w["_cls"] == "signal_1"]
    units = collections.Counter(w["asset_id"] for w in s1)
    s1sites = collections.Counter(w["site_name"] for w in s1)
    defect = [a for a in assets if a["_defect_window"]]
    hot = {"ERCOT_WEST", "ERCOT_SOUTH", "CAISO_CV", "CAISO_MOJAVE"}
    by_site = {s["site_name"]: s for s in sites}
    print(f"\nSIGNAL 1 — Kelvara KVP-3600 defect-window thermal degradation")
    print(f"  work orders            {len(s1)}")
    print(f"  distinct units         {len(units)}   (intended 30)")
    print(f"  distinct sites         {len(s1sites)}   (intended 9)")
    print(f"  sites match spec       {sorted(s1sites) == sorted(fleet.SIGNAL1_SITES)}")
    print(f"  max WOs at any site    {max(s1sites.values())}  ({max(s1sites, key=s1sites.get)})")
    print(f"  distinct technicians   {len({w['technician_id'] for w in s1})}")
    print(f"  distinct symptom types {len({w['_sym'] for w in s1})}")
    print(f"  distinct resolution cd {len({w['resolution_code'] for w in s1})}")
    print(f"  span                   {min(w['date_opened'] for w in s1)} -> {max(w['date_opened'] for w in s1)}")
    print(f"  by year                {dict(sorted(collections.Counter(w['date_opened'].year for w in s1).items()))}")
    print(f"  by month               {dict(sorted(collections.Counter(w['date_opened'].month for w in s1).items()))}")
    print(f"  outside May-Sep        {sum(1 for w in s1 if w['date_opened'].month not in (5,6,7,8,9))}")
    print(f"  severity stage mix     {dict(sorted(collections.Counter(w['_stage'] for w in s1).items()))}")
    print(f"  repeat visits/unit     {dict(sorted(collections.Counter(units.values()).items()))}")
    print(f"  firmware mentions      {sum(1 for w in s1 if w.get('_fw'))}")
    print(f"  fan-control guesses    {sum(1 for w in s1 if w.get('_speculation'))}")
    print(f"\n  defect-window units in fleet   {len(defect)}")
    print(f"    at hot-region sites          {sum(1 for a in defect if by_site[a['site_name']]['region'] in hot)}")
    print(f"    at cool-region sites         {sum(1 for a in defect if by_site[a['site_name']]['region'] not in hot)}")
    print(f"    sites holding them           {len({a['site_name'] for a in defect})}  (only {len(s1sites)} show failures)")
    print(f"    with failure history         {len(units)}")
    print(f"    at risk, no failure yet      {len(defect) - len(units)}")

    # ---- Signal 2
    s2 = [w for w in wos if w["_cls"] == "signal_2"]
    print(f"\nSIGNAL 2 — Caprock Mesa backsheet degradation read as soiling")
    print(f"  work orders            {len(s2)}  all at {sorted({w['site_name'] for w in s2})}")
    print(f"  kinds                  {dict(collections.Counter(w['_kind'] for w in s2))}")
    halves = collections.Counter((w["date_opened"].year, (w["date_opened"].month - 1)//6) for w in s2)
    print(f"  per half-year          {dict(sorted(halves.items()))}  (rising)")
    old = sum(1 for w in s2 if w["_block"] in ("B01","B02","B03","B04"))
    print(f"  in older blocks B01-04 {old} of {len(s2)}")
    print(f"  distinct technicians   {len({w['technician_id'] for w in s2})}")

    # ---- Decoy 1
    d1 = [w for w in wos if w["_cls"] == "decoy_1"]
    modes = collections.Counter(w["_mode"] for w in d1)
    habit = [w for w in wos if w.get("_habit")]
    print(f"\nDECOY 1 — Sundowner Mesa wind event plus a logging artifact")
    print(f"  work orders            {len(d1)}  at {sorted({w['site_name'] for w in d1})}")
    print(f"  window                 {min(w['date_opened'] for w in d1)} -> {max(w['date_opened'] for w in d1)}")
    print(f"  per-row vs per-zone    {dict(modes)}")
    print(f"  logged by TECH-0231    {sum(1 for w in d1 if w['technician_id']=='TECH-0231')}")
    print(f"  narratives naming event{sum(1 for w in d1 if w.get('_names_event'))}")
    print(f"  carrying claim ref     {sum(1 for w in d1 if w.get('_claim'))}")
    print(f"  TECH-0231 per-row work OUTSIDE the event window: {len(habit)}")
    lh_row = [w["labor_hours"] for w in d1 if w["_mode"]=="per_row"]
    lh_zone = [w["labor_hours"] for w in d1 if w["_mode"]=="per_zone"]
    print(f"  mean labor_hours       per-row {sum(lh_row)/len(lh_row):.1f}  per-zone {sum(lh_zone)/len(lh_zone):.1f}")

    # ---- Decoy 2
    print(f"\nDECOY 2 — normalization trap (structural, consumes no work orders)")
    import calendar_util as cal
    rows = []
    for s in sites:
        n = sum(1 for w in wos if w["site_name"] == s["site_name"])
        cov = cal.coverage_months(s)
        rows.append((s["site_name"], n, cov, n / s["capacity_mwdc"] / cov * 1000))
    rows.sort(key=lambda r: r[1])
    print("  lowest RAW count (the naive 'most reliable' list):")
    for nm, n, cov, nrm in rows[:6]:
        print(f"    {nm:22s} raw={n:4d}  cov={cov:2d}mo  norm={nrm:5.1f}")
    rows.sort(key=lambda r: -r[3])
    print("  highest NORMALIZED (WO per GW per month):")
    for nm, n, cov, nrm in rows[:4]:
        print(f"    {nm:22s} norm={nrm:5.1f}  raw={n:4d}  cov={cov:2d}mo")

    # ---- distractors
    for cls, label in [("distractor_slew", "Auster slew drive grease"),
                       ("distractor_comms", "Soltera ST-250 comms dropouts")]:
        d = [w for w in wos if w["_cls"] == cls]
        print(f"\nDISTRACTOR — {label}")
        print(f"  work orders {len(d)} across {len({w['site_name'] for w in d})} sites: "
              f"{sorted({w['site_name'] for w in d})}")
        lost = [w["estimated_lost_production_mwh"] for w in d
                if w["estimated_lost_production_mwh"] is not None]
        print(f"  lost production recorded on {len(lost)}/{len(d)}, total "
              f"{sum(lost):.1f} MWh")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
