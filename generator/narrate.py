"""
Narrative authoring driver.

Batches are STRATIFIED SHUFFLES, not contiguous slices: the work order list is
shuffled with a fixed seed before being cut into batches, so every batch mixes
sites, technicians, months and pattern classes. A batch that was all-planted
would let batch-level drift in authoring style correlate with plant status,
which would be the worst leak in the corpus.
"""

import json, os, hashlib, sys
from datetime import date
from config import substream, NARRATIVE_BATCH_SIZE, CHECKPOINT_DIR, MASTER_SEED
import run, balance


def _ser(o):
    if isinstance(o, date):
        return o.isoformat()
    raise TypeError(type(o))


def load_all():
    sites, assets, techs, wos = run.assemble()
    balance.balance(wos, verbose=False)
    rng = substream("batching")
    order = list(range(len(wos)))
    rng.shuffle(order)
    for pos, i in enumerate(order):
        wos[i]["_batch"] = pos // NARRATIVE_BATCH_SIZE
        wos[i]["_slot"] = pos
    return sites, assets, techs, wos


def n_batches(wos):
    return max(w["_batch"] for w in wos) + 1


def dump_batch(wos, techs, b):
    voices = {t["technician_id"]: t["_voice"] for t in techs}
    rows = sorted([w for w in wos if w["_batch"] == b], key=lambda w: w["_slot"])
    out = []
    for w in rows:
        out.append(dict(
            wo_id=w["wo_id"], tech=w["technician_id"], register=w["_register"],
            words=w["_target_words"], wo_type=w["wo_type"],
            site=w["site"]["site_name"], region=w["site"]["region"],
            date=w["date_opened"].isoformat(), asset=w["asset_id"],
            parts=w["parts_used"], res=w["resolution_code"],
            brief=w["brief"], voice=voices[w["technician_id"]]))
    return out


def batch_file(b):
    return os.path.join(CHECKPOINT_DIR, f"narratives_{b:03d}.json")


def have_batch(b):
    return os.path.exists(batch_file(b))


def save_batch(b, mapping):
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    blob = json.dumps(mapping, sort_keys=True, ensure_ascii=False)
    with open(batch_file(b), "w") as f:
        f.write(blob)
    return hashlib.sha256(blob.encode()).hexdigest()


def load_narratives():
    out = {}
    for fn in sorted(os.listdir(CHECKPOINT_DIR)):
        if fn.startswith("narratives_") and fn.endswith(".json"):
            with open(os.path.join(CHECKPOINT_DIR, fn)) as f:
                out.update(json.load(f))
    return out


def status(wos):
    nb = n_batches(wos)
    done = [b for b in range(nb) if have_batch(b)]
    return nb, done
