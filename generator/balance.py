"""
Structural balance pass.

Most matching in this corpus happens by construction: planted and background
work orders run through the same field generators with the same distributions.
This pass exists for the residual - fields where small-sample draw pushed a
planted group away from its controls far enough that a single-column sort would
notice. It resamples the offending values from the matched control distribution.

It runs BEFORE narrative authoring, so narrative length targets are corrected
here rather than patched after the text exists.
"""

import collections
from config import substream
import calendar_util as _cal


def cal_end():
    return _cal.WINDOW_END

INV_THEMES = {"cm_inv_dcgf", "cm_inv_acfault", "cm_inv_part", "cm_inv_cooling",
              "wty_inverter", "pm_inverter"}

# planted class -> predicate selecting its matched background controls
CONTROLS = {
    "signal_1": lambda w: w.get("_theme_key") in INV_THEMES,
    "signal_2": lambda w: w.get("_theme_key") in {"pm_wash", "insp_ir_aerial", "insp_walk",
                                                  "pm_gfault", "cm_combiner", "insp_soiling"},
    "decoy_1": lambda w: w.get("_theme_key") in {"cm_tracker_motor", "cm_tracker_ctrl",
                                                 "pm_tracker", "wty_tracker"},
}


def _by_type(rows):
    out = collections.defaultdict(list)
    for w in rows:
        out[w["wo_type"]].append(w)
    return out


def balance(wos, tolerance=1.6, verbose=True):
    rng = substream("balance")
    bg = [w for w in wos if w["_cls"] == "background"]
    report = []

    for cls, pred in CONTROLS.items():
        target = [w for w in wos if w["_cls"] == cls]
        if not target:
            continue
        ctl_all = [w for w in bg if pred(w)]
        ctl_by_type = _by_type(ctl_all)

        # --- priority: resample from the control distribution for the same wo_type
        for w in target:
            pool = ctl_by_type.get(w["wo_type"]) or ctl_all
            if pool:
                w["priority"] = rng.choice(pool)["priority"]

        # --- narrative length target: resample from controls of the same
        #     technician register, so voice still drives length but the planted
        #     group cannot sit systematically short or long.
        ctl_by_reg = collections.defaultdict(list)
        for w in ctl_all:
            ctl_by_reg[w["_register"]].append(w["_target_words"])
        for w in target:
            pool = ctl_by_reg.get(w["_register"])
            if pool:
                import build
                w["_target_words"] = build.clamp_words(rng.choice(pool), w["brief"])

        # --- lost production presence: match the control rate for the wo_type
        for wt, pool in ctl_by_type.items():
            if not pool:
                continue
            rate = sum(1 for w in pool if w["estimated_lost_production_mwh"] is not None) / len(pool)
            mags = [w["estimated_lost_production_mwh"] for w in pool
                    if w["estimated_lost_production_mwh"] is not None]
            for w in [x for x in target if x["wo_type"] == wt]:
                if rng.random() < rate:
                    if w["estimated_lost_production_mwh"] is None and mags:
                        w["estimated_lost_production_mwh"] = rng.choice(mags)
                else:
                    w["estimated_lost_production_mwh"] = None

        # --- still-open rate: planted work leans on ESCALATED / VENDOR-REFERRED,
        #     which carries a much higher chance of an open ticket. Left alone,
        #     "sort by tickets still open" enriches for the planted set.
        for wt, pool in ctl_by_type.items():
            if not pool:
                continue
            rate = sum(1 for w in pool if w["date_closed"] is None) / len(pool)
            closed = [w["date_closed"] for w in pool if w["date_closed"] is not None]
            for w in [x for x in target if x["wo_type"] == wt]:
                if rng.random() < rate:
                    w["date_closed"] = None
                elif w["date_closed"] is None and closed:
                    from datetime import timedelta
                    lag = rng.choice([0, 0, 1, 2, 3, 5, 9, 14, 21])
                    d = w["date_opened"] + timedelta(days=lag)
                    w["date_closed"] = d if d <= cal_end() else None

        report.append((cls, len(target), len(ctl_all)))

    if verbose:
        for cls, n, nc in report:
            print(f"  balanced {cls}: {n} work orders against {nc} matched controls")
    return wos
