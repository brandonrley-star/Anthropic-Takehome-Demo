"""
Serialize the corpus.

The single most important property here is that output keys come from an
explicit ALLOWLIST rather than a denylist. A generator-internal field cannot
leak into corpus/ by being forgotten; it can only leak if someone deliberately
adds its name to the allowlist below. A byte-level scan for forbidden tokens
runs afterwards as a second line of defence.
"""

import json, csv, os, hashlib, sys
from datetime import date
from config import (MASTER_SEED, CORPUS_VERSION, CORPUS_DIR,
                    FORBIDDEN_CORPUS_TOKENS, OPERATOR_NAME)
import taxonomy as tx

WO_FIELDS = ["wo_id", "site_id", "site_name", "date_opened", "date_closed",
             "wo_type", "priority", "asset_id", "technician_id", "labor_hours",
             "parts_used", "narrative", "resolution_code",
             "estimated_lost_production_mwh"]

SITE_FIELDS = ["site_id", "site_name", "region", "capacity_mwdc",
               "commercial_operation_date", "om_contract_start",
               "central_inverter_models", "string_inverter_model",
               "module_models", "tracker_model", "bess_installed"]

ASSET_FIELDS = ["asset_id", "site_id", "site_name", "asset_class", "manufacturer",
                "model", "rated_mw", "commissioned_date", "warranty_parts_expiry"]

TECH_FIELDS = ["technician_id", "home_region", "hire_date"]

REGION_PUBLIC = {k: v["label"] for k, v in tx.REGIONS.items()}
REGION_PUBLIC["TRAVEL"] = "Multi-region (travelling)"


def _d(v):
    return v.isoformat() if isinstance(v, date) else v


def emit(sites, assets, techs, wos, narratives, outdir=CORPUS_DIR):
    os.makedirs(outdir, exist_ok=True)

    inv_by_site = {}
    for a in assets:
        inv_by_site.setdefault(a["site_name"], set()).add(a["model"])

    site_rows = []
    for s in sites:
        site_rows.append({
            "site_id": s["site_id"], "site_name": s["site_name"],
            "region": s["region_label"], "capacity_mwdc": s["capacity_mwdc"],
            "commercial_operation_date": s["commercial_operation_date"],
            "om_contract_start": s["om_contract_start"],
            "central_inverter_models": sorted(inv_by_site.get(s["site_name"], [])),
            "string_inverter_model": s["string_inverter_model"],
            "module_models": s["module_models"],
            "tracker_model": s["tracker_model"],
            "bess_installed": s["bess"],
        })

    asset_rows = [{k: _d(a[k]) for k in ASSET_FIELDS} for a in assets]
    asset_rows.sort(key=lambda r: r["asset_id"])

    tech_rows = [{"technician_id": t["technician_id"],
                  "home_region": REGION_PUBLIC[t["home_region"]],
                  "hire_date": t["hire_date"]} for t in techs]

    wo_rows = []
    for w in sorted(wos, key=lambda x: x["wo_id"]):
        wo_rows.append({
            "wo_id": w["wo_id"], "site_id": w["site"]["site_id"],
            "site_name": w["site"]["site_name"],
            "date_opened": _d(w["date_opened"]), "date_closed": _d(w["date_closed"]),
            "wo_type": w["wo_type"], "priority": w["priority"],
            "asset_id": w["asset_id"], "technician_id": w["technician_id"],
            "labor_hours": w["labor_hours"], "parts_used": w["parts_used"],
            "narrative": narratives[w["wo_id"]],
            "resolution_code": w["resolution_code"],
            "estimated_lost_production_mwh": w["estimated_lost_production_mwh"],
        })
        assert set(wo_rows[-1]) == set(WO_FIELDS), "allowlist mismatch"

    def write_json(name, obj):
        p = os.path.join(outdir, name)
        with open(p, "w") as f:
            json.dump(obj, f, indent=1, ensure_ascii=False)
        return p

    paths = [
        write_json("work_orders.json", wo_rows),
        write_json("sites.json", site_rows),
        write_json("assets.json", asset_rows),
        write_json("technicians.json", tech_rows),
    ]

    csv_path = os.path.join(outdir, "work_orders.csv")
    with open(csv_path, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=WO_FIELDS)
        wr.writeheader()
        for r in wo_rows:
            wr.writerow({k: ("" if r[k] is None else r[k]) for k in WO_FIELDS})
    paths.append(csv_path)

    # ---- second line of defence: byte scan for generator-internal tokens ----
    problems = []
    for p in paths:
        blob = open(p).read()
        for tok in FORBIDDEN_CORPUS_TOKENS:
            if tok in blob:
                problems.append((os.path.basename(p), tok))
    if problems:
        raise SystemExit(f"FORBIDDEN TOKEN IN CORPUS: {problems}")

    manifest = {
        "operator": OPERATOR_NAME,
        "corpus_version": CORPUS_VERSION,
        "master_seed": MASTER_SEED,
        "work_orders": len(wo_rows),
        "sites": len(site_rows),
        "registered_assets": len(asset_rows),
        "technicians": len(tech_rows),
        "window": {"start": "2024-07-01", "end": "2026-06-30"},
        "files": {},
    }
    for p in paths:
        manifest["files"][os.path.basename(p)] = hashlib.sha256(
            open(p, "rb").read()).hexdigest()
    write_json("MANIFEST.json", manifest)
    return manifest
