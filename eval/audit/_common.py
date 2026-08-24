import sys, json
sys.path.insert(0, "/home/user/Anthropic-Takehome-Demo/generator")
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
    with open("/home/user/Anthropic-Takehome-Demo/corpus/work_orders.json") as f:
        return json.load(f)
