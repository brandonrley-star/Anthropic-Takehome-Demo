"""
Assemble the full work order skeleton set.

The single most important property of this module: EVERY work order, planted or
background, has its structured fields produced by the same functions with the
same distributions. The only thing that differs between a planted work order and
a routine one is the content of the narrative brief. There is no branch anywhere
below that gives a planted record a different priority model, a different labour
model, a different completeness model or a different technician pool.
"""

import math
from datetime import timedelta
from config import substream
import calendar_util as cal
import assets_ref as ar
import themes as th
import schedule as sch
import signals as sg
import briefs as bf
import fleet

# Some work does not cost production even when it generates a ticket. Applied
# by theme, not by planted-vs-background: a comms dropout and a SCADA outage are
# both near-costless regardless of which pattern they belong to.
LOST_SCALE = {
    "cm_scada": 0.05, "cm_met": 0.02, "misc_dup": 0.0, "misc_safety": 0.0,
    "insp_walk": 0.0, "insp_fence": 0.0, "veg_mow": 0.0, "veg_spray": 0.0,
    "veg_tree": 0.0, "pm_torque": 0.05, "pm_met": 0.02,
}

WORD_RANGE = {"fragment": (6, 22), "clipped": (13, 46), "narrative": (33, 96),
              "thorough": (70, 205)}

# Firmware revisions quoted casually across the fleet on every inverter model.
# Signal 1's four mentions of the affected revision sit inside this noise.
BACKGROUND_FIRMWARE = [
    "Firmware on this one is {v}, matches the rest of the block.",
    "Noted fw rev {v} while I was in the service menu.",
    "Checked the rev, {v}. Nothing pending from the OEM.",
    "Running {v}. Flagged for the next update window.",
    "{v} installed, took about twenty minutes and it came back clean.",
]
FW_VERSIONS = ["5.1.0", "5.0.4", "4.3.2", "4.3.0", "3.9.7", "5.2.1", "4.4.1", "2.8.3", "6.0.0"]


def target_words(rng, register, wo_type, theme_key=None):
    lo, hi = WORD_RANGE[register]
    n = round(math.exp(rng.uniform(math.log(lo), math.log(hi))))
    if wo_type == "Emergency":
        n = round(n * rng.uniform(1.15, 1.5))
    elif wo_type in ("PM", "Vegetation"):
        n = round(n * rng.uniform(0.8, 1.05))
    if theme_key == "misc_dup":
        n = rng.randint(3, 9)
    return max(3, n)


def clamp_words(n, brief):
    """A narrative expands a brief; it does not invent substance that is not
    there. A twelve word brief must not become a 170 word narrative just because
    the assigned technician is a verbose writer."""
    bw = max(4, len(brief.split()))
    return max(3, min(n, round(bw * 3.4) + 10), round(bw * 0.42))


def finalize(rng, wo, techs, sites_by_name):
    """Fill every remaining structured field. Class-agnostic by construction."""
    site = wo["site"]
    d = wo["date_opened"]

    # technician: same regional pool for every class of work order
    if wo.get("_tech"):
        tech = [t for t in techs if t["technician_id"] == wo["_tech"]][0]
    else:
        pool = [t for t in techs if sch.tech_available(t, d)]
        prefer = 0.10 if wo["wo_type"] in ("Warranty", "Emergency") else 0.0
        tech = sch.pick_tech(rng, site, pool, prefer_travel=prefer)
    wo["technician_id"] = tech["technician_id"]
    wo["_register"] = tech["_register"]
    wo["_voice"] = tech["_voice"]

    wo["priority"] = sch.priority_for(rng, wo["wo_type"])
    theme_key = wo.get("_theme_key")
    lo, hi = wo.get("_hours", (1.5, 8))
    h = math.exp(rng.uniform(math.log(lo), math.log(hi)))
    wo["labor_hours"] = round(h, 1) if h < 10 else round(h * 2) / 2

    codes = wo.get("res_pool") or ["OTHER"]
    code = rng.choice(codes)
    if rng.random() < 0.13:                       # deliberate miscoding, fleet-wide
        code = rng.choice(["RESET", "PART-REPL", "SW-UPDATE", "NO-FAULT-FOUND", "CLEANED",
                           "ADJUSTED", "ESCALATED", "VENDOR-REFERRED", "OTHER"])
    wo["resolution_code"] = code

    parts = wo.get("_parts_pool")
    chosen = rng.choice(parts) if parts else None
    if chosen and rng.random() < 0.22:            # techs often leave it blank
        chosen = None
    if chosen and rng.random() < 0.35:
        chosen = f"{chosen} x{rng.randint(2, 4)}"
    wo["parts_used"] = chosen or ""

    lost = sch.lost_production(rng, wo["wo_type"], wo["labor_hours"], code)
    scale = wo.get("_lost_scale", 1.0)
    if lost is not None and scale != 1.0:
        lost = round(lost * scale, 2) if lost * scale < 10 else round(lost * scale)
        if lost <= 0:
            lost = None
    wo["estimated_lost_production_mwh"] = lost

    cd = sch.close_date(rng, d, code, wo["wo_type"])
    wo["date_closed"] = cd
    wo["_target_words"] = clamp_words(
        target_words(rng, tech["_register"], wo["wo_type"], theme_key), wo["brief"])
    return wo


def background(sites, assets, techs, n_target, rng=None):
    rng = rng or substream("background")
    by_name = {s["site_name"]: s for s in sites}
    assets_by_site = {}
    for a in assets:
        assets_by_site.setdefault(a["site_name"], []).append(a)

    weights = sch.site_weights(sites)
    total_w = sum(v["weight"] for v in weights.values())

    wos = []
    for s in sites:
        share = weights[s["site_name"]]["weight"] / total_w
        n = max(3, round(share * n_target))
        cs, ce = cal.coverage_start(s), cal.WINDOW_END
        valid = [(y, m) for (y, m) in cal.ALL_MONTHS
                 if cal.parse(f"{y}-{m:02d}-28") >= cs]
        if not valid:
            valid = [(2026, 6)]
        for _ in range(n):
            y, m = rng.choice(valid)
            d = cal.random_day(rng, y, m)
            if d < cs:
                d = cs + timedelta(days=rng.randint(0, 20))
            theme = sch._pick_theme(rng, s, m)
            nb = ar.n_blocks_for(s["capacity_mwdc"])
            asset = sch._asset_for(rng, theme["asset_kind"], s, assets_by_site.get(s["site_name"], []))
            brief = rng.choice(theme["briefs"])
            # Use the asset's own block in the brief where the asset IS a block
            # or carries one, so the narrative does not name a different part of
            # the site than the asset_id field does.
            if asset and asset.startswith("B") and len(asset) == 3:
                blk = asset
            elif asset and "-B" in asset:
                blk = asset.split("-B")[1][:2]
                blk = f"B{blk}"
            else:
                blk = ar.block_tag(rng, nb)
            fill = dict(asset=asset or "the block", block=blk,
                        n=rng.randint(2, 14), pct=rng.choice([2, 3, 4, 5, 6, 8]),
                        cb=ar.combiner(rng, nb), ang=rng.choice([-45, -30, 0, 25, 52, 60]),
                        part=rng.choice([p for p in (theme["parts"] or ["the part"]) if p] or ["the part"]),
                        hrs=rng.randint(2, 9))
            wos.append(dict(_cls="background", _theme_key=theme["key"], site=s,
                            date_opened=d, asset_id=asset, wo_type=theme["wo_type"],
                            res_pool=_expand(theme["res"]),
                            _lost_scale=LOST_SCALE.get(theme["key"], 1.0),
                            _parts_pool=theme["parts"], _hours=theme["hours"],
                            brief=brief.format(**fill)))
    # firmware chatter spread across inverter work fleet-wide
    inv = [w for w in wos if w["_theme_key"] in ("pm_inverter", "cm_inv_acfault", "cm_inv_part",
                                                 "cm_inv_cooling", "cm_stringinv", "pm_stringinv",
                                                 "wty_inverter", "cm_inv_dcgf")]
    for w in rng.sample(inv, min(26, len(inv))):
        w["brief"] += " " + rng.choice(BACKGROUND_FIRMWARE).format(v=rng.choice(FW_VERSIONS))
    return wos


def _expand(res):
    out = []
    for c, w in res:
        out.extend([c] * w)
    return out
