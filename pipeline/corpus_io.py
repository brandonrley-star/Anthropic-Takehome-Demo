"""Corpus loading. Reads corpus/ and nothing else."""
import json, datetime
from . import paths

WINDOW_START = datetime.date(2024, 7, 1)
WINDOW_END = datetime.date(2026, 6, 30)


def _j(name):
    with open(paths.corpus_file(name)) as f:
        return json.load(f)


def load():
    wos = _j("work_orders.json")
    sites = {s["site_name"]: s for s in _j("sites.json")}
    assets = {a["asset_id"]: a for a in _j("assets.json")}
    techs = {t["technician_id"]: t for t in _j("technicians.json")}
    for w in wos:
        w["_d"] = datetime.date.fromisoformat(w["date_opened"])
    return wos, sites, assets, techs


def d(s):
    return datetime.date.fromisoformat(s) if s else None


def coverage_months(site):
    """Exposure window for a site: it must exist AND be under contract.
    This is the normalisation basis used everywhere a count is compared."""
    start = max(WINDOW_START, d(site["om_contract_start"]),
                d(site["commercial_operation_date"]))
    if start > WINDOW_END:
        return 0
    return max(1, (WINDOW_END.year - start.year) * 12
               + (WINDOW_END.month - start.month) + 1)


def site_exposure_gw_months(site):
    return site["capacity_mwdc"] / 1000.0 * coverage_months(site)
