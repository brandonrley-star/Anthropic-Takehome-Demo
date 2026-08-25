#!/usr/bin/env python3
"""
Export the read-only API surface to a self-contained static site in docs/.

    python3 demo_ui/export_static.py

Why this is faithful: it imports demo_ui.data — the exact module the local
server calls — and serialises the return value of each endpoint function. It
does not re-read, reinterpret or recompute anything. If the local app and the
static build ever disagree, this file is not the reason.

What it never touches: demo/live_run, corpus/, pipeline/, generator/, eval/.
It reads demo_ui/data.py (which reads live_run and corpus) and writes only
under docs/.

Output layout, all relative so it works under https://user.github.io/<repo>/:

    docs/index.html          window.FI_STATIC = true injected
    docs/app.css  app.js     copied verbatim
    docs/.nojekyll           stop Pages running Jekyll over it
    docs/api/*.json          one file per endpoint
    docs/api/finding/*.json
    docs/api/work_order/*.json
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from demo_ui import data  # noqa: E402

DOCS = os.path.join(ROOT, "docs")
STATIC_SRC = os.path.join(HERE, "static")

# Protected: read-only inputs. Asserted untouched at the end.
PROTECTED = ("demo/live_run", "corpus", "pipeline", "generator", "eval")


def write(rel, obj):
    p = os.path.join(DOCS, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        json.dump(obj, f, separators=(",", ":"))
    return os.path.getsize(p)


def main():
    if os.path.isdir(DOCS):
        shutil.rmtree(DOCS)
    os.makedirs(os.path.join(DOCS, "api"))

    total = 0
    total += write("api/overview.json", data.overview())
    total += write("api/provenance.json", data.provenance())
    total += write("api/baseline.json", data.baseline_ranking())
    findings = data.findings_list()
    total += write("api/findings.json", findings)

    # The Ask feature is inert in a static build. Ship a status file saying so
    # rather than letting the fetch 404 and fall into an error path.
    total += write("api/ask_status.json",
                   {"available": False, "model": None, "static_build": True})

    # Every finding, and every work order any finding can reach from the UI:
    # its cluster members, its cited evidence, and the fixed IDs the two
    # comparison panels open directly.
    wo_ids = set()
    for card in findings:
        cid = card["candidate_id"]
        d = data.finding_detail(cid)
        total += write(f"api/finding/{cid}.json", d)
        wo_ids.update(d["supporting_wo_ids"])
        wo_ids.update(d["members"])
    wo_ids.update(["WO-2026-00571", "WO-2026-00586"])          # 24Q2 comparison
    wo_ids.update(["WO-2025-00810", "WO-2024-00049", "WO-2024-00145",
                   "WO-2024-00194", "WO-2025-00715", "WO-2025-00856",
                   "WO-2025-01057", "WO-2026-00620"])           # wash panel
    for w in sorted(wo_ids):
        rec = data.work_order(w)
        if rec:
            total += write(f"api/work_order/{w}.json", rec)

    # Front end, copied verbatim except for the static flag.
    for name in ("app.css", "app.js"):
        shutil.copy2(os.path.join(STATIC_SRC, name), os.path.join(DOCS, name))
    html = open(os.path.join(STATIC_SRC, "index.html")).read()
    html = html.replace('href="/static/app.css"', 'href="app.css"')
    html = html.replace('src="/static/app.js"',
                        'src="app.js"').replace(
        "<script src=", '<script>window.FI_STATIC=true;</script>\n<script src=')
    open(os.path.join(DOCS, "index.html"), "w").write(html)
    open(os.path.join(DOCS, ".nojekyll"), "w").close()

    n = sum(len(f) for _, _, f in os.walk(DOCS))
    print(f"  docs/  {n} files, {total/1024:.0f} KB of JSON")
    print(f"  findings {len(findings)}  work orders {len(wo_ids)}")

    # Guarantee the export changed nothing it reads from.
    import subprocess
    d = subprocess.run(["git", "status", "--porcelain", "--"] + list(PROTECTED),
                       cwd=ROOT, capture_output=True, text=True)
    dirty = [l for l in d.stdout.splitlines() if l.strip()]
    if dirty:
        sys.exit("  FAIL — export modified protected paths:\n    "
                 + "\n    ".join(dirty))
    print("  protected paths unmodified: " + ", ".join(PROTECTED))


if __name__ == "__main__":
    main()
