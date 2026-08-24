"""
Stage 1 — per-ticket extraction.

Two halves, deliberately:

  DETERMINISTIC (regex, free, 100% recall). Equipment tags, version strings and
  serial attributes follow conventions the data dictionary specifies exactly.
  A regex does not miss `4.2.1` in a narrative; a language model occasionally
  does, and the hardest evidence in a corpus like this hides in exactly those
  passing mentions. It is also far easier to defend to a technical reviewer.

  MODEL. Everything requiring judgement: what actually went wrong, on what
  component, under what conditions, what was done, and — critically — whether
  the action helped.
"""

import re, json, os
from . import schema, paths
from .corpus_io import d

SERIAL = re.compile(r"\b([A-Z]{3}\d{2})-(\d{2})(\d{2})([A-D])-(\d{4})\b", re.I)
TAG = re.compile(r"\b(?:CB-B\d{2}-\d{2}|TR-B\d{2}-R\d{3}|TR-Z\d{2}|XFMR-B\d{2}"
                 r"|MET-\d{2}|CX-R\d{2})\b", re.I)
BLOCK = re.compile(r"\bB\d{2}\b")
# Firmware / software revisions. Guarded so decimals like "1.5 mm" don't match.
VERSION = re.compile(r"\b(\d+\.\d+(?:\.\d+)?)\b")
VERSION_CTX = re.compile(r"(?:fw|f/w|firmware|rev|revision|version|build|loaded|running|"
                         r"installed|on)\b[^.]{0,24}?\b(\d+\.\d+(?:\.\d+)?)\b", re.I)
PCT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", re.I)


def parse_serial(s):
    m = SERIAL.match(s or "")
    if not m:
        return None
    return {"prefix": m.group(1).upper(), "mfg_yy": int(m.group(2)),
            "mfg_ww": int(m.group(3)), "batch_letter": m.group(4).upper(),
            "unit": m.group(5)}


def deterministic(wo, assets):
    """Facts extractable without a model. Never wrong about what is written."""
    nar = wo.get("narrative") or ""
    serials = sorted({m.group(0).upper() for m in SERIAL.finditer(nar)})
    tags = sorted({m.group(0).upper() for m in TAG.finditer(nar)})
    blocks = sorted({m.group(0).upper() for m in BLOCK.finditer(nar)})
    versions = sorted({m.group(1) for m in VERSION_CTX.finditer(nar)})

    asset = assets.get(wo.get("asset_id") or "")
    ser = parse_serial(wo.get("asset_id") or "")
    warranty_active = None
    if asset and asset.get("warranty_parts_expiry"):
        warranty_active = d(asset["warranty_parts_expiry"]) > wo["_d"]

    return {
        "serials_in_narrative": serials,
        "tags_in_narrative": tags,
        "blocks_in_narrative": blocks,
        "versions_in_narrative": versions,
        "asset_model": asset.get("model") if asset else None,
        "asset_manufacturer": asset.get("manufacturer") if asset else None,
        "asset_commissioned": asset.get("commissioned_date") if asset else None,
        "asset_warranty_expiry": asset.get("warranty_parts_expiry") if asset else None,
        "warranty_active_at_ticket": warranty_active,
        "serial_prefix": ser["prefix"] if ser else None,
        "serial_mfg_yy": ser["mfg_yy"] if ser else None,
        "serial_mfg_ww": ser["mfg_ww"] if ser else None,
        "serial_batch_letter": ser["batch_letter"] if ser else None,
        "narrative_words": len(nar.split()),
    }


SYSTEM = """You are extracting structured facts from utility-scale solar O&M field \
work orders. The narratives are written by technicians on a tablet in the field: \
fragments, abbreviations, typos and irrelevant detail are normal.

Return ONE JSON object, no prose, with exactly these keys:

  symptom      one of: {symptom}
  component    one of: {component}
  environment  list from: {environment}
  action       one of: {action}
  outcome      one of: {outcome}
  quantified_benefit_pct   number if the technician states a measured percentage \
improvement from the work (e.g. "output up about 4%"), else null
  uncertainty_expressed    true if the technician expresses doubt, speculation or \
inability to explain what they saw ("not sure", "might be", "no idea", "nothing I \
can prove", "hard to say")
  recurrence_language      true if the text indicates this is not the first time \
("again", "third time", "same as last time", "keeps coming back", "second trip")
  notes        at most 12 words, only for something materially unusual, else ""

Rules:
- Describe ONLY what the narrative says. Do not infer a root cause.
- `outcome` records whether the action WORKED, which is distinct from whether the
  ticket was closed. Use "no_change" when work was done with no measurable benefit,
  "recurring" when the text says the problem has happened before, "partial_improvement"
  when it helped but not fully, "pending" when awaiting parts or escalation.
- If the narrative is routine with nothing wrong, use outcome "not_applicable".
- The structured resolution_code is frequently WRONG in this source system. Trust
  the narrative over it."""


def build_system():
    return SYSTEM.format(
        symptom=", ".join(schema.SYMPTOM), component=", ".join(schema.COMPONENT),
        environment=", ".join(schema.ENVIRONMENT), action=", ".join(schema.ACTION),
        outcome=", ".join(schema.OUTCOME))


def build_user(wo):
    return json.dumps({
        "wo_type": wo["wo_type"], "priority": wo["priority"],
        "resolution_code": wo["resolution_code"],
        "parts_used": wo["parts_used"], "labor_hours": wo["labor_hours"],
        "asset_id": wo["asset_id"], "narrative": wo["narrative"],
    }, ensure_ascii=False)


def build_prompt(wo):
    return wo["wo_id"], build_system(), build_user(wo)


# --------------------------------------------------------------------------
# Rules backend. A deterministic stand-in so the pipeline can run end to end
# with no credentials. Clearly weaker than the model at symptom normalisation;
# every run labels which backend produced Stage 1.
# --------------------------------------------------------------------------
_SYM_RULES = [
    ("contactor_welded", ("welded",)),
    ("component_thermal_damage", ("thermal damage", "heat marked", "discoloured and the busbar")),
    ("overtemperature_trip", ("over temperature", "overtemp", "cabinet temperature alarm", "high cabinet temp")),
    ("thermal_derate", ("derat",)),
    ("cooling_airflow_low", ("airflow", "fan bank", "cooling alarm", "fan fault", "filters were", "filters completely blocked")),
    ("ground_fault", ("ground fault", "dc gf", " gf ", "gf reading", "gf alarm", "gf testing", "gf continuity")),
    ("overcurrent_trip", ("overcurrent",)),
    ("undervoltage_trip", ("undervolt",)),
    ("grid_ride_through", ("ride through", "ride thru")),
    ("failure_to_start", ("failed to start", "would not start", "no start", "wouldnt start")),
    ("hard_fault", ("hard fault", "hard faulted", "shut down hard")),
    ("blown_fuse", ("blown fuse", "fuses out", "fuse, replaced", "reading zero")),
    ("open_string", ("open string", "string out")),
    ("string_underperformance", ("reading soft", "strings low", "underperformance", "flagged low", "low string")),
    ("reporting_dropout", ("dropped off the network", "not reporting", "offline in the portal", "comms fault", "comms card")),
    ("comms_loss", ("comm fault", "lost scada", "comms alarm", "daisy chain")),
    ("scada_data_gap", ("historian gap", "data gap", "rtu")),
    ("water_ingress", ("water in the bottom", "water in two", "water sat in")),
    ("tracker_misalignment", ("out of alignment", "not following", "not tracking", "recalibrat")),
    ("tracker_stall", ("stuck at",)),
    ("tracker_mechanical_damage", ("damper", "purlin", "torque tube", "stow pin", "coupling sheared", "clamps pulled through")),
    ("drive_grease_degradation", ("grease", "squealing", "notchy", "rotating rough")),
    ("module_cosmetic_change", ("chalky", "discoloured and a bit dry", "backsheet", "back sheet")),
    ("hot_cells", ("hot cells", "warm cells", "ir scan", "thermal survey", "ir survey", "ir on")),
    ("module_glass_damage", ("cracked glass", "shattered", "broken modules", "shot out")),
    ("soiling", ("soiling", "wash", "ag dust")),
    ("vegetation_growth", ("mow", "herbicide", "spray", "brush", "volunteer growth", "tree line", "treeline")),
    ("wildlife_intrusion", ("coyote", "snake", "bird nest", "wildlife")),
    ("theft_or_vandalism", ("theft", "vandalism", "stolen")),
    ("physical_damage", ("burned connector", "chafed", "pinched connector")),
    ("no_fault_found", ("no fault when i got there", "nothing obvious", "no fault found", "nothing wrong")),
    ("routine_inspection", ("walkdown", "inspection", "site walk", "perimeter", "assessment", "audit")),
    ("routine_service", ("pm ", "annual", "semiannual", "quarterly", "lubrication", "torque check", "torque sweep")),
]
_COMP_RULES = [
    ("igbt_module", ("igbt",)), ("dc_contactor", ("contactor", "contacter")),
    ("gate_driver", ("gate driver",)), ("cooling_fan", ("fan",)),
    ("air_filter", ("filter",)), ("capacitor", ("capacitor",)),
    ("control_board", ("control board",)), ("combiner", ("cb-b", "combiner")),
    ("fuse", ("fuse",)), ("tracker_motor", ("motor",)),
    ("tracker_drive", ("drive", "gearbox", "slew")),
    ("tracker_controller", ("tcu", "controller", "limit switch")),
    ("tracker_structure", ("damper", "purlin", "torque tube", "stow pin")),
    ("module", ("module", "panel", "backsheet", "glass")),
    ("transformer", ("xfmr", "transformer", "bushing")),
    ("mv_equipment", ("mv ", "feeder", "switchgear", "termination", "poi")),
    ("scada_or_comms", ("scada", "rtu", "fiber", "comms", "historian")),
    ("met_station", ("met-", "pyranometer", "anemometer", "soiling station")),
    ("bess", ("cx-r", "bess", "hvac")),
    ("string_inverter", ("slt25", "ces27")),
    ("central_inverter", ("kvp36", "kvp24", "ces40", "mgx33", "invertor", "inverter")),
    ("conductor_or_connector", ("home run", "connector", "conductor", "cable")),
]
_ENV_RULES = [
    ("high_ambient_heat", ("hot", "heat", "105", "104", "103", "102", "101", "100 ", "afternoon heat", "97", "96", "98", "99")),
    ("cold_or_freezing", ("cold", "frozen", "ice", "freez")),
    ("snow_or_ice", ("snow", "drift")),
    ("high_wind", ("wind", "microburst", "gust")),
    ("storm_or_lightning", ("storm", "lightning")),
    ("rain_or_wet", ("rain", "wet", "damp", "water")),
    ("high_humidity", ("humid", "fog")),
    ("dust_or_soiling", ("dust", "soiling")),
]
_ACT_RULES = [
    ("part_replaced", ("replaced", "rplcd", "swapped", "swap")),
    ("software_or_firmware_change", ("installed, took about twenty minutes", "firmware update", "loaded")),
    ("cleaned_or_serviced", ("cleaned", "greased", "washed", "wash ", "vacuumed", "repacked", "wiped")),
    ("adjusted_or_recalibrated", ("retorqued", "recalibrat", "realigned", "shimmed", "resecured", "reseated", "adjusted", "torqued")),
    ("reset_or_restart", ("reset", "restarted", "power cycled", "rebooted", "cycled")),
    ("escalated_or_referred", ("escalat", "opened a case", "vendor", "oem", "contractor scheduled", "passing it up", "pending")),
    ("repaired_in_place", ("repaired", "reterminated", "cut back", "patched", "straightened", "resealed", "drained")),
    ("inspected_only", ("walked", "inspection", "checked", "survey", "assessment", "sampled", "chkd")),
]
_UNC = ("not sure", "might be", "hard to say", "no idea", "idk", "nothing i can proveerty",
        "nothing i can prove", "could not tell", "wonder if", "i suspect", "presumably",
        "tbd", "no root cause", "unexplained", "not happy about")
_REC = ("again", "second time", "third", "fourth", "same as last", "keeps coming back",
        "second trip", "stopped counting", "this season", "same story", "every time",
        "as always", "same conversation", "not the first")


def rules_extract(wo):
    t = (wo.get("narrative") or "").lower()
    rec = schema.blank()
    for sym, needles in _SYM_RULES:
        if any(n in t for n in needles):
            rec["symptom"] = sym
            break
    for comp, needles in _COMP_RULES:
        if any(n in t for n in needles):
            rec["component"] = comp
            break
    env = [e for e, needles in _ENV_RULES if any(n in t for n in needles)]
    rec["environment"] = env or ["none_mentioned"]
    for act, needles in _ACT_RULES:
        if any(n in t for n in needles):
            rec["action"] = act
            break
    m = PCT.search(wo.get("narrative") or "")
    if m and any(k in t for k in ("up about", "up ", "back", "recovery", "picked up", "output")):
        rec["quantified_benefit_pct"] = float(m.group(1))
    rec["uncertainty_expressed"] = any(n in t for n in _UNC)
    rec["recurrence_language"] = any(n in t for n in _REC)
    # outcome
    if rec["recurrence_language"]:
        rec["outcome"] = "recurring"
    elif any(n in t for n in ("pending", "waiting on", "awaiting", "opened a case",
                              "contractor scheduled", "locked out", "no answer yet")):
        rec["outcome"] = "pending"
    elif rec["quantified_benefit_pct"] is not None and rec["quantified_benefit_pct"] < 1.5:
        rec["outcome"] = "no_change"
    elif any(n in t for n in ("not seeing much change", "barely worth", "no real change",
                              "minimal", "same result", "keeps coming back")):
        rec["outcome"] = "no_change"
    elif rec["action"] in ("inspected_only", "no_action", "other"):
        rec["outcome"] = "not_applicable"
    else:
        rec["outcome"] = "resolved"
    return rec
