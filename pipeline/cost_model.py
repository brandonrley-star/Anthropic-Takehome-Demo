"""
Financial assumptions, in one auditable place.

The model supplies QUANTITIES (how many units, hours, MWh, truck rolls).
This module supplies DOLLARS. No language model is ever asked to produce a
currency figure, because "the LLM estimated it" is not an answer to "where did
that number come from?".

Every constant below is an assumption. They are deliberately conservative and
are printed alongside any figure derived from them.
"""

ASSUMPTIONS = {
    "loaded_labor_rate_usd_per_hour": (
        95.0, "Fully loaded field technician cost including burden and vehicle."),
    "truck_roll_usd": (
        450.0, "Mobilisation cost for one site visit: travel, per-diem, scheduling "
               "overhead. Applied once per work order."),
    "energy_value_usd_per_mwh": (
        42.0, "Blended merchant + PPA value of lost generation. Deliberately mid-range; "
              "ERCOT summer peak is far higher and would raise every figure here."),
    "parts_cost_usd": ({
        "igbt_module": 8500.0,
        "dc_contactor": 2400.0,
        "gate_driver": 1900.0,
        "cooling_fan": 650.0,
        "capacitor": 1200.0,
        "control_board": 3100.0,
        "tracker_motor": 1450.0,
        "gearbox": 2200.0,
        "module": 210.0,
        "combiner_fuse": 45.0,
        "unknown": 0.0,
    }, "Replacement part cost by component class. 'unknown' is zero so that "
       "unclassified parts never inflate an estimate."),
    "inverter_replacement_usd": (
        62000.0, "Full central inverter replacement, installed. Used only for "
                 "population-at-risk exposure, never for realised cost."),
    "warranty_recovery_rate": (
        0.65, "Share of in-warranty parts and labour realistically recovered from an "
              "OEM claim, net of negotiation and administrative cost."),
    "lost_production_reporting_rate": (
        0.14, "Share of work orders carrying estimated_lost_production_mwh. The data "
              "dictionary states absence does not mean zero, so realised energy loss "
              "is extrapolated from this rate to produce a RANGE, never a point."),
}


def value(key):
    return ASSUMPTIONS[key][0]


def _parts_bucket(parts_text):
    t = (parts_text or "").lower()
    for needle, bucket in [
        ("igbt", "igbt_module"), ("dc contactor", "dc_contactor"),
        ("ac contactor", "dc_contactor"), ("contactor", "dc_contactor"),
        ("contacter", "dc_contactor"), ("gate driver", "gate_driver"),
        ("cooling fan", "cooling_fan"), ("fan", "cooling_fan"),
        ("capacitor", "capacitor"), ("control board", "control_board"),
        ("tracker motor", "tracker_motor"), ("motor", "tracker_motor"),
        ("gearbox", "gearbox"), ("module", "module"), ("fuse", "combiner_fuse"),
    ]:
        if needle in t:
            return bucket
    return "unknown"


def realised_cost(work_orders):
    """Cost already incurred on a set of work orders. Every term is observed in
    the corpus; nothing here is inferred."""
    hours = sum(w.get("labor_hours") or 0 for w in work_orders)
    rolls = len(work_orders)
    parts = 0.0
    parts_detail = {}
    for w in work_orders:
        b = _parts_bucket(w.get("parts_used"))
        if b == "unknown":
            continue
        qty = 1
        pu = (w.get("parts_used") or "").lower()
        for n in ("x2", "x3", "x4"):
            if n in pu:
                qty = int(n[1])
        c = value("parts_cost_usd")[b] * qty
        parts += c
        parts_detail[b] = parts_detail.get(b, 0) + qty
    mwh = sum(w.get("estimated_lost_production_mwh") or 0 for w in work_orders)

    labor = hours * value("loaded_labor_rate_usd_per_hour")
    mob = rolls * value("truck_roll_usd")
    energy_reported = mwh * value("energy_value_usd_per_mwh")
    # extrapolate the unreported share; presented as the top of a range
    rate = value("lost_production_reporting_rate")
    energy_upper = (mwh / rate) * value("energy_value_usd_per_mwh") if rate else energy_reported

    return {
        "labor_hours": round(hours, 1),
        "labor_usd": round(labor),
        "truck_rolls": rolls,
        "mobilisation_usd": round(mob),
        "parts_usd": round(parts),
        "parts_detail": parts_detail,
        "lost_mwh_reported": round(mwh, 1),
        "energy_usd_reported": round(energy_reported),
        "energy_usd_extrapolated": round(energy_upper),
        "total_low_usd": round(labor + mob + parts + energy_reported),
        "total_high_usd": round(labor + mob + parts + energy_upper),
    }


def exposure_value(n_units_at_risk):
    """Replacement exposure if an at-risk population is not remediated."""
    return round(n_units_at_risk * value("inverter_replacement_usd"))


def warranty_recovery(realised, n_in_warranty, n_total):
    """Recoverable share of realised parts+labour, scaled by how much of the
    affected population is inside its parts warranty."""
    if not n_total:
        return 0
    share = n_in_warranty / n_total
    base = realised["parts_usd"] + realised["labor_usd"]
    return round(base * share * value("warranty_recovery_rate"))


def render_assumptions():
    out = ["Financial assumptions (all figures below derive from these):"]
    for k, (v, why) in ASSUMPTIONS.items():
        if isinstance(v, dict):
            out.append(f"  {k}: {len(v)} component classes — {why}")
        else:
            out.append(f"  {k} = {v} — {why}")
    return "\n".join(out)
