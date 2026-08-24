import sys
sys.path.insert(0, "/home/user/Anthropic-Takehome-Demo/generator")
import narrate, emit, json

sites, assets, techs, wos = narrate.load_all()
nar = narrate.load_narratives()
missing = [w["wo_id"] for w in wos if w["wo_id"] not in nar]
if missing:
    raise SystemExit(f"{len(missing)} work orders without narratives: {missing[:5]}")
m = emit.emit(sites, assets, techs, wos, nar)
print(json.dumps({k: v for k, v in m.items() if k != "files"}, indent=1))
for k, v in m["files"].items():
    print(f"  {k:22s} {v[:16]}")
