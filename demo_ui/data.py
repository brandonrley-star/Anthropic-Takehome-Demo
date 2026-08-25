"""
Read-only data layer for the Field Intelligence demo UI.

Loads the committed live-run artifacts and the corpus once at import. Nothing
here computes a new finding, re-ranks anything, or calls a model. The pipeline
remains the only thing that produces analysis; this module only reads what it
already produced.

eval/ is never imported, never read, and never served. The pipeline enforces
that in code (pipeline/paths.py); this module simply never refers to it.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pipeline import corpus_io  # noqa: E402  - reused so UI and pipeline agree

LIVE_RUN = os.path.join(ROOT, "demo", "live_run")
CORPUS = os.path.join(ROOT, "corpus")

VERDICTS = ("escalate", "deprioritize", "decline")


def _json(path):
    with open(path) as f:
        return json.load(f)


# --------------------------------------------------------------- raw sources
FINDINGS = _json(os.path.join(LIVE_RUN, "findings.json"))
CANDIDATES = _json(os.path.join(LIVE_RUN, "candidates.json"))
MANIFEST = _json(os.path.join(LIVE_RUN, "run_manifest.json"))

_WOS = _json(os.path.join(CORPUS, "work_orders.json"))
WORK_ORDERS = {w["wo_id"]: w for w in _WOS}
SITES = {s["site_name"]: s for s in _json(os.path.join(CORPUS, "sites.json"))}
ASSETS = {a["asset_id"]: a for a in _json(os.path.join(CORPUS, "assets.json"))}

CAND_BY_ID = {c["candidate_id"]: c for c in CANDIDATES}
_RANK = {c["candidate_id"]: i for i, c in enumerate(
    sorted(CANDIDATES, key=lambda c: -c["_materiality"]), 1)}


# ------------------------------------------------------------------ overview
def _dedup_realised(finding_ids):
    """Sum incurred cost over the UNION of member work orders.

    Findings can share work orders, so summing their totals would double-count.
    Costing the de-duplicated union is the only figure that adds up.
    """
    from pipeline import cost_model as cm
    ids = set()
    for cid in finding_ids:
        ids.update(FINDINGS[cid]["candidate"]["members"])
    mem = [WORK_ORDERS[i] for i in sorted(ids) if i in WORK_ORDERS]
    r = cm.realised_cost(mem) if mem else None
    return r, len(mem)


# Which escalated findings describe a KVP-3600 INVERTER population.
#
# The cost model prices exactly one kind of replacement: an inverter, at
# $62,000. Applying that to MV collector circuits (CAND-010), module blocks
# (CAND-017) or individual PV modules (CAND-031, which the model itself prices
# at $210) produces a number that is not defensible, so those populations are
# reported as counts and excluded from the dollar total rather than mispriced.
#
# Among the inverter populations, CAND-002 is the full 2024 KVP-3600 build
# (24Q1 45 + 24Q2 53 + 24Q3 44 + 24Q4 37 = 179). CAND-006 (44, being 24Q3) and
# CAND-014 (8, being week 32, inside 24Q3) are strict subsets of it. Claude
# returned population_shared_with = [] on all three, so the renderer treated
# them as distinct and summed them. Taking the largest population instead of
# the sum is the correct de-duplication.
INVERTER_POPULATION_FINDINGS = ("CAND-002", "CAND-006", "CAND-014")


def overview():
    esc = [c for c, f in FINDINGS.items() if f["verdict"]["verdict"] == "escalate"]
    counts = {v: sum(1 for f in FINDINGS.values() if f["verdict"]["verdict"] == v)
              for v in VERDICTS}
    realised, n_wo = _dedup_realised(esc)

    # No aggregate replacement-exposure figure is published at fleet level.
    # The per-finding populations overlap (CAND-002's 179 units contain
    # CAND-006's 44 and CAND-014's 8) and the cost model prices only inverter
    # replacement, so summing them across heterogeneous populations produces a
    # number that cannot be defended. Exposure stays on individual findings,
    # where its basis is stated. See _exposure_note().
    warranty = sum(FINDINGS[c]["finance"]["warranty_recoverable_usd"] for c in esc)
    total_mw = sum(s["capacity_mwdc"] for s in SITES.values())

    return {
        "work_orders": MANIFEST["work_orders"],
        "sites": MANIFEST["sites"],
        "fleet_gw": round(total_mw / 1000.0, 2),
        "window": MANIFEST["window"],
        "candidates_total": MANIFEST["candidates_total"],
        "candidates_examined": MANIFEST["candidates_examined"],
        "verdict_counts": counts,
        "commercial": {
            "incurred_low": realised["total_low_usd"] if realised else 0,
            "incurred_high": realised["total_high_usd"] if realised else 0,
            "incurred_work_orders": n_wo,
            "labor_hours": round(realised["labor_hours"], 1) if realised else 0,
            "warranty_recoverable": warranty,
        },
        "replay_steps": [
            f"{MANIFEST['work_orders']:,} technician reports interpreted",
            f"{MANIFEST['candidates_total']} candidate patterns generated",
            f"{MANIFEST['candidates_examined']} materially ranked candidates examined",
            "Competing hypotheses evaluated, including benign explanations",
            "Matched controls tested against each cluster",
            f"{counts['escalate']} escalated · {counts['deprioritize']} deprioritised "
            f"· {counts['decline']} declined",
        ],
    }


# Elapsed wall clock comes from the manifest's explicit runtime block, which
# names what each figure measures. It is no longer derived from a single
# ambiguous field, and no longer hardcoded here.
RUNTIME = MANIFEST.get("runtime", {})
ANALYSIS_SECONDS = RUNTIME.get("analysis_wall_clock_seconds", 0)


def provenance():
    a = MANIFEST["accounting"]
    p = MANIFEST.get("provenance", {})
    stages = []
    for name, s in a["stages"].items():
        if s["calls"] or s["cache_hits"]:
            stages.append({"stage": name, "model": s.get("model"),
                           "calls": s["calls"], "usd": round(s["usd"], 2)})
    return {
        "model": MANIFEST["model"],
        "stage1_backend": MANIFEST["stage1_backend"],
        "reasoning_backend": MANIFEST["reasoning_backend"],
        "generated_at_utc": MANIFEST.get("generated_at_utc"),
        "stages": stages,
        "findings_cost_usd": p.get("total_usd_to_produce", a.get("total_usd")),
        "analysis_seconds": round(ANALYSIS_SECONDS),
        "analysis_minutes": round(RUNTIME.get("analysis_wall_clock_minutes",
                                              ANALYSIS_SECONDS / 60)),
        "analysis_definition": RUNTIME.get("analysis_definition", ""),
        "producing_runs": RUNTIME.get("producing_runs", []),
        "session_cost_usd": p.get("session_total_usd"),
        "extraction_quality": MANIFEST["extraction_quality"],
    }


# ---------------------------------------------------------------- baseline
def baseline_ranking():
    """Raw ticket count vs exposure-normalised rate. Deterministic, no model.

    Uses pipeline.corpus_io so this chart cannot drift from the detector.
    """
    raw = {}
    for w in _WOS:
        raw[w["site_name"]] = raw.get(w["site_name"], 0) + 1
    rows = []
    for name, site in SITES.items():
        gwm = corpus_io.site_exposure_gw_months(site)
        n = raw.get(name, 0)
        rows.append({"site": name, "tickets": n, "mw": site["capacity_mwdc"],
                     "months": corpus_io.coverage_months(site),
                     "gw_months": round(gwm, 2),
                     "rate": round(n / gwm, 1) if gwm else 0.0})
    by_raw = sorted(rows, key=lambda r: -r["tickets"])
    by_rate = sorted(rows, key=lambda r: -r["rate"])
    rr = {r["site"]: i for i, r in enumerate(by_raw, 1)}
    nr = {r["site"]: i for i, r in enumerate(by_rate, 1)}
    for r in rows:
        r["raw_rank"] = rr[r["site"]]
        r["norm_rank"] = nr[r["site"]]
        r["move"] = rr[r["site"]] - nr[r["site"]]
    return {
        "by_raw": sorted(rows, key=lambda r: r["raw_rank"]),
        "by_rate": sorted(rows, key=lambda r: r["norm_rank"]),
        "movers": sorted(rows, key=lambda r: -abs(r["move"]))[:6],
        "total_sites": len(rows),
    }


# ---------------------------------------------------------------- findings
def _card(cid):
    f = FINDINGS[cid]
    c, v, fin = f["candidate"], f["verdict"], f["finance"]
    return {
        "candidate_id": cid,
        "rank": _RANK.get(cid),
        "kind": c["kind"],
        "label": c["label"],
        "verdict": v["verdict"],
        "confidence": v["confidence"],
        "headline": v.get("business_headline", ""),
        "action": v.get("recommended_action", ""),
        "action_type": v.get("action_type", ""),
        "n_work_orders": c["n"],
        "n_cited": len(v.get("supporting_wo_ids") or []),
        "population": (v.get("population_at_risk") or {}).get("count", 0),
        "incurred_low": fin["realised"]["total_low_usd"],
        "incurred_high": fin["realised"]["total_high_usd"],
        "warranty": fin["warranty_recoverable_usd"],
        "lift": c.get("lift"),
    }


def findings_list():
    cards = [_card(c) for c in FINDINGS]
    order = {"escalate": 0, "deprioritize": 1, "decline": 2}
    cards.sort(key=lambda x: (order[x["verdict"]], -x["incurred_high"]))
    return cards


def finding_detail(cid):
    if cid not in FINDINGS:
        return None
    f = FINDINGS[cid]
    c, v, fin = f["candidate"], f["verdict"], f["finance"]
    d = _card(cid)
    d.update({
        "reasoning": v.get("reasoning", ""),
        "contradicting": v.get("contradicting_evidence", ""),
        "population_detail": v.get("population_at_risk") or {},
        "selected_hypothesis": v.get("selected_hypothesis"),
        "hypotheses": (f.get("hypotheses") or {}).get("hypotheses", []),
        "supporting_wo_ids": v.get("supporting_wo_ids") or [],
        "members": c["members"],
        "cost_basis": fin["realised"],
        "replacement_exposure": fin["replacement_exposure_usd"],
        "exposure_note": _exposure_note(cid),
        "dims": c.get("dims", {}),
        "units_in_cohort": c.get("units_in_cohort"),
        "rate_per_unit": c.get("rate_per_unit"),
        "peer_median_rate": c.get("peer_median_rate"),
        "symptom_mix": c.get("symptom_mix"),
    })
    return d


def _exposure_note(cid):
    """Say plainly when a per-finding exposure figure is priced on inverters."""
    if cid in INVERTER_POPULATION_FINDINGS:
        return None
    f = FINDINGS.get(cid)
    if not f or not f["finance"]["replacement_exposure_usd"]:
        return None
    return ("Priced at the cost model's inverter replacement rate. This "
            "population is not inverters, so treat the count as the reliable "
            "figure and this dollar value as indicative only.")


def work_order(wo_id):
    w = WORK_ORDERS.get(wo_id)
    if not w:
        return None
    a = ASSETS.get(w.get("asset_id") or "")
    return {
        "wo_id": w["wo_id"], "site": w["site_name"], "date": w["date_opened"],
        "date_closed": w.get("date_closed"), "type": w.get("wo_type"),
        "priority": w.get("priority"), "asset_id": w.get("asset_id"),
        "asset_model": a["model"] if a else None,
        "asset_manufacturer": a.get("manufacturer") if a else None,
        "technician_id": w.get("technician_id"),
        "labor_hours": w.get("labor_hours"),
        "parts_used": w.get("parts_used"),
        "resolution_code": w.get("resolution_code"),
        "lost_mwh": w.get("estimated_lost_production_mwh"),
        "narrative": w.get("narrative"),
    }


def work_orders(ids):
    return [w for w in (work_order(i) for i in ids) if w]
