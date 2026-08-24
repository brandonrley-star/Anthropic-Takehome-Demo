"""Background work order scheduling."""

import math
from config import substream, BUDGET, TARGET_WORK_ORDERS
import calendar_util as cal
import assets_ref as ar
import themes as th
import fleet


# Site-level reporting culture. This is the mechanism that stops raw work order
# count from correlating cleanly with actual reliability: two identical sites
# can differ 2x in ticket volume purely because of how their crews log.
# Blackfoot Draw is the deliberate inversion of Decoy 2 - short coverage window,
# small site, therefore low RAW count, but genuinely the worst site in the fleet
# on a per-MW-per-month basis. Normalising is what makes it visible.
CULTURE_OVERRIDES = {
    "Blackfoot Draw": 2.35,
    "Caprock Mesa": 1.15,
    "Sundowner Mesa": 1.10,
    "Marlow Crossing": 0.72,
    "Tallow Branch": 0.78,
    "Sawgrass Reach": 0.85,
}


def site_weights(sites):
    rng = substream("culture")
    w = {}
    for s in sites:
        cov = cal.coverage_months(s)
        cap = s["capacity_mwdc"] / 180.0
        age = 1.0 + 0.035 * (2026 - int(s["commercial_operation_date"][:4]))
        culture = CULTURE_OVERRIDES.get(s["site_name"], rng.uniform(0.74, 1.34))
        w[s["site_name"]] = dict(weight=cap * cov * age * culture,
                                 coverage=cov, culture=culture)
    return w


def _pick_theme(rng, site, month):
    region = site["region"]
    pool, wts = [], []
    for t in th.THEMES:
        w = float(t["weight"])
        k, wt = t["key"], t["wo_type"]
        if wt == "Vegetation":
            w *= cal.VEG_SEASON[region][month - 1] * (1.6 if region in ("SE_NONISO", "PJM_MATL") else 1.0)
        elif wt in ("CM", "Emergency"):
            w *= cal.CM_SEASON[region][month - 1]
        elif wt == "PM":
            w *= cal.PM_SEASON[month - 1]
        if k == "pm_wash":
            w *= {"CAISO_CV": 3.2, "ERCOT_WEST": 1.5, "CAISO_MOJAVE": 0.5,
                  "ERCOT_SOUTH": 1.0}.get(region, 0.35)
            w *= 1.6 if month in (3, 4, 5, 6, 7, 8, 9, 10) else 0.2
        if k == "misc_snow":
            w *= 6.0 if (region == "MISO_UMW" and month in (11, 12, 1, 2, 3)) else 0.02
        if k == "insp_storm":
            w *= 2.2 if region in ("SE_NONISO", "PJM_MATL", "ERCOT_WEST") else 0.7
        if k == "pm_bess" or k == "cm_bess":
            w *= 1.0 if site["bess"] else 0.0
        if k in ("pm_stringinv", "cm_stringinv"):
            w *= 1.0 if site["string_inverter_model"] else 0.0
        if k == "cm_module" or k == "wty_module":
            w *= 1.0 + 0.06 * (2026 - int(site["commercial_operation_date"][:4]))
        if w > 0:
            pool.append(t); wts.append(w)
    return rng.choices(pool, weights=wts)[0]


def _asset_for(rng, kind, site, site_assets):
    nb = ar.n_blocks_for(site["capacity_mwdc"])
    if kind == "inverter":
        return rng.choice(site_assets)["asset_id"] if site_assets else ar.combiner(rng, nb)
    if kind == "string_inverter":
        pfx = {"ST-250": "SLT25", "CE-275": "CES27"}.get(site["string_inverter_model"], "SLT25")
        return ar.string_inv(rng, pfx, int(site["commercial_operation_date"][:4]))
    if kind == "combiner":
        return ar.combiner(rng, nb)
    if kind == "tracker":
        return ar.tracker_zone(rng, min(14, nb + 2)) if rng.random() < 0.55 else ar.tracker_row(rng, nb)
    if kind == "xfmr":
        return ar.transformer(rng, nb)
    if kind == "bess":
        return ar.bess_rack(rng)
    if kind == "met":
        return ar.met_station(rng)
    if kind in ("module", "mv", "site"):
        return "" if rng.random() < 0.55 else ar.block_tag(rng, nb)
    return ""


def pick_tech(rng, site, techs, prefer_travel=0.0):
    region = site["region"]
    local = [t for t in techs if t["home_region"] == region]
    travel = [t for t in techs if t["home_region"] == "TRAVEL"]
    if travel and rng.random() < (prefer_travel + 0.06):
        return rng.choice(travel)
    return rng.choice(local) if local else rng.choice(techs)


def tech_available(tech, d):
    return cal.parse(tech["hire_date"]) <= d


def resolution_for(rng, theme):
    codes = [c for c, _ in theme["res"]]
    wts = [w for _, w in theme["res"]]
    code = rng.choices(codes, weights=wts)[0]
    # Deliberate miscoding: real crews pick the wrong bucket often. This is why
    # resolution_code cannot be trusted as a grouping key anywhere in the corpus.
    if rng.random() < 0.13:
        code = rng.choice([c for c in th.THEMES[0]["res"] and
                           ["RESET", "PART-REPL", "SW-UPDATE", "NO-FAULT-FOUND", "CLEANED",
                            "ADJUSTED", "ESCALATED", "VENDOR-REFERRED", "OTHER"]])
    return code


def close_date(rng, opened, res_code, wo_type):
    r = rng.random()
    if res_code in ("ESCALATED", "VENDOR-REFERRED") and r < 0.34:
        return None
    if opened >= cal.parse("2026-05-01") and r < 0.16:
        return None
    if r < 0.46:
        lag = 0
    elif r < 0.76:
        lag = rng.randint(1, 3)
    elif r < 0.94:
        lag = rng.randint(4, 21)
    else:
        lag = rng.randint(22, 75)
    from datetime import timedelta
    d = opened + timedelta(days=lag)
    return None if d > cal.WINDOW_END else d


def priority_for(rng, wo_type):
    table = {
        "Emergency": [("P1", 6), ("P2", 4)],
        "CM":        [("P2", 4), ("P3", 6), ("P1", 1), ("P4", 1)],
        "Warranty":  [("P3", 6), ("P2", 2), ("P4", 2)],
        "PM":        [("P4", 5), ("P3", 5)],
        "Inspection":[("P4", 6), ("P3", 4)],
        "Vegetation":[("P4", 7), ("P3", 3)],
    }[wo_type]
    return rng.choices([c for c, _ in table], weights=[w for _, w in table])[0]


def lost_production(rng, wo_type, hours, res_code):
    """Present on a minority of tickets only, and never systematically."""
    if wo_type in ("Vegetation", "Inspection"):
        return None
    p = {"Emergency": 0.52, "CM": 0.24, "Warranty": 0.18, "PM": 0.05}[wo_type]
    if rng.random() > p:
        return None
    base = {"Emergency": (4, 140), "CM": (0.3, 42), "Warranty": (0.2, 18), "PM": (0.1, 6)}[wo_type]
    v = math.exp(rng.uniform(math.log(base[0]), math.log(base[1])))
    return round(v, 1 if v < 10 else 0)
