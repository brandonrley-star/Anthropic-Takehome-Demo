import sys, json
sys.path.insert(0, "/home/user/Anthropic-Takehome-Demo/generator")
import narrate
sites, assets, techs, wos = narrate.load_all()
b = int(sys.argv[1])
rows = narrate.dump_batch(wos, techs, b)
nb, done = narrate.status(wos)
sys.stderr.write(f"batch {b} of {nb} ({len(rows)} WOs); completed: {len(done)}\n")
for r in rows:
    print(json.dumps(r, ensure_ascii=False))
