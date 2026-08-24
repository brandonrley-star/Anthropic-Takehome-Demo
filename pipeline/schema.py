"""
Controlled vocabularies for Stage 1 extraction.

Closed vocabularies matter here. If the model free-texts the symptom, Stage 2
cannot group on it and the whole pipeline degrades into string matching. The
model picks from these lists or returns "other" with a free-text note.
"""

SYMPTOM = [
    "overtemperature_trip", "thermal_derate", "cooling_airflow_low",
    "component_thermal_damage", "contactor_welded",
    "ground_fault", "overcurrent_trip", "undervoltage_trip",
    "grid_ride_through", "failure_to_start", "hard_fault",
    "comms_loss", "scada_data_gap", "reporting_dropout",
    "string_underperformance", "open_string", "blown_fuse",
    "physical_damage", "water_ingress", "corrosion_or_wear",
    "tracker_misalignment", "tracker_stall", "tracker_mechanical_damage",
    "drive_grease_degradation",
    "soiling", "vegetation_growth", "wildlife_intrusion", "theft_or_vandalism",
    "module_glass_damage", "module_cosmetic_change", "hot_cells",
    "no_fault_found", "routine_inspection", "routine_service", "other",
]

COMPONENT = [
    "central_inverter", "string_inverter", "igbt_module", "dc_contactor",
    "ac_contactor", "gate_driver", "cooling_fan", "air_filter", "capacitor",
    "control_board", "combiner", "fuse", "conductor_or_connector",
    "tracker_drive", "tracker_motor", "tracker_controller", "tracker_structure",
    "module", "mv_equipment", "transformer", "scada_or_comms",
    "met_station", "bess", "site_infrastructure", "none", "other",
]

ENVIRONMENT = [
    "high_ambient_heat", "cold_or_freezing", "snow_or_ice", "high_wind",
    "storm_or_lightning", "rain_or_wet", "high_humidity", "dust_or_soiling",
    "none_mentioned",
]

ACTION = [
    "reset_or_restart", "part_replaced", "cleaned_or_serviced", "adjusted_or_recalibrated",
    "inspected_only", "repaired_in_place", "escalated_or_referred",
    "software_or_firmware_change", "no_action", "other",
]

# The field that makes efficacy-decay findings representable at all.
OUTCOME = [
    "resolved",            # fixed, no expectation of recurrence
    "partial_improvement", # helped, but not fully
    "no_change",           # action taken, no measurable benefit
    "recurring",           # explicitly not the first time
    "pending",             # escalated / awaiting parts / open
    "not_applicable",      # inspection or routine work with nothing to fix
]

EXTRACTION_FIELDS = [
    "symptom", "component", "environment", "action", "outcome",
    "quantified_benefit_pct", "uncertainty_expressed", "recurrence_language",
    "notes",
]


def blank():
    return {"symptom": "other", "component": "other", "environment": ["none_mentioned"],
            "action": "other", "outcome": "not_applicable",
            "quantified_benefit_pct": None, "uncertainty_expressed": False,
            "recurrence_language": False, "notes": ""}


def validate(rec):
    """Coerce a model response into the closed vocabulary. Returns (rec, problems)."""
    problems = []
    out = blank()
    out.update({k: v for k, v in (rec or {}).items() if k in EXTRACTION_FIELDS})
    if out["symptom"] not in SYMPTOM:
        problems.append(f"symptom={out['symptom']!r}"); out["symptom"] = "other"
    if out["component"] not in COMPONENT:
        problems.append(f"component={out['component']!r}"); out["component"] = "other"
    env = out["environment"]
    if isinstance(env, str):
        env = [env]
    env = [e for e in (env or []) if e in ENVIRONMENT] or ["none_mentioned"]
    out["environment"] = env
    if out["action"] not in ACTION:
        problems.append(f"action={out['action']!r}"); out["action"] = "other"
    if out["outcome"] not in OUTCOME:
        problems.append(f"outcome={out['outcome']!r}"); out["outcome"] = "not_applicable"
    q = out["quantified_benefit_pct"]
    if q is not None:
        try:
            out["quantified_benefit_pct"] = float(q)
        except (TypeError, ValueError):
            problems.append(f"benefit={q!r}"); out["quantified_benefit_pct"] = None
    out["uncertainty_expressed"] = bool(out["uncertainty_expressed"])
    out["recurrence_language"] = bool(out["recurrence_language"])
    return out, problems
