"""
Stage 2 — deterministic aggregation. No model calls.

Two families of candidate, because they are structurally different shapes of
finding and a pipeline that only builds the first is blind to the second:

  OCCURRENCE clusters      "N similar events, concentrated somewhere"
  EFFICACY-DECAY clusters  "we keep doing X and X keeps working less well"

The second cannot be found by grouping on symptom: symptom, component, site and
action are all CONSTANT across the group. The pattern lives entirely in the
trend of outcomes over time, which is why Stage 1 has to capture outcome at all.

Exposure normalisation is applied wherever a count is compared. Raw counts in
this corpus track site size, coverage window and crew reporting culture at least
as strongly as they track reliability.
"""

import collections, statistics, datetime
from .corpus_io import coverage_months, site_exposure_gw_months

MIN_CLUSTER = 6
MIN_DECAY_EVENTS = 5

# A cluster keyed on an unclassified symptom is an extraction failure wearing a
# finding's clothes. Excluded from candidate generation and counted instead as a
# Stage 1 quality metric, which is the honest place for it.
UNUSABLE_SYMPTOM = {"other"}
UNUSABLE_COMPONENT = {"other", "none"}


def extraction_quality(recs):
    n = len(recs)
    unclassified = sum(1 for r in recs if r["symptom"] in UNUSABLE_SYMPTOM)
    nocomp = sum(1 for r in recs if r["component"] in UNUSABLE_COMPONENT)
    outcomes = collections.Counter(r["outcome"] for r in recs)
    return {
        "work_orders": n,
        "symptom_unclassified": unclassified,
        "symptom_unclassified_pct": round(100 * unclassified / max(n, 1), 1),
        "component_unclassified": nocomp,
        "component_unclassified_pct": round(100 * nocomp / max(n, 1), 1),
        "outcome_mix": dict(outcomes),
        "outcome_no_change_or_recurring": outcomes["no_change"] + outcomes["recurring"],
    }


def _quarter(yy, ww):
    return f"{yy:02d}Q{min(3, (ww - 1) // 13) + 1}"


def _season(month):
    return {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring",
            5: "spring", 6: "summer", 7: "summer", 8: "summer", 9: "autumn",
            10: "autumn", 11: "autumn"}[month]


def build_records(wos, det, ext, sites, assets):
    """One flat record per work order combining structured, deterministic and
    model-extracted fields."""
    recs = []
    for w in wos:
        dd, ee = det[w["wo_id"]], ext[w["wo_id"]]
        site = sites[w["site_name"]]
        rec = dict(
            wo_id=w["wo_id"], site=w["site_name"], region=site["region"],
            date=w["_d"], month=w["_d"].month, year=w["_d"].year,
            season=_season(w["_d"].month), wo_type=w["wo_type"],
            priority=w["priority"], tech=w["technician_id"],
            asset_id=w["asset_id"], labor_hours=w["labor_hours"],
            parts_used=w["parts_used"],
            lost_mwh=w["estimated_lost_production_mwh"],
            resolution_code=w["resolution_code"],
            symptom=ee["symptom"], component=ee["component"],
            environment=ee["environment"], action=ee["action"],
            outcome=ee["outcome"], benefit=ee["quantified_benefit_pct"],
            uncertain=ee["uncertainty_expressed"],
            recurrence=ee["recurrence_language"],
            asset_model=dd["asset_model"], serial_prefix=dd["serial_prefix"],
            mfg_yy=dd["serial_mfg_yy"], mfg_ww=dd["serial_mfg_ww"],
            batch_letter=dd["serial_batch_letter"],
            versions=dd["versions_in_narrative"],
            warranty_active=dd["warranty_active_at_ticket"],
        )
        rec["mfg_quarter"] = (_quarter(rec["mfg_yy"], rec["mfg_ww"])
                              if rec["mfg_yy"] is not None else None)
        recs.append(rec)
    return recs


# ---------------------------------------------------------------- exposure
def exposure_index(sites):
    """GW-months of coverage per site, and the fleet total."""
    per = {n: site_exposure_gw_months(s) for n, s in sites.items()}
    return per, sum(per.values())


def asset_population(assets):
    """Installed base by (model, manufacture quarter) — the denominator that
    turns a raw ticket count into a defect RATE."""
    pop = collections.Counter()
    by_model = collections.Counter()
    for a in assets.values():
        from .stage1_extract import parse_serial
        s = parse_serial(a["asset_id"])
        if not s:
            continue
        pop[(a["model"], _quarter(s["mfg_yy"], s["mfg_ww"]))] += 1
        by_model[a["model"]] += 1
    return pop, by_model


# ------------------------------------------------------------- candidates
def occurrence_candidates(recs, sites, assets):
    out = []
    per_site, fleet_gwm = exposure_index(sites)
    pop, by_model = asset_population(assets)
    corrective = [r for r in recs if r["wo_type"] in ("CM", "Emergency", "Warranty")
                  and r["symptom"] not in UNUSABLE_SYMPTOM]

    # --- 1. serial cohort, normalised by installed units --------------------
    # A manufacturing defect is a property of the BUILD, not of a symptom label.
    # It presents as a family: the same bad batch shows up as thermal derate,
    # over-temperature trip, fan fault, IGBT damage or hard shutdown depending
    # on severity and on when a technician happened to catch it. Grouping on
    # exact symptom splits one physical population across five labels and then
    # tests each fragment against a threshold sized for a whole cohort.
    #
    # So the grouping key is (model, manufacture quarter). Symptom composition
    # is evidence ABOUT the cohort, carried as a secondary attribute, not the
    # thing that defines it.
    #
    # The peer baseline changes accordingly, and improves: other manufacture
    # quarters of the SAME model. That holds equipment design fixed and varies
    # only the build window, which is exactly the comparison a warranty claim
    # has to survive.
    g = collections.defaultdict(list)
    for r in corrective:
        if r["asset_model"] and r["mfg_quarter"]:
            g[(r["asset_model"], r["mfg_quarter"])].append(r)
    for (model, q), members in g.items():
        units = pop.get((model, q), 0)
        if len(members) < MIN_CLUSTER or units < 10:
            continue
        rate = len(members) / units
        peer = [len(v) / max(pop.get((m2, q2), 1), 1)
                for (m2, q2), v in g.items() if m2 == model and q2 != q
                and pop.get((m2, q2), 0) >= 10]
        base = statistics.median(peer) if peer else 0.0
        mix = collections.Counter(r["symptom"] for r in members)
        top = mix.most_common(4)
        out.append(dict(
            kind="serial_cohort", key=f"{model}|{q}",
            label=f"{model} manufactured {q} ({units} units): "
                  + ", ".join(f"{k} x{v}" for k, v in top),
            members=[r["wo_id"] for r in members], n=len(members),
            units_in_cohort=units, rate_per_unit=round(rate, 3),
            peer_median_rate=round(base, 3),
            peer_quarters=len(peer),
            symptom_mix=dict(mix),
            distinct_symptoms=len(mix),
            lift=round(rate / base, 2) if base else None,
            dims=dict(model=model, mfg_quarter=q,
                      symptoms=[k for k, _ in top])))

    # --- 2. equipment model x symptom, normalised by installed units --------
    g2 = collections.defaultdict(list)
    for r in corrective:
        if r["asset_model"]:
            g2[(r["asset_model"], r["symptom"])].append(r)
    for (model, sym), members in g2.items():
        units = by_model.get(model, 0)
        if len(members) < MIN_CLUSTER or units < 20:
            continue
        rate = len(members) / units
        peer = [len(v) / max(by_model.get(m2, 1), 1)
                for (m2, s2), v in g2.items() if s2 == sym and m2 != model]
        base = statistics.median(peer) if peer else 0.0
        out.append(dict(
            kind="model_symptom", key=f"{model}|{sym}",
            label=f"{model}, symptom '{sym}'",
            members=[r["wo_id"] for r in members], n=len(members),
            units_in_cohort=units, rate_per_unit=round(rate, 3),
            peer_median_rate=round(base, 3),
            lift=round(rate / base, 2) if base else None,
            dims=dict(model=model, symptom=sym)))

    # --- 3. site x symptom, normalised by GW-months of coverage -------------
    g3 = collections.defaultdict(list)
    for r in corrective:
        g3[(r["site"], r["symptom"])].append(r)
    sym_tot = collections.Counter(r["symptom"] for r in corrective)
    for (site, sym), members in g3.items():
        if len(members) < MIN_CLUSTER:
            continue
        gwm = per_site.get(site, 0) or 1
        rate = len(members) / gwm
        fleet_rate = sym_tot[sym] / fleet_gwm
        out.append(dict(
            kind="site_symptom", key=f"{site}|{sym}",
            label=f"{site}, symptom '{sym}'",
            members=[r["wo_id"] for r in members], n=len(members),
            exposure_gw_months=round(gwm, 1),
            rate_per_gw_month=round(rate, 2),
            fleet_rate_per_gw_month=round(fleet_rate, 2),
            lift=round(rate / fleet_rate, 2) if fleet_rate else None,
            dims=dict(site=site, symptom=sym)))

    # --- 4. time-bounded bursts: site x component in a rolling 8-week window -
    g4 = collections.defaultdict(list)
    for r in recs:
        g4[(r["site"], r["component"])].append(r)
    for (site, comp), members in g4.items():
        if len(members) < MIN_CLUSTER or comp in UNUSABLE_COMPONENT:
            continue
        members = sorted(members, key=lambda r: r["date"])
        best = None
        for i, r0 in enumerate(members):
            win = [r for r in members[i:] if (r["date"] - r0["date"]).days <= 56]
            if best is None or len(win) > len(best[0]):
                best = (win, r0["date"])
        win, start = best
        share = len(win) / len(members)
        if len(win) >= max(MIN_CLUSTER, 8) and share >= 0.45:
            out.append(dict(
                kind="temporal_burst", key=f"{site}|{comp}|{start}",
                label=f"{site}, {comp}: {len(win)} tickets in 8 weeks from {start}",
                members=[r["wo_id"] for r in win], n=len(win),
                burst_share_of_site_component=round(share, 2),
                window_start=str(start),
                dims=dict(site=site, component=comp, window_start=str(start))))

    # --- 5. data-quality: technician logging granularity --------------------
    tr = collections.defaultdict(lambda: collections.Counter())
    for r in recs:
        if r["component"] in ("tracker_drive", "tracker_motor", "tracker_controller",
                              "tracker_structure") and r["asset_id"]:
            gran = "row" if r["asset_id"].upper().startswith("TR-B") else (
                "zone" if r["asset_id"].upper().startswith("TR-Z") else "other")
            tr[r["tech"]][gran] += 1
    peers = {t: c for t, c in tr.items() if sum(c.values()) >= 8}
    if peers:
        fleet_row_share = (sum(c["row"] for c in peers.values())
                           / max(sum(sum(c.values()) for c in peers.values()), 1))
        for tech, c in peers.items():
            tot = sum(c.values())
            share = c["row"] / tot
            if share >= 0.85 and fleet_row_share < 0.75 and tot >= 10:
                mem = [r["wo_id"] for r in recs if r["tech"] == tech
                       and (r["asset_id"] or "").upper().startswith("TR-B")]
                out.append(dict(
                    kind="logging_granularity", key=f"{tech}|per_row",
                    label=f"{tech} logs tracker work per ROW ({share:.0%}) vs fleet {fleet_row_share:.0%}",
                    members=mem, n=len(mem), tech_row_share=round(share, 2),
                    fleet_row_share=round(fleet_row_share, 2),
                    dims=dict(technician=tech)))
    return out


def decay_candidates(recs):
    """Repeated intervention whose benefit flattens or disappears over time.

    Deliberately blind to symptom: the whole point is that symptom, component,
    site and action are all constant. Only the OUTCOME trend moves.
    """
    out = []
    g = collections.defaultdict(list)
    for r in recs:
        if r["action"] in ("cleaned_or_serviced", "adjusted_or_recalibrated",
                           "repaired_in_place", "reset_or_restart", "part_replaced"):
            g[(r["site"], r["action"], r["component"])].append(r)
    for (site, action, comp), members in g.items():
        if len(members) < MIN_DECAY_EVENTS or comp in UNUSABLE_COMPONENT:
            continue
        members = sorted(members, key=lambda r: r["date"])
        half = len(members) // 2
        early, late = members[:half], members[half:]

        def bad_share(rows):
            return sum(1 for r in rows
                       if r["outcome"] in ("no_change", "recurring")) / max(len(rows), 1)

        eb, lb = bad_share(early), bad_share(late)
        ben_e = [r["benefit"] for r in early if r["benefit"] is not None]
        ben_l = [r["benefit"] for r in late if r["benefit"] is not None]
        benefit_drop = None
        if ben_e and ben_l:
            benefit_drop = round(statistics.mean(ben_e) - statistics.mean(ben_l), 2)

        worsening = (lb - eb) >= 0.25 or (benefit_drop is not None and benefit_drop >= 1.0)
        if not worsening:
            continue
        out.append(dict(
            kind="efficacy_decay", key=f"{site}|{action}|{comp}",
            label=f"{site}: repeated {action} on {comp} with declining benefit",
            members=[r["wo_id"] for r in members], n=len(members),
            early_ineffective_share=round(eb, 2), late_ineffective_share=round(lb, 2),
            mean_benefit_early_pct=round(statistics.mean(ben_e), 2) if ben_e else None,
            mean_benefit_late_pct=round(statistics.mean(ben_l), 2) if ben_l else None,
            benefit_drop_pct=benefit_drop,
            span=f"{members[0]['date']} to {members[-1]['date']}",
            dims=dict(site=site, action=action, component=comp)))
    return out


def _anomaly(c):
    """How unusual is this cluster relative to a matched baseline?

    Multiplicative, not additive. A cluster whose normalised rate equals its
    peers' is by definition unremarkable no matter how many hours it consumed —
    additive scoring let below-baseline clusters (lift 0.58) outrank 9x outliers
    purely on volume, which put the wrong candidates in front of the model.
    """
    if c["kind"] in ("serial_cohort", "model_symptom", "site_symptom"):
        lift = c.get("lift")
        if lift is None:
            # no peer had this symptom at all: genuinely novel, treat as strong
            return 2.5
        return max(0.15, min(float(lift), 10.0)) / 2.0
    if c["kind"] == "temporal_burst":
        return 0.5 + 2.0 * c.get("burst_share_of_site_component", 0.0)
    if c["kind"] == "logging_granularity":
        fleet = max(c.get("fleet_row_share", 0.5), 0.01)
        return max(0.3, min(c.get("tech_row_share", 0) / fleet, 4.0))
    if c["kind"] == "efficacy_decay":
        delta = c.get("late_ineffective_share", 0) - c.get("early_ineffective_share", 0)
        drop = c.get("benefit_drop_pct") or 0.0
        return 0.5 + 3.0 * max(delta, 0) + 0.35 * max(drop, 0)
    return 1.0


def materiality(c, recs_by_id):
    """Deterministic ranking so stages 3-4 have a bounded budget.

    score = material volume x how anomalous it is. Volume uses only observable
    quantities; no model output and no dollar figures enter the ranking.
    """
    mem = [recs_by_id[w] for w in c["members"] if w in recs_by_id]
    hours = sum(r["labor_hours"] or 0 for r in mem)
    mwh = sum(r["lost_mwh"] or 0 for r in mem)
    p1p2 = sum(1 for r in mem if r["priority"] in ("P1", "P2"))
    volume = hours * 0.4 + mwh * 1.2 + p1p2 * 3 + c["n"] * 1.5
    anomaly = _anomaly(c)
    c["_materiality"] = round(volume * anomaly, 1)
    c["_volume"] = round(volume, 1)
    c["_anomaly"] = round(anomaly, 2)
    c["_labor_hours"] = round(hours, 1)
    c["_lost_mwh"] = round(mwh, 1)
    return c["_materiality"]


# How deep to examine. A fixed rank cutoff ("top 15") is not defensible: 15 of
# 57 and 15 of 200 are completely different depths, and this distribution has no
# natural break after about rank 7 — it decays smoothly, so any rank in the teens
# is an arbitrary point on a smooth curve.
#
# Coverage is scale-free and states what it buys: examine clusters until they
# account for COVERAGE of total estimated materiality. The floor and cap keep a
# degenerate distribution (one huge cluster, or a long flat tail) from examining
# almost nothing or almost everything.
#
# The economics argue for examining deep. Examining one candidate costs about
# $0.21 in reasoning calls. Missing one costs a finding — the Kelvara cohort
# carries $3.6M of replacement exposure. And because "examined and declined" is
# a first-class output, a candidate that turns out to be nothing is still a
# rendered result showing the system discriminates, not wasted spend.
COVERAGE = 0.80
MIN_BUDGET = 20
MAX_BUDGET = 35


def examine_depth(cands, coverage=COVERAGE, lo=MIN_BUDGET, hi=MAX_BUDGET):
    """How many ranked candidates to carry into stages 3-4, and why."""
    total = sum(c["_materiality"] for c in cands) or 1.0
    cum, n = 0.0, 0
    for c in cands:
        cum += c["_materiality"]
        n += 1
        if cum / total >= coverage:
            break
    return max(lo, min(n, hi, len(cands)))


def run(recs, sites, assets, budget=None):
    cands = occurrence_candidates(recs, sites, assets) + decay_candidates(recs)
    by_id = {r["wo_id"]: r for r in recs}
    for c in cands:
        materiality(c, by_id)
    cands.sort(key=lambda c: -c["_materiality"])
    for i, c in enumerate(cands):
        c["candidate_id"] = f"CAND-{i+1:03d}"
    n = budget if budget else examine_depth(cands)
    return cands, cands[:n]
