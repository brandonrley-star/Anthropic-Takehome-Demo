"""
Stage 3 — competing explanations.

One call per candidate. The model must produce SEVERAL explanations including
at least one benign one. A pipeline that asks "what is the defect here?" will
find a defect in noise; asking "what are the candidate explanations, and what
would tell them apart?" is what makes Stage 4 able to decline.
"""
import json, random

def cache_key(cand):
    """Stable identity for caching and authored responses.

    NOT candidate_id: that is assigned by materiality rank, so CAND-005 means a
    different cluster in every run. Keying on it let a cached response from one
    run be served for an unrelated cluster in the next — the authored demo run
    silently returned live verdicts attached to the wrong findings.

    kind|key is content-derived and survives re-ranking, re-budgeting and new
    generators appearing above a cluster in the ordering.
    """
    return f"{cand['kind']}|{cand['key']}"


SYSTEM = """You are a reliability engineer reviewing candidate patterns from a \
utility-scale solar O&M work-order corpus.

You are given an aggregate statistical profile of a candidate cluster plus a \
sample of the underlying field narratives.

Produce COMPETING explanations. Return ONE JSON object:

{"hypotheses":[{"id":"H1",
                "statement":"one sentence, specific and falsifiable",
                "type":"systemic_defect|benign_operational|data_artifact|environmental_event|normal_wear_and_tear|reporting_culture|other",
                "prior":"high|medium|low",
                "predictions":["if this is true, what else must be visible in the data"],
                "discriminating_evidence":["what observation would separate this from the others"]}]}

Requirements:
- Between 2 and 4 hypotheses.
- AT LEAST ONE must be benign: a discrete weather event, a reporting or logging \
artifact, expected end-of-life wear, a population-size effect, or coincidence.
- Do not assume the cluster is real. "This is ordinary variation given the \
installed base" is a legitimate hypothesis and should be offered when the \
normalised rate is unremarkable.
- Predictions must be checkable against work-order data, not against outside \
knowledge."""


def sample_members(cand, recs_by_id, n=14, seed=7):
    rng = random.Random(seed + len(cand["members"]))
    mem = [recs_by_id[w] for w in cand["members"] if w in recs_by_id]
    mem.sort(key=lambda r: r["date"])
    if len(mem) <= n:
        return mem
    # keep the ends of the time range plus a spread through the middle
    keep = [mem[0], mem[-1]]
    mid = mem[1:-1]
    keep += rng.sample(mid, min(n - 2, len(mid)))
    return sorted(keep, key=lambda r: r["date"])


def build_prompt(cand, recs_by_id, wo_by_id):
    profile = {k: v for k, v in cand.items()
               if not k.startswith("_") and k != "members"}
    profile["member_count"] = cand["n"]
    profile["labor_hours_total"] = cand.get("_labor_hours")
    profile["lost_mwh_reported_total"] = cand.get("_lost_mwh")
    sample = []
    for r in sample_members(cand, recs_by_id):
        w = wo_by_id[r["wo_id"]]
        sample.append({"wo_id": r["wo_id"], "date": str(r["date"]),
                       "site": r["site"], "asset_id": r["asset_id"],
                       "wo_type": r["wo_type"], "priority": r["priority"],
                       "tech": r["tech"], "labor_hours": r["labor_hours"],
                       "parts_used": r["parts_used"],
                       "resolution_code": r["resolution_code"],
                       "extracted": {"symptom": r["symptom"], "component": r["component"],
                                     "environment": r["environment"], "action": r["action"],
                                     "outcome": r["outcome"], "benefit_pct": r["benefit"],
                                     "uncertain": r["uncertain"],
                                     "recurrence": r["recurrence"]},
                       "narrative": w["narrative"]})
    user = json.dumps({"candidate": profile, "sample_narratives": sample},
                      ensure_ascii=False, indent=1)
    return cache_key(cand), SYSTEM, user
