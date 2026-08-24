"""Orchestrate skeleton generation, checkpoint, and hand off to narrative authoring."""

import json, os, hashlib, sys
from datetime import date
from config import (MASTER_SEED, substream, TARGET_WORK_ORDERS, BUDGET,
                    NARRATIVE_BATCH_SIZE, CHECKPOINT_DIR, CORPUS_VERSION)
import calendar_util as cal
import assets_ref as ar
import fleet, build, signals as sg, briefs as bf, schedule as sch

# Hours and parts for planted work are mirrored from the analogous background
# theme, so labour and completeness match by construction rather than by a
# post-hoc correction.
S1_PROFILE = {
    1: ((1.5, 7.0), [None, None, None, "air filter set"]),
    2: ((2.0, 8.0), [None, "cooling fan", "air filter set", None]),
    3: ((4.0, 14.0), ["IGBT module", "DC contactor", "gate driver", "cooling fan"]),
}
S2_PROFILE = {"wash": ((6, 20), None, 0.0), "scada": ((2, 8), None, 0.35),
              "ir": ((4, 9), None, 0.0), "cosmetic": ((2, 7), None, 0.0),
              "gf": ((2, 6), [None, None, "string connector"], 0.15)}


def assemble():
    rng = substream("assemble")
    sites = fleet.build_sites()
    fleet.build_equipment(sites)
    assets = fleet.build_assets(sites)
    techs = fleet.build_technicians()
    by_name = {s["site_name"]: s for s in sites}

    planted = []

    # ---- Signal 1
    for w in sg.build_signal1(sites, assets, techs):
        hours, parts = S1_PROFILE[w["_stage"]]
        w["_hours"], w["_parts_pool"] = hours, parts
        n = rng.randint(1, 6)
        pct = rng.choice([6, 8, 10, 12, 15])
        w["brief"] = w["brief"].format(asset=w["asset_id"], n=n, pct=pct)
        if w.get("_fw"):
            w["brief"] += " " + rng.choice(sg.S1_FIRMWARE_NOTES)
        if w.get("_speculation"):
            w["brief"] += " " + w["_speculation"]
        planted.append(w)

    # ---- Signal 2
    for w in sg.build_signal2(sites, techs):
        wt, codes, text = bf.signal2_brief(rng, w["_kind"], w["_block"], w["_progress"])
        hours, parts, lscale = S2_PROFILE[w["_kind"]]
        w.update(wo_type=wt, res_pool=codes, brief=text, _hours=hours,
                 _parts_pool=parts, _lost_scale=lscale)
        if w["_kind"] in ("gf", "scada"):
            w["asset_id"] = ar.combiner(rng, 8, block=w["_block"])
        elif w["_kind"] == "ir":
            w["asset_id"] = w["_block"]
        else:
            w["asset_id"] = "" if rng.random() < 0.5 else w["_block"]
        planted.append(w)

    # ---- Decoy 1
    for w in sg.build_decoy1(sites, techs):
        w["brief"] = bf.decoy1_brief(rng, w).format(asset=w["asset_id"])
        w["_hours"] = (1.5, 5.0) if w["_mode"] == "per_row" else (5.0, 16.0)
        w["_parts_pool"] = ["damper", "tracker motor", None, "bearing housing", "coupling"]
        w["_lost_scale"] = 0.25
        planted.append(w)

    # ---- distractors
    for w in sg.build_distractor_slew(sites):
        w["brief"] = w["brief"].format(asset=w["asset_id"] or "the row")
        w["_hours"], w["_parts_pool"] = (2.0, 7.0), ["grease cartridge", "gearbox", None, None]
        w["_lost_scale"] = 0.15
        planted.append(w)
    for w in sg.build_distractor_comms(sites):
        nb = 8
        w["brief"] = w["brief"].format(asset=w["asset_id"], block=ar.block_tag(rng, nb))
        w["_hours"], w["_parts_pool"] = (0.75, 3.5), [None, None, None, "comms module"]
        w["_lost_scale"] = 0.03
        planted.append(w)

    # ---- TECH-0231's standing per-row habit outside the decoy window
    habit = sg.build_tech231_habit(sites)
    for w in habit:
        w["brief"] = rng.choice(bf.HABIT_BRIEFS).format(asset=w["asset_id"])
        w["_hours"], w["_parts_pool"] = (1.5, 5.0), ["tracker motor", None, "limit switch", None]
        w["_lost_scale"] = 0.25

    n_bg = TARGET_WORK_ORDERS - len(planted) - len(habit)
    bg = build.background(sites, assets, techs, n_bg)

    allwos = planted + habit + bg
    for w in allwos:
        build.finalize(rng, w, techs, by_name)

    # wo_id assigned LAST, in global date order, so the identifier sequence
    # carries no information about which generator produced a record.
    allwos.sort(key=lambda w: (w["date_opened"], w["site"]["site_name"], w["asset_id"]))
    seq = {}
    for w in allwos:
        y = w["date_opened"].year
        seq[y] = seq.get(y, 0) + 1
        w["wo_id"] = f"WO-{y}-{seq[y]:05d}"

    return sites, assets, techs, allwos


def checkpoint_path(name):
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    return os.path.join(CHECKPOINT_DIR, name)


def _ser(o):
    if isinstance(o, date):
        return o.isoformat()
    raise TypeError(type(o))


def save_skeletons(sites, assets, techs, wos):
    slim = []
    for w in wos:
        slim.append({k: v for k, v in w.items() if k not in ("site", "_unit", "_voice")}
                    | {"site_name": w["site"]["site_name"],
                       "region": w["site"]["region"]})
    payload = dict(master_seed=MASTER_SEED, corpus_version=CORPUS_VERSION,
                   n=len(slim), work_orders=slim)
    blob = json.dumps(payload, default=_ser, sort_keys=True)
    with open(checkpoint_path("skeletons.json"), "w") as f:
        f.write(blob)
    with open(checkpoint_path("skeletons.sha256"), "w") as f:
        f.write(hashlib.sha256(blob.encode()).hexdigest())
    return hashlib.sha256(blob.encode()).hexdigest()


if __name__ == "__main__":
    sites, assets, techs, wos = assemble()
    h = save_skeletons(sites, assets, techs, wos)
    import collections
    print(f"seed={MASTER_SEED}  work_orders={len(wos)}  sha256={h[:16]}")
    print("by class:", dict(collections.Counter(w["_cls"] for w in wos)))
    print("by type: ", dict(collections.Counter(w["wo_type"] for w in wos)))
