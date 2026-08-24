import sys, json, collections
sys.path.insert(0, "/home/user/Anthropic-Takehome-Demo/eval/audit")
from _common import load
sys.path.insert(0, "/home/user/Anthropic-Takehome-Demo/generator")
import fleet, calendar_util as cal

sites, assets, techs, wos = load()
by_cls = collections.defaultdict(list)
for w in wos:
    by_cls[w["_cls"]].append(w)

defect = [a for a in assets if a["_defect_window"]]
site_of = {s["site_name"]: s for s in sites}
HOT = {"ERCOT_WEST", "ERCOT_SOUTH", "CAISO_CV", "CAISO_MOJAVE"}
failed = {w["asset_id"] for w in by_cls["signal_1"]}

def wo_ids(cls):
    return sorted(w["wo_id"] for w in by_cls[cls])

s1 = by_cls["signal_1"]
cost = sum(w["labor_hours"] for w in s1)
lost = sum(w["estimated_lost_production_mwh"] or 0 for w in s1)

gt = {
    "master_seed": 20260824,
    "corpus_version": "1.0.0",
    "total_work_orders": len(wos),
    "findings": {
        "signal_1_kelvara_thermal": {
            "kind": "TRUE SIGNAL (strong)",
            "summary": ("Kelvara KVP-3600 central inverters manufactured in weeks 18-36 "
                        "of 2024 shipped with cooling-fan controller firmware v4.2.1, which "
                        "ramps the fan bank too late under combined high ambient and high "
                        "irradiance. Result is progressive thermal stress on the IGBT modules "
                        "and, in advanced cases, DC contactor welding."),
            "work_order_ids": wo_ids("signal_1"),
            "n_work_orders": len(s1),
            "sites": sorted({w["site_name"] for w in s1}),
            "affected_units_with_failures": sorted(failed),
            "population": {
                "defect_window_units_fleetwide": len(defect),
                "at_hot_region_sites": sum(1 for a in defect if site_of[a["site_name"]]["region"] in HOT),
                "at_cool_region_sites": sum(1 for a in defect if site_of[a["site_name"]]["region"] not in HOT),
                "sites_holding_defect_units": sorted({a["site_name"] for a in defect}),
                "units_with_failure_history": len(failed),
                "at_risk_not_yet_failed": len(defect) - len(failed),
                "in_parts_warranty_at_window_end": sum(
                    1 for a in defect if a["warranty_parts_expiry"] > "2026-06-30"),
            },
            "firmware_mentions": sorted(w["wo_id"] for w in s1 if w.get("_fw")),
            "unescalated_speculation": sorted(w["wo_id"] for w in s1 if w.get("_speculation")),
            "advanced_stage_work_orders": sorted(w["wo_id"] for w in s1 if w["_stage"] == 3),
            "repeat_offender_units": {k: v for k, v in
                sorted(collections.Counter(w["asset_id"] for w in s1).items()) if v >= 2},
            "observed_cost": {
                "labor_hours_total": round(cost, 1),
                "lost_production_mwh_recorded": round(lost, 1),
                "note": "recorded lost production is a floor; the field is populated on a minority of tickets",
            },
        },
        "signal_2_caprock_backsheet": {
            "kind": "TRUE SIGNAL (weak)",
            "summary": ("Caprock Mesa (COD 2017, 180 MWdc, ERCOT West Texas) is losing output "
                        "to backsheet degradation on its Pinnacle Solar PS-500M modules, "
                        "concentrated in the older array sections. The site reads it as a "
                        "soiling and vegetation problem. No work order states a diagnosis."),
            "work_order_ids": wo_ids("signal_2"),
            "n_work_orders": len(by_cls["signal_2"]),
            "site": "Caprock Mesa",
            "evidence_threads": {
                "cleaning_benefit_decay": sorted(w["wo_id"] for w in by_cls["signal_2"] if w["_kind"] == "wash"),
                "scada_underperformance": sorted(w["wo_id"] for w in by_cls["signal_2"] if w["_kind"] == "scada"),
                "ir_scans_called_unremarkable": sorted(w["wo_id"] for w in by_cls["signal_2"] if w["_kind"] == "ir"),
                "backsheet_observations_closed_cosmetic": sorted(w["wo_id"] for w in by_cls["signal_2"] if w["_kind"] == "cosmetic"),
                "rising_ground_fault_readings": sorted(w["wo_id"] for w in by_cls["signal_2"] if w["_kind"] == "gf"),
            },
        },
        "decoy_1_sundowner_wind": {
            "kind": "DECOY - must NOT be called systemic",
            "summary": ("31 tracker work orders at Sundowner Mesa in a seven-week window in "
                        "spring 2025. Not an Auster Trackline H2 defect. Two benign causes are "
                        "stacked: a microburst on 2025-03-14, and TECH-0231 logging one work "
                        "order per tracker row where colleagues log one per zone."),
            "work_order_ids": wo_ids("decoy_1"),
            "event_date": "2025-03-14",
            "insurance_claim_ref": "NRS-PL-2025-0417",
            "narratives_naming_the_event": sorted(w["wo_id"] for w in by_cls["decoy_1"] if w.get("_names_event")),
            "per_row_tickets": sum(1 for w in by_cls["decoy_1"] if w["_mode"] == "per_row"),
            "per_zone_tickets": sum(1 for w in by_cls["decoy_1"] if w["_mode"] == "per_zone"),
            "tech_0231_per_row_work_outside_window": sorted(w["wo_id"] for w in wos if w.get("_habit")),
        },
        "decoy_2_normalization": {
            "kind": "DECOY - must NOT produce a false reliability ranking",
            "summary": ("Six sites came under contract partway through the window and ten "
                        "reached commercial operation after it opened. Ranking sites by raw "
                        "ticket count calls them the fleet's best assets. Blackfoot Draw is "
                        "the inverse: unremarkable on raw count, worst in the fleet per MW "
                        "per month of coverage."),
            "late_contract_sites": {s["site_name"]: s["om_contract_start"]
                                    for s in sites if s["om_contract_start"] > "2024-07-01"},
            "late_cod_sites": {s["site_name"]: s["commercial_operation_date"]
                               for s in sites if s["commercial_operation_date"] > "2024-07-01"},
            "inverted_trap_site": "Blackfoot Draw",
        },
        "distractor_slew_drive": {
            "kind": "REAL but commercially minor - must be deprioritised",
            "summary": "Auster Trackline H2 slew drive grease degradation on 2016-2019 vintage rows.",
            "work_order_ids": wo_ids("distractor_slew"),
            "sites": sorted({w["site_name"] for w in by_cls["distractor_slew"]}),
        },
        "distractor_comms": {
            "kind": "REAL but commercially minor - must be deprioritised",
            "summary": ("Soltera ST-250 comms-module dropouts at humid sites. Generates nearly "
                        "as many tickets as the thermal defect and costs almost nothing."),
            "work_order_ids": wo_ids("distractor_comms"),
            "sites": sorted({w["site_name"] for w in by_cls["distractor_comms"]}),
            "lost_production_mwh_recorded": round(sum(
                w["estimated_lost_production_mwh"] or 0 for w in by_cls["distractor_comms"]), 1),
        },
    },
}
with open("/home/user/Anthropic-Takehome-Demo/eval/ground_truth.json", "w") as f:
    json.dump(gt, f, indent=1)
print("wrote eval/ground_truth.json")
p = gt["findings"]["signal_1_kelvara_thermal"]["population"]
print(json.dumps(p, indent=1))
print("labor hours on signal 1:", gt["findings"]["signal_1_kelvara_thermal"]["observed_cost"])
