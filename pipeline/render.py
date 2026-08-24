"""
Findings rendering.

The audience is a VP of Asset Management, not an engineering review. Every
escalated finding leads with what it costs, how much is exposed, what to do and
what that is worth. Technical evidence sits underneath as support. A finding
that reads as a diagnostic report is wrong for this audience.

Two rules that matter commercially and are easy to get wrong:

  1. Exposure is not additive. Three clusters that are three severity stages of
     the same cohort fault describe ONE population. Summing their replacement
     exposure would inflate the number three-fold in front of a customer. The
     portfolio summary counts each shared population once, using the
     population_shared_with links the verification stage emits.

  2. Realised cost IS additive: every work order belongs to exactly one cluster
     member list, and the cost model charges labour, mobilisation and parts per
     work order. Where clusters share work orders the summary de-duplicates on
     wo_id before costing.
"""
from . import cost_model as cm

BAR = "=" * 78
SUB = "-" * 78

_PART_LABEL = {
    "igbt_module": "IGBT module", "dc_contactor": "DC contactor",
    "gate_driver": "gate driver", "cooling_fan": "cooling fan",
    "capacitor": "capacitor", "control_board": "control board",
    "tracker_motor": "tracker motor", "gearbox": "gearbox",
    "module": "PV module", "combiner_fuse": "combiner fuse",
}


def _money(n):
    return f"${n:,.0f}"


def _parts_phrase(detail):
    if not detail:
        return ""
    bits = []
    for k, v in sorted(detail.items(), key=lambda kv: -kv[1]):
        if k == "unknown":
            continue
        bits.append(f"{v}x {_PART_LABEL.get(k, k.replace('_', ' '))}")
    return ", ".join(bits)


def finance(cand, verdict, wo_by_id):
    mem = [wo_by_id[w] for w in cand["members"] if w in wo_by_id]
    realised = cm.realised_cost(mem)
    pop = (verdict.get("population_at_risk") or {}).get("count") or 0
    in_warranty = sum(1 for w in mem
                      if (w.get("_warranty_active") is True))
    rec = cm.warranty_recovery(realised, in_warranty, len(mem)) if mem else 0
    return {
        "realised": realised,
        "population_at_risk": pop,
        "replacement_exposure_usd": cm.exposure_value(pop) if pop else 0,
        "warranty_recoverable_usd": rec,
        "in_warranty_members": in_warranty,
    }


def portfolio(results, wo_by_id):
    """De-duplicated commercial totals across escalated findings.

    Work orders are de-duplicated by wo_id before costing. Populations are
    de-duplicated by the shared-population groups the verification stage
    declares, taking the largest count in each group.
    """
    esc = [r for r in results.values() if r["verdict"]["verdict"] == "escalate"]
    wo_ids, groups = set(), []
    for r in esc:
        wo_ids.update(r["candidate"]["members"])
        cid = r["candidate"]["candidate_id"]
        linked = set(r["verdict"].get("population_shared_with") or []) | {cid}
        for g in groups:
            if g["ids"] & linked:
                g["ids"] |= linked
                g["pop"] = max(g["pop"], r["finance"]["population_at_risk"])
                g["warranty"] += r["finance"]["warranty_recoverable_usd"]
                break
        else:
            groups.append({"ids": set(linked),
                           "pop": r["finance"]["population_at_risk"],
                           "warranty": r["finance"]["warranty_recoverable_usd"]})
    mem = [wo_by_id[w] for w in sorted(wo_ids) if w in wo_by_id]
    realised = cm.realised_cost(mem) if mem else None
    pop = sum(g["pop"] for g in groups)
    return {
        "findings": len(esc),
        "populations": len(groups),
        "work_orders": len(mem),
        "realised": realised,
        "population_at_risk": pop,
        "replacement_exposure_usd": cm.exposure_value(pop) if pop else 0,
        "warranty_recoverable_usd": sum(g["warranty"] for g in groups),
    }


def render_portfolio(p):
    if not p["findings"]:
        return ""
    r = p["realised"]
    lines = [BAR, "COMMERCIAL SUMMARY — ESCALATED FINDINGS", BAR]
    lines.append(f"  {'Findings':<28}{p['findings']} across {p['populations']} distinct "
                 f"at-risk population(s)")
    lines.append(f"  {'Cost already incurred':<28}{_money(r['total_low_usd'])} – "
                 f"{_money(r['total_high_usd'])}   ({p['work_orders']} work orders)")
    lines.append(f"  {'Assets exposed':<28}{p['population_at_risk']} units not yet failed")
    lines.append(f"  {'Replacement exposure':<28}{_money(p['replacement_exposure_usd'])} "
                 f"if left unremediated")
    lines.append(f"  {'Warranty recovery in play':<28}{_money(p['warranty_recoverable_usd'])}")
    lines.append("")
    lines.append("  Exposure is counted ONCE per physical population. Findings that are")
    lines.append("  severity stages of the same fault share one population and are not summed.")
    return "\n".join(lines)


def render_finding(i, cand, verdict, fin, hypotheses, exposure_owner=None):
    r = fin["realised"]
    kind = verdict["verdict"].upper()
    lines = [SUB]
    lines.append(f"{kind} #{i} — {verdict.get('business_headline','(no headline)')}")
    lines.append(SUB)
    lines.append(f"  {'Cost incurred to date':<26}{_money(r['total_low_usd'])} – {_money(r['total_high_usd'])}"
                 f"   ({cand['n']} work orders, {r['labor_hours']:.0f} labour hours)")
    if fin["population_at_risk"] and not exposure_owner:
        lines.append(f"  {'Assets exposed':<26}{fin['population_at_risk']} units not yet failed")
        lines.append(f"  {'Replacement exposure':<26}{_money(fin['replacement_exposure_usd'])} if unremediated")
    elif exposure_owner:
        lines.append(f"  {'Assets exposed':<26}same {fin['population_at_risk']} units as "
                     f"{exposure_owner} — already counted there, not additional")
    if fin["warranty_recoverable_usd"]:
        lines.append(f"  {'Warranty recovery':<26}{_money(fin['warranty_recoverable_usd'])} potentially recoverable"
                     f" ({fin['in_warranty_members']} of {cand['n']} in warranty)")
    lines.append(f"  {'Recommended action':<26}{verdict.get('recommended_action','—')}")
    lines.append(f"  {'Action type':<26}{verdict.get('action_type','—')}")
    lines.append(f"  {'Confidence':<26}{verdict.get('confidence','—')}")
    shared = verdict.get("population_shared_with") or []
    if shared and not exposure_owner:
        lines.append(f"  {'Shared population':<26}also presents as {', '.join(shared)}"
                     f"; exposure above covers all three")
    if kind == "DEPRIORITIZE":
        annual = r["total_high_usd"] / 2.0        # 24-month observation window
        rec = (f"{_money(fin['warranty_recoverable_usd'])} of warranty recovery"
               if fin["warranty_recoverable_usd"] else "no warranty recovery")
        exp = (f"{fin['population_at_risk']} units at risk"
               if fin["population_at_risk"] else "no quantified population at risk")
        lines.append(f"  {'Why not escalated':<26}~{_money(annual)}/yr run-rate across the fleet,"
                     f" {rec},")
        lines.append(f"  {'':<26}{exp}. Below the threshold that justifies a")
        lines.append(f"  {'':<26}customer conversation or a supplier claim.")
    lines.append(SUB)
    lines.append("EVIDENCE")
    for para in (verdict.get("reasoning") or "").split("\n"):
        lines.append(f"  {para}")
    sup = verdict.get("supporting_wo_ids") or []
    lines.append(f"  Cited from the {cand['n']}-ticket cluster ({len(sup)} shown): "
                 + ", ".join(sup[:8]) + (" …" if len(sup) > 8 else ""))
    lines.append(f"  Contradicting evidence: {verdict.get('contradicting_evidence','—')}")
    hs = hypotheses.get("hypotheses", [])
    if hs:
        sel = verdict.get("selected_hypothesis")
        lines.append(f"  Hypotheses considered ({len(hs)}):")
        for h in hs:
            mark = ">>" if h.get("id") == sel else "  "
            lines.append(f"    {mark} {h.get('id')} [{h.get('type')}] {h.get('statement')}")
    pa = verdict.get("population_at_risk") or {}
    if pa.get("basis"):
        lines.append(f"  Population basis: {pa.get('basis')}")
    lines.append(SUB)
    lines.append("COST BASIS (all figures from stated assumptions, not model output)")
    lines.append(f"  labour        {r['labor_hours']:>8.1f} h   x ${cm.value('loaded_labor_rate_usd_per_hour'):.0f}/h"
                 f"          = {_money(r['labor_usd'])}")
    lines.append(f"  mobilisation  {r['truck_rolls']:>8d} rolls x ${cm.value('truck_roll_usd'):.0f}"
                 f"          = {_money(r['mobilisation_usd'])}")
    if r["parts_usd"]:
        ph = _parts_phrase(r["parts_detail"])
        if len(ph) <= 32:
            lines.append(f"  parts         {ph:<32}= {_money(r['parts_usd'])}")
        else:
            lines.append(f"  parts         {'':<32}= {_money(r['parts_usd'])}")
            lines.append(f"                {ph}")
    lines.append(f"  energy        {r['lost_mwh_reported']:>8.1f} MWh x ${cm.value('energy_value_usd_per_mwh'):.0f}/MWh"
                 f"       = {_money(r['energy_usd_reported'])}  (as reported)")
    lines.append(f"                upper bound {_money(r['energy_usd_extrapolated'])} — only "
                 f"{cm.value('lost_production_reporting_rate'):.0%} of tickets record lost production")
    return "\n".join(lines)


def render_declined(i, cand, verdict, hypotheses):
    lines = [SUB]
    lines.append(f"DECLINED #{i} — {verdict.get('business_headline') or cand['label']}")
    lines.append(f"  Candidate {cand['candidate_id']}  |  {cand['n']} work orders  |  "
                 f"confidence {verdict.get('confidence','—')}")
    sel = verdict.get("selected_hypothesis")
    for h in hypotheses.get("hypotheses", []):
        if h.get("id") == sel:
            lines.append(f"  Accepted explanation: [{h.get('type')}] {h.get('statement')}")
    lines.append(f"  Why not escalated: {verdict.get('reasoning','—')}")
    if verdict.get("recommended_action") and verdict.get("action_type") != "none":
        lines.append(f"  Residual action: {verdict['recommended_action']} ({verdict.get('action_type')})")
    return "\n".join(lines)


def render_report(results, wo_by_id, accounting, extraction_quality, meta):
    esc, dep, dec = [], [], []
    for cid, r in results.items():
        v = r["verdict"]
        (esc if v["verdict"] == "escalate" else
         dep if v["verdict"] == "deprioritize" else dec).append(r)
    for bucket in (esc, dep):
        bucket.sort(key=lambda r: -r["finance"]["realised"]["total_high_usd"])

    out = [BAR, "NORTHLIGHT RENEWABLE SERVICES — FLEET PATTERN DETECTION", BAR,
           f"  corpus            {meta['work_orders']} work orders, {meta['sites']} sites, "
           f"{meta['window']}",
           f"  stage 1 backend   {meta['stage1_backend']}"
           + ("   (deterministic stand-in, not a model)" if meta['stage1_backend'] == 'rules' else ""),
           f"  reasoning backend {meta['reasoning_backend']}  model {meta['model']}",
           f"  candidates        {meta['candidates_total']} generated, {meta['candidates_examined']} examined",
           f"  outcome           {len(esc)} escalated | {len(dep)} real but deprioritised | {len(dec)} examined and declined",
           ""]

    port = portfolio(results, wo_by_id)
    if port["findings"]:
        out.append(render_portfolio(port))
        out.append("")

    out.append(BAR)
    out.append(f"ESCALATED — {len(esc)} finding(s), ranked by financial impact")
    out.append(BAR)
    if not esc:
        out.append("  (none)")
    owner = {}          # candidate_id -> label of the finding that carries its exposure
    seen = {}           # frozenset(group ids) -> label
    for i, r in enumerate(esc, 1):
        cid = r["candidate"]["candidate_id"]
        grp = frozenset(set(r["verdict"].get("population_shared_with") or []) | {cid})
        for g, lab in seen.items():
            if g & grp:
                owner[cid] = lab
                break
        else:
            seen[grp] = f"ESCALATE #{i}"
    for i, r in enumerate(esc, 1):
        out.append(render_finding(i, r["candidate"], r["verdict"], r["finance"],
                                  r["hypotheses"],
                                  owner.get(r["candidate"]["candidate_id"])))
        out.append("")

    out.append(BAR)
    out.append(f"REAL BUT DEPRIORITISED — {len(dep)} finding(s)")
    out.append("Confirmed as real. Not worth commercial action at the estimated impact below.")
    out.append(BAR)
    if not dep:
        out.append("  (none)")
    for i, r in enumerate(dep, 1):
        out.append(render_finding(i, r["candidate"], r["verdict"], r["finance"], r["hypotheses"]))
        out.append("")

    out.append(BAR)
    out.append(f"EXAMINED AND DECLINED — {len(dec)} candidate(s)")
    out.append("A system that visibly refuses to escalate is more useful than one that only shows hits.")
    out.append(BAR)
    if not dec:
        out.append("  (none)")
    for i, r in enumerate(dec, 1):
        out.append(render_declined(i, r["candidate"], r["verdict"], r["hypotheses"]))
        out.append("")

    out.append(BAR)
    out.append("EXTRACTION QUALITY — what gates finding quality upstream")
    out.append(BAR)
    out.append(f"  symptom unclassified          {extraction_quality['symptom_unclassified']}"
               f" of {extraction_quality['work_orders']} ({extraction_quality['symptom_unclassified_pct']}%)")
    out.append(f"  outcome no_change/recurring   {extraction_quality['outcome_no_change_or_recurring']}"
               f"   (the signal efficacy-decay detection depends on)")
    out.append("")

    out.append(BAR)
    out.append("COST AND TIME")
    out.append(BAR)
    out.append(accounting.render())
    out.append("")
    out.append(cm.render_assumptions())
    return "\n".join(out)
