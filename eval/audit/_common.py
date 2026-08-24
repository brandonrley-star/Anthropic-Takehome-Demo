import os as _os, sys as _sys
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_sys.path.insert(0, _os.path.join(_ROOT, "generator"))
_sys.path.insert(0, _os.path.join(_ROOT, "eval", "audit"))

import sys, json
import narrate, fleet


def load():
    sites, assets, techs, wos = narrate.load_all()
    nar = narrate.load_narratives()
    for w in wos:
        w["narrative"] = nar.get(w["wo_id"], "")
        w["site_name"] = w["site"]["site_name"]
        w["region"] = w["site"]["region"]
    return sites, assets, techs, wos


def corpus():
    with open(_os.path.join(_ROOT, "corpus", "work_orders.json")) as f:
        return json.load(f)
