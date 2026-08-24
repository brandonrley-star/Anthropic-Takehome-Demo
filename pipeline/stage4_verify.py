"""
Stage 4 — verification against matched controls.

The control set is MATCHED (same site or same equipment model, same season,
non-member), not random. "Is the evidence consistent with H?" is trivially yes
against random vegetation tickets; it is a real question against work of the
same kind on the same equipment that is NOT in the cluster.

This stage must be able to return "decline". That is the point of it.
"""
import json, random

SYSTEM = """You are adjudicating a candidate finding for a solar O&M provider's \
asset-management team.

You receive: the candidate's aggregate profile, the competing hypotheses from the \
previous stage, full narratives for cluster members, and full narratives for a \
MATCHED CONTROL set of comparable work orders that are NOT in the cluster.

Decide. Return ONE JSON object:

{"verdict":"escalate|decline|deprioritize",
 "confidence":"high|medium|low",
 "selected_hypothesis":"H2",
 "reasoning":"3-6 sentences. Say why the selected hypothesis beats the others, \
citing what you saw in members versus controls.",
 "supporting_wo_ids":["..."],
 "contradicting_evidence":"What argues against the verdict, or 'none identified'.",
 "population_at_risk":{"count":0,"description":"","basis":"how the count was derived, or 'not quantifiable from this data'"},
 "population_shared_with":["CAND-0NN"],
 "recommended_action":"one sentence, an action a person can take",
 "action_type":"warranty_claim|remediation_campaign|engineering_assessment|data_quality_fix|monitor_only|none",
 "business_headline":"one sentence a VP of Asset Management would act on"}

Verdict meanings:
- escalate      real, material, and worth commercial action now.
- deprioritize  real but low financial impact. Say so plainly and give the impact reasoning.
- decline       not a systemic finding. A discrete event, a reporting artifact, \
expected wear, or ordinary variation once normalised by installed base.

Rules:
- DECLINE IS A RESULT, NOT A FAILURE. If the controls look the same as the members, \
say so and decline.
- Every claim must cite wo_ids that appear in the data you were given. Do not cite \
a wo_id you have not seen.
- Do not produce dollar figures. Quantities only: units, hours, MWh, counts. \
Financial modelling happens downstream in auditable code.
- population_at_risk.count must be derivable from what you were shown, or 0 with \
basis 'not quantifiable from this data'.
- population_shared_with lists any OTHER candidate_ids whose at-risk population is \
the same physical fleet as this one. Exposure for shared populations is counted once \
downstream, not once per candidate. Empty list if the population is this cluster's alone."""


def matched_controls(cand, recs, recs_by_id, n=10, seed=11):
    """Non-members that resemble members on site / equipment / season."""
    rng = random.Random(seed + cand["n"])
    members = set(cand["members"])
    mem = [recs_by_id[w] for w in cand["members"] if w in recs_by_id]
    if not mem:
        return []
    sites = {r["site"] for r in mem}
    models = {r["asset_model"] for r in mem if r["asset_model"]}
    comps = {r["component"] for r in mem}
    seasons = {r["season"] for r in mem}

    def score(r):
        if r["wo_id"] in members:
            return -1
        s = 0
        if r["site"] in sites: s += 2
        if r["asset_model"] and r["asset_model"] in models: s += 2
        if r["component"] in comps: s += 2
        if r["season"] in seasons: s += 1
        return s

    scored = [(score(r), r) for r in recs]
    best = [r for sc, r in scored if sc >= 4]
    if len(best) < n:
        best = [r for sc, r in scored if sc >= 3]
    if len(best) < n:
        best = [r for sc, r in scored if sc >= 2]
    return rng.sample(best, min(n, len(best))) if best else []


def installed_base_context(cand, assets, recs_by_id):
    """Deterministic installed-base breakdown for the equipment involved.

    Without this, Stage 4 can describe a cohort but cannot size it, and
    "population at risk" degrades into a guess. The counts here come from the
    asset registry, which includes units that have never generated a ticket.
    """
    from .stage1_extract import parse_serial
    from .stage2_cluster import _quarter
    models = {recs_by_id[w]["asset_model"] for w in cand["members"]
              if w in recs_by_id and recs_by_id[w].get("asset_model")}
    if not models:
        return None
    out = {}
    for m in models:
        buckets, wk = {}, {}
        for a in assets.values():
            if a["model"] != m:
                continue
            ser = parse_serial(a["asset_id"])
            if not ser:
                continue
            buckets[_quarter(ser["mfg_yy"], ser["mfg_ww"])] = \
                buckets.get(_quarter(ser["mfg_yy"], ser["mfg_ww"]), 0) + 1
            if ser["mfg_yy"] == 24:
                wk[ser["mfg_ww"]] = wk.get(ser["mfg_ww"], 0) + 1
        out[m] = {"total_installed": sum(buckets.values()),
                  "by_manufacture_quarter": dict(sorted(buckets.items())),
                  "units_by_2024_manufacture_week": dict(sorted(wk.items()))}
    return out


def build_prompt(cand, hypotheses, recs, recs_by_id, wo_by_id, assets=None, max_members=22):
    def row(r):
        w = wo_by_id[r["wo_id"]]
        return {"wo_id": r["wo_id"], "date": str(r["date"]), "site": r["site"],
                "asset_id": r["asset_id"], "wo_type": r["wo_type"],
                "priority": r["priority"], "tech": r["tech"],
                "labor_hours": r["labor_hours"], "parts_used": r["parts_used"],
                "resolution_code": r["resolution_code"],
                "extracted": {"symptom": r["symptom"], "component": r["component"],
                              "environment": r["environment"], "action": r["action"],
                              "outcome": r["outcome"], "benefit_pct": r["benefit"]},
                "narrative": w["narrative"]}

    mem = [recs_by_id[w] for w in cand["members"] if w in recs_by_id]
    mem.sort(key=lambda r: r["date"])
    if len(mem) > max_members:
        step = len(mem) / max_members
        mem = [mem[int(i * step)] for i in range(max_members)]
    ctl = matched_controls(cand, recs, recs_by_id)
    profile = {k: v for k, v in cand.items() if not k.startswith("_") and k != "members"}
    user = json.dumps({
        "candidate": profile,
        "hypotheses": hypotheses.get("hypotheses", []),
        "cluster_members": [row(r) for r in mem],
        "matched_controls_not_in_cluster": [row(r) for r in ctl],
        "installed_base": installed_base_context(cand, assets, recs_by_id) if assets else None,
    }, ensure_ascii=False, indent=1)
    return cand["candidate_id"], SYSTEM, user
