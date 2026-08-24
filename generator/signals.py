"""
Planted patterns. Nothing in this module writes an identifying value into any
emitted field: every work order it produces is built from the same field
generators as background work, and the only thing that distinguishes it is the
CONTENT of the narrative brief.
"""

from datetime import timedelta
from config import substream
import calendar_util as cal
import assets_ref as ar
import schedule as sch
import fleet

HOT = {5, 6, 7, 8, 9}


# ===========================================================================
# SIGNAL 1 - Kelvara KVP-3600 defect-window thermal degradation
# ===========================================================================
S1_SYMPTOMS = {
    1: [
        ("overtemp_trip",  "CM", ["RESET", "NO-FAULT-FOUND"],
         "{asset} tripped on over temperature mid afternoon. Reset at the HMI, came back "
         "and ran the rest of the day. Nothing else in the fault log."),
        ("comms_offline",  "CM", ["RESET", "NO-FAULT-FOUND"],
         "SCADA showed {asset} offline, drove out expecting a comms issue, unit was in "
         "fault and had stopped itself. Restarted, back online."),
        ("derate",         "CM", ["NO-FAULT-FOUND", "OTHER"],
         "{asset} was derating all afternoon, output down maybe {pct}% against its "
         "neighbours. No fault logged, nothing to reset. Watched it recover after sundown."),
        ("high_cab_temp",  "CM", ["NO-FAULT-FOUND", "ADJUSTED"],
         "Cabinet temperature alarm on {asset}, was reading high but under the trip point. "
         "Nothing obviously wrong inside. Left it running."),
    ],
    2: [
        ("fan_airflow",    "CM", ["CLEANED", "ADJUSTED", "PART-REPL"],
         "{asset} fan bank all running but airflow across the stack felt low. Pulled and "
         "cleaned the filters, they were not that dirty. Temps came down some."),
        ("repeat_trip",    "CM", ["RESET", "ADJUSTED", "ESCALATED"],
         "Second overtemp on {asset} this season. Reset it again. Checked the intake and "
         "the heat sinks, both clear."),
        ("vendor_call",    "CM", ["VENDOR-REFERRED", "ESCALATED", "OTHER", "NO-FAULT-FOUND"],
         "{asset} keeps derating in the afternoon heat. Got the OEM support line on the "
         "phone, they had me pull logs and send them in. Case opened, no answer yet."),
        ("fan_replace",    "CM", ["PART-REPL", "CLEANED"],
         "Replaced two fans in the {asset} fan bank, bearings were noisy. Others tested ok. "
         "Cleaned the plenum while I was in there."),
    ],
    3: [
        ("igbt",           "CM", ["PART-REPL", "PART-REPL", "PART-REPL", "VENDOR-REFERRED"],
         "{asset} hard faulted. Opened the cabinet, IGBT module {n} had clear thermal "
         "damage, discoloured and the busbar was heat marked. Replaced the module and the "
         "gate driver. Long day."),
        ("contactor",      "CM", ["PART-REPL", "PART-REPL", "PART-REPL", "ESCALATED"],
         "{asset} would not open the DC side. Found the DC contactor welded shut. Replaced "
         "it. Contacts were badly pitted, looked like it had been running hot for a while."),
        ("igbt_warranty",  "Warranty", ["VENDOR-REFERRED", "PART-REPL", "ESCALATED"],
         "{asset} IGBT failure, unit is inside the parts warranty so opened a case with "
         "Kelvara before touching it. They authorised the swap, part shipped from the depot."),
        ("emerg_shutdown", "Emergency", ["ESCALATED", "PART-REPL", "PART-REPL", "OTHER"],
         "Called out, {asset} shut down hard and would not restart. Thermal damage on the "
         "power stage. Isolated and locked out pending parts."),
    ],
}

# Firmware is mentioned on 4 of the 48 signal work orders. It is NOT rare in the
# corpus overall - roughly 26 background work orders across every inverter model
# also quote a firmware revision - so "narrative mentions firmware" is not a
# useful filter on its own, and the link has to come from correlating WHICH
# revision appears against batch and outcome.
S1_FIRMWARE_NOTES = [
    "Checked the rev while I was in the menus, still on 4.2.1.",
    "Noted fw 4.2.1 on this one, not sure if that is current.",
    "Firmware showing 4.2.1. Asked the OEM if there is a newer cooling package, no reply yet.",
    "Running a 4.2.x build, did not write down the exact rev.",
]

S1_SPECULATION = [
    "Starting to wonder if the fan control is ramping late on these. Just a hunch, the "
    "airflow does not pick up until it is already hot.",
    "Third time on a Kelvara unit this summer with the same story. Might be a fan control "
    "thing rather than the fans themselves. Nothing I can prove.",
]


def build_signal1(sites, assets, techs, rng=None):
    rng = rng or substream("signal1")
    by_name = {s["site_name"]: s for s in sites}
    defect = [a for a in assets if a["_defect_window"]]
    candidates = [a for a in defect if a["site_name"] in fleet.SIGNAL1_SITES]

    # 30 of the 43 units at the nine sites actually fail. The other 13, plus 9
    # more at hot sites with no failures and 22 in cool regions, are the
    # at-risk population that has to be quantified from the asset registry.
    rng.shuffle(candidates)
    failing = candidates[:30]
    counts = [3] * 4 + [2] * 10 + [1] * 16          # 12 + 20 + 16 = 48
    rng.shuffle(counts)

    wos = []
    fw_slots = rng.sample(range(48), 4)
    spec_units = None
    idx = 0
    for unit, n in zip(failing, counts):
        site = by_name[unit["site_name"]]
        comm = cal.parse(unit["commissioned_date"])
        start = max(comm + timedelta(days=rng.randint(25, 120)), cal.coverage_start(site))
        hot_slots = [(y, m) for (y, m) in cal.ALL_MONTHS
                     if m in HOT and cal.parse(f"{y}-{m:02d}-28") >= start]
        if not hot_slots:
            hot_slots = [(y, m) for (y, m) in cal.ALL_MONTHS
                         if cal.parse(f"{y}-{m:02d}-28") >= start][:3] or [(2026, 6)]

        # A defective unit fails in one of its FIRST hot seasons, not a season
        # sampled uniformly from the whole corpus window. Without this bias the
        # units commissioned in 2024 never fail until 2025 and the cluster loses
        # its long thin tail.
        seasons = sorted({y for (y, _) in hot_slots})
        chosen = []
        first_season = seasons[0] if (len(seasons) == 1 or rng.random() < 0.72) else seasons[1]
        pool0 = [sl for sl in hot_slots if sl[0] == first_season]
        mw = {5: 0.5, 6: 0.9, 7: 1.6, 8: 1.6, 9: 1.0}
        chosen.append(rng.choices(pool0, weights=[mw[m] for (_, m) in pool0])[0])
        later = [sl for sl in hot_slots if sl > chosen[0]]
        for _ in range(n - 1):
            if not later:
                break
            pick = rng.choices(later, weights=[mw[m] * (1.0 + 0.5 * (y - first_season))
                                               for (y, m) in later])[0]
            chosen.append(pick)
            later = [sl for sl in later if sl > pick]
        chosen.sort()

        for i, (y, m) in enumerate(chosen):
            d = cal.random_day(rng, y, m)
            if d < start:
                d = start + timedelta(days=rng.randint(0, 14))
            # cumulative hot months this unit has actually run since commissioning
            cum_hot = sum(1 for (yy, mm) in cal.ALL_MONTHS
                          if mm in HOT and cal.parse(f"{yy}-{mm:02d}-15") >= comm
                          and cal.parse(f"{yy}-{mm:02d}-15") <= d)
            stage = 1
            if i >= 1 or cum_hot >= 4:
                stage = 2
            if i >= 2 or (i >= 1 and cum_hot >= 6) or cum_hot >= 8:
                stage = 3
            key, wo_type, codes, brief = rng.choice(S1_SYMPTOMS[stage])
            wos.append(dict(_cls="signal_1", _stage=stage, _sym=key, _cum_hot=cum_hot,
                            site=site, asset_id=unit["asset_id"], wo_type=wo_type,
                            date_opened=d, res_pool=codes,
                            brief=brief, _unit=unit, _fw=idx in fw_slots))
            idx += 1

    # Units whose first hot season is 2026 run out of later slots, which leaves
    # the budget short. Top up by giving additional incidents to units that do
    # still have room, preserving the intended 48.
    guard = 0
    while len(wos) < 48 and guard < 400:
        guard += 1
        unit = rng.choice(failing)
        existing = sorted(w["date_opened"] for w in wos if w["asset_id"] == unit["asset_id"])
        if not existing or len(existing) >= 4:
            continue
        comm = cal.parse(unit["commissioned_date"])
        site = by_name[unit["site_name"]]
        later = [(y, m) for (y, m) in cal.ALL_MONTHS if m in HOT
                 and cal.parse(f"{y}-{m:02d}-01") > existing[-1]]
        if not later:
            continue
        y, m = rng.choices(later, weights=[{5: .5, 6: .9, 7: 1.6, 8: 1.6, 9: 1.0}[m] for (_, m) in later])[0]
        d = cal.random_day(rng, y, m)
        cum_hot = sum(1 for (yy, mm) in cal.ALL_MONTHS if mm in HOT
                      and comm <= cal.parse(f"{yy}-{mm:02d}-15") <= d)
        i = len(existing)
        stage = 3 if (i >= 2 or cum_hot >= 6) else 2
        key, wo_type, codes, brief = rng.choice(S1_SYMPTOMS[stage])
        wos.append(dict(_cls="signal_1", _stage=stage, _sym=key, _cum_hot=cum_hot,
                        site=site, asset_id=unit["asset_id"], wo_type=wo_type,
                        date_opened=d, res_pool=codes, brief=brief, _unit=unit, _fw=False))
    # Nudge a few incidents into shoulder months. A unit whose power stage is
    # already thermally damaged can fail on a warm day in April or October, and
    # a cluster confined perfectly to May-September would make `month` a clean
    # filter on its own.
    for w in rng.sample([x for x in wos if x["_stage"] >= 2], 3):
        from datetime import timedelta as _td
        m0 = w["date_opened"].month
        shift = rng.choice([30, 36]) if m0 >= 8 else rng.choice([-34, -40])
        w["date_opened"] = w["date_opened"] + _td(days=shift)
        w["date_opened"] = min(max(w["date_opened"], cal.WINDOW_START), cal.WINDOW_END)

    fw_pick = rng.sample(range(len(wos)), 4)
    for i, w in enumerate(wos):
        w["_fw"] = i in fw_pick

    # two independent, non-escalating speculations at two different sites
    pool = [w for w in wos if w["_stage"] >= 2]
    picks, seen = [], set()
    for w in sorted(pool, key=lambda x: x["date_opened"]):
        if w["site"]["site_name"] not in seen:
            picks.append(w); seen.add(w["site"]["site_name"])
        if len(picks) == 2:
            break
    for w, txt in zip(picks, S1_SPECULATION):
        w["_speculation"] = txt
    return wos


# ===========================================================================
# SIGNAL 2 - Caprock Mesa backsheet degradation read as soiling
# ===========================================================================
def build_signal2(sites, techs, rng=None):
    rng = rng or substream("signal2")
    site = [s for s in sites if s["site_name"] == fleet.SIGNAL2_SITE][0]
    nb = ar.n_blocks_for(site["capacity_mwdc"])          # 8 blocks
    old_blocks = [f"B{i:02d}" for i in range(1, 5)]      # oldest sections
    all_blocks = [f"B{i:02d}" for i in range(1, nb + 1)]

    # Rising frequency across the window: 4 / 5 / 7 / 10 by half-year.
    halves = [(2024, 7, 12, 4), (2025, 1, 6, 5), (2025, 7, 12, 7), (2026, 1, 6, 10)]
    months = []
    for y, m0, m1, n in halves:
        for _ in range(n):
            months.append((y, rng.randint(m0, m1)))
    months.sort()
    WASH_OK = {3, 4, 5, 6, 7, 8, 9, 10}

    # 10 washes with a decaying benefit window, 5 SCADA underperformance,
    # 4 IR scans called unremarkable, 3 passing cosmetic observations,
    # 4 ground fault tickets that escalate in tone over time.
    kinds = (["wash"] * 10 + ["scada"] * 5 + ["ir"] * 4 + ["cosmetic"] * 3 + ["gf"] * 4)
    # washes and gf skew later, ir skews earlier, so the mix drifts over time
    order = {"ir": 0, "wash": 1, "scada": 2, "cosmetic": 3, "gf": 4}
    kinds.sort(key=lambda k: order[k] + rng.uniform(-1.6, 1.6))

    wos = []
    used = []          # (block, kind, date) to stop near-duplicate tickets
    for i, ((y, m), kind) in enumerate(zip(months, kinds)):
        # Nobody schedules a wash crew in December in West Texas.
        if kind == "wash" and m not in WASH_OK:
            ok = [mm for mm in sorted(WASH_OK)
                  if cal.WINDOW_START <= cal.parse(f"{y}-{mm:02d}-15") <= cal.WINDOW_END]
            m = rng.choice(ok) if ok else m
        d = cal.random_day(rng, y, m)
        d = min(max(d, cal.WINDOW_START), cal.WINDOW_END)
        was_old = rng.random() < 0.72
        blk = rng.choice(old_blocks) if was_old else rng.choice(all_blocks)
        # If we have to move the block to avoid a near-duplicate ticket, stay in
        # the same part of the array: the degradation is concentrated in the
        # older sections and must not wander out of them.
        for _ in range(6):
            if not any(b == blk and k == kind and abs((d - dd).days) < 21 for b, k, dd in used):
                break
            blk = rng.choice(old_blocks if was_old else all_blocks)
        used.append((blk, kind, d))
        prog = i / max(1, len(months) - 1)   # 0 early -> 1 late
        wos.append(dict(_cls="signal_2", _kind=kind, site=site, date_opened=d,
                        _block=blk, _progress=prog, asset_id="", wo_type="", res_pool=[],
                        brief=""))
    return wos


# ===========================================================================
# DECOY 1 - Sundowner Mesa: one wind event plus one technician's logging habit
# ===========================================================================
EVENT_DATE = cal.parse("2025-03-14")
CLAIM_REF = "NRS-PL-2025-0417"


def build_decoy1(sites, techs, rng=None):
    rng = rng or substream("decoy1")
    site = [s for s in sites if s["site_name"] == fleet.DECOY1_SITE][0]
    nb = ar.n_blocks_for(site["capacity_mwdc"])
    wos = []

    # 21 per-row tickets from the new tech, covering roughly seven zones' worth
    # of work that his colleagues would have logged as seven tickets.
    for i in range(21):
        d = EVENT_DATE + timedelta(days=rng.randint(1, 47))
        wos.append(dict(_cls="decoy_1", _mode="per_row", site=site, date_opened=d,
                        asset_id=ar.tracker_row(rng, nb), wo_type="CM",
                        _tech="TECH-0231", brief="", res_pool=["PART-REPL", "ADJUSTED", "RESET"]))
    # 10 tickets from everyone else, logged per zone as usual
    for i in range(10):
        d = EVENT_DATE + timedelta(days=rng.randint(0, 47))
        wos.append(dict(_cls="decoy_1", _mode="per_zone", site=site, date_opened=d,
                        asset_id=ar.tracker_zone(rng, 12),
                        wo_type=rng.choices(["CM", "Emergency", "Inspection"], weights=[6, 2, 2])[0],
                        _tech=None, brief="", res_pool=["PART-REPL", "ADJUSTED", "ESCALATED", "OTHER"]))
    wos.sort(key=lambda w: w["date_opened"])
    # three narratives name the event outright; two carry the insurance claim ref
    for w in wos[:2]:
        w["_names_event"] = True
    wos[4]["_names_event"] = True
    for w in [x for x in wos if x["wo_type"] == "Emergency"][:2] or wos[:2]:
        w["_claim"] = CLAIM_REF
    for w in rng.sample(wos, 8):
        w.setdefault("_oblique", True)
    return wos


def build_tech231_habit(sites, rng=None):
    """TECH-0231 logs per row everywhere, all the time. Without this the habit
    looks like an artifact of the March event rather than a standing practice,
    and Decoy 1 becomes unresolvable."""
    rng = rng or substream("habit")
    mojave = [s for s in sites if s["region"] == "CAISO_MOJAVE"]
    wos = []
    for _ in range(16):
        site = rng.choice(mojave)
        y, m = rng.choice([(y, m) for (y, m) in cal.ALL_MONTHS
                           if cal.parse(f"{y}-{m:02d}-28") >= cal.parse("2025-04-01")])
        wos.append(dict(_cls="background", _habit=True, site=site,
                        date_opened=cal.random_day(rng, y, m),
                        asset_id=ar.tracker_row(rng, ar.n_blocks_for(site["capacity_mwdc"])),
                        wo_type=rng.choices(["CM", "PM"], weights=[7, 3])[0],
                        _tech="TECH-0231", brief="", res_pool=["PART-REPL", "ADJUSTED", "RESET", "NO-FAULT-FOUND"]))
    return wos


# ===========================================================================
# DISTRACTOR CLUSTERS - real, multi-site, and commercially minor.
# These exist to test whether a detection system ranks by financial impact
# rather than by how many tickets a pattern generates. The comms cluster in
# particular produces MORE work orders than Signal 1 while being worth almost
# nothing, so raw cluster size points at the wrong finding.
# ===========================================================================
SLEW_BRIEFS = [
    "{asset} rotating rough through the morning sweep. Pulled the drive cover, grease was dried out and "
    "gritty. Repacked it, moves smooth now.",
    "Slew drive on {asset} notchy under load. Regreased, backlash still within spec so leaving it.",
    "{asset} squealing on the east sweep. Old grease had separated, cleaned it out and repacked. "
    "These older rows are all about due.",
    "Regreased the drive on {asset}, third one in this block this quarter. Normal wear for the vintage.",
    "{asset} drive replaced, grease had hardened and the gear faces were scored. Row back in service.",
]

COMMS_BRIEFS = [
    "{asset} dropped off the network again. Power cycled at the AC disconnect, came back. Production "
    "was never affected, it just stops reporting.",
    "Comms fault on {asset}. Nothing wrong with the unit, it was inverting fine the whole time. Reset "
    "the comms card.",
    "Half the string inverters in {block} showed offline overnight, all back by the time I arrived. "
    "Humidity was high. No production loss.",
    "{asset} not reporting. Reseated the comms module and the RS485 leads. Fine after that.",
    "Same units in {block} dropping out again. Logged it, no action, they self recover.",
    "{asset} offline in the portal but generating normally per the meter. Firmware on the comms board "
    "is a couple revs back, flagged it for the next update window.",
]


def build_distractor_slew(sites, rng=None):
    """Auster Trackline H2 slew drive grease degradation on 2016-2019 vintage
    rows. Genuine, spans five sites, and correctly worth deprioritising."""
    rng = rng or substream("distractor_slew")
    pool = [s for s in sites if s["tracker_model"] == "Trackline H2"
            and int(s["commercial_operation_date"][:4]) <= 2019]
    # Keep this cluster off Caprock Mesa and Sundowner Mesa: those two sites
    # already carry a planted pattern each, and stacking a third confound on
    # them muddies findings that are meant to be readable.
    pool = [s for s in pool if s["site_name"] not in (fleet.SIGNAL2_SITE, fleet.DECOY1_SITE)]
    pool = sorted(pool, key=lambda s: s["commercial_operation_date"])[:5]
    wos = []
    for _ in range(38):
        site = rng.choice(pool)
        y, m = rng.choice([(y, m) for (y, m) in cal.ALL_MONTHS
                           if cal.parse(f"{y}-{m:02d}-28") >= cal.coverage_start(site)])
        nb = ar.n_blocks_for(site["capacity_mwdc"])
        wos.append(dict(_cls="distractor_slew", site=site, date_opened=cal.random_day(rng, y, m),
                        asset_id=ar.tracker_row(rng, nb) if rng.random() < 0.6 else ar.tracker_zone(rng, 12),
                        wo_type=rng.choices(["CM", "PM", "Warranty"], weights=[6, 3, 1])[0],
                        res_pool=["ADJUSTED", "PART-REPL", "CLEANED", "NO-FAULT-FOUND"],
                        brief=rng.choice(SLEW_BRIEFS)))
    return wos


def build_distractor_comms(sites, rng=None):
    """Soltera ST-250 comms module dropouts at humid sites. High ticket count,
    essentially zero production impact."""
    rng = rng or substream("distractor_comms")
    pool = [s for s in sites if s["string_inverter_model"] == "ST-250"
            and s["region"] in ("SE_NONISO", "PJM_MATL", "ERCOT_SOUTH")]
    if not pool:
        pool = [s for s in sites if s["string_inverter_model"] == "ST-250"]
    wos = []
    for _ in range(44):
        site = rng.choice(pool)
        y, m = rng.choice([(y, m) for (y, m) in cal.ALL_MONTHS
                           if cal.parse(f"{y}-{m:02d}-28") >= cal.coverage_start(site)])
        wos.append(dict(_cls="distractor_comms", site=site, date_opened=cal.random_day(rng, y, m),
                        asset_id=ar.string_inv(rng, "SLT25", int(site["commercial_operation_date"][:4])),
                        wo_type=rng.choices(["CM", "PM"], weights=[8, 2])[0],
                        res_pool=["RESET", "NO-FAULT-FOUND", "SW-UPDATE", "ADJUSTED"],
                        brief=rng.choice(COMMS_BRIEFS)))
    return wos
