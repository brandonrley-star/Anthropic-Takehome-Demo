"""
Pipeline orchestrator.

  python3 -m pipeline.run --stage1-backend rules --backend authored
  python3 -m pipeline.run --stage1-backend anthropic --backend anthropic   # needs a key
"""
import argparse, json, os, sys, time, datetime
from . import (paths, corpus_io, schema, stage1_extract as s1,
               stage2_cluster as s2, stage3_hypothesize as s3,
               stage4_verify as s4, render, cost_model)
from .llm import LLMClient, Accounting, DEFAULT_MODEL


def _ser(o):
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    raise TypeError(type(o))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage1-backend", default="rules",
                    choices=["rules", "authored", "anthropic"])
    ap.add_argument("--backend", default="authored", choices=["authored", "anthropic"],
                    help="backend for the reasoning stages (3 and 4)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--budget", type=int, default=15,
                    help="candidates carried into stages 3-4")
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--out", default=paths.REFERENCE_RUN)
    ap.add_argument("--authored-dir", default=None)
    ap.add_argument("--dump-pending", default=None,
                    help="write prompts with no authored response to this file")
    a = ap.parse_args(argv)

    os.makedirs(a.out, exist_ok=True)
    acct = Accounting()
    t_all = time.time()

    # ---------------------------------------------------------------- load
    t0 = time.time()
    wos, sites, assets, techs = corpus_io.load()
    wo_by_id = {w["wo_id"]: w for w in wos}
    acct.add_seconds("load_corpus", time.time() - t0)
    print(f"[load]    {len(wos)} work orders, {len(sites)} sites, {len(assets)} registered assets")

    # ------------------------------------------------------------- stage 1
    t0 = time.time()
    det = {w["wo_id"]: s1.deterministic(w, assets) for w in wos}
    for w in wos:
        w["_warranty_active"] = det[w["wo_id"]]["warranty_active_at_ticket"]
    acct.add_seconds("stage1_deterministic", time.time() - t0)

    ext, missing1 = {}, []
    if a.stage1_backend == "rules":
        t0 = time.time()
        for w in wos:
            ext[w["wo_id"]], _ = schema.validate(s1.rules_extract(w))
        acct.add_seconds("stage1_rules", time.time() - t0)
    else:
        client1 = LLMClient(backend=a.stage1_backend, model=a.model, accounting=acct,
                            authored_dir=a.authored_dir, concurrency=a.concurrency)
        raw, missing1 = client1.map("stage1_extract", wos, s1.build_prompt, max_tokens=900)
        for k, v in raw.items():
            ext[k], _ = schema.validate(v)
        for w in wos:                      # fall back so the run always completes
            if w["wo_id"] not in ext:
                ext[w["wo_id"]], _ = schema.validate(s1.rules_extract(w))
        if a.dump_pending and missing1:
            client1.dump_pending(a.dump_pending)
    print(f"[stage1]  extracted {len(ext)} records "
          f"({a.stage1_backend}{f', {len(missing1)} unauthored -> rules fallback' if missing1 else ''})")

    # ------------------------------------------------------------- stage 2
    t0 = time.time()
    recs = s2.build_records(wos, det, ext, sites, assets)
    quality = s2.extraction_quality(recs)
    cands, top = s2.run(recs, sites, assets, budget=a.budget)
    recs_by_id = {r["wo_id"]: r for r in recs}
    acct.add_seconds("stage2_cluster", time.time() - t0)
    print(f"[stage2]  {len(cands)} candidates, examining top {len(top)}")

    # ---------------------------------------------------------- stages 3-4
    client = LLMClient(backend=a.backend, model=a.model, accounting=acct,
                       authored_dir=a.authored_dir, concurrency=a.concurrency)
    hyp, miss3 = client.map("stage3_hypothesize", top,
                            lambda c: s3.build_prompt(c, recs_by_id, wo_by_id),
                            max_tokens=1600)
    print(f"[stage3]  {len(hyp)} hypothesis sets"
          + (f", {len(miss3)} unauthored" if miss3 else ""))

    ready = [c for c in top if c["candidate_id"] in hyp]
    ver, miss4 = client.map("stage4_verify", ready,
                            lambda c: s4.build_prompt(c, hyp[c["candidate_id"]],
                                                      recs, recs_by_id, wo_by_id, assets),
                            max_tokens=2200)
    print(f"[stage4]  {len(ver)} verdicts"
          + (f", {len(miss4)} unauthored" if miss4 else ""))

    if a.dump_pending:
        n = client.dump_pending(a.dump_pending)
        if n:
            print(f"[pending] {n} prompts needing authored responses -> {a.dump_pending}")

    # -------------------------------------------------------------- render
    results = {}
    by_cid = {c["candidate_id"]: c for c in top}
    for cid, v in ver.items():
        c = by_cid[cid]
        results[cid] = {"candidate": c, "hypotheses": hyp.get(cid, {}), "verdict": v,
                        "finance": render.finance(c, v, wo_by_id)}

    meta = {"work_orders": len(wos), "sites": len(sites),
            "window": "2024-07-01 to 2026-06-30",
            "stage1_backend": a.stage1_backend, "reasoning_backend": a.backend,
            "model": a.model, "candidates_total": len(cands),
            "candidates_examined": len(results)}
    acct.add_seconds("render", 0.0)
    report = render.render_report(results, wo_by_id, acct, quality, meta)

    with open(os.path.join(a.out, "report.txt"), "w") as f:
        f.write(report + "\n")
    with open(os.path.join(a.out, "candidates.json"), "w") as f:
        json.dump(cands, f, indent=1, default=_ser)
    with open(os.path.join(a.out, "findings.json"), "w") as f:
        json.dump({cid: {k: v for k, v in r.items()} for cid, r in results.items()},
                  f, indent=1, default=_ser)
    with open(os.path.join(a.out, "stage1_extractions.json"), "w") as f:
        json.dump({k: {**ext[k], **{"_deterministic": det[k]}} for k in ext},
                  f, indent=1, default=_ser)
    run_meta = {**meta, "extraction_quality": quality,
                "accounting": acct.summary(),
                "wall_clock_seconds": round(time.time() - t_all, 1),
                "generated_at_utc": datetime.datetime.utcnow().isoformat(timespec="seconds")}
    with open(os.path.join(a.out, "run_manifest.json"), "w") as f:
        json.dump(run_meta, f, indent=1, default=_ser)

    print(f"\n[done]    {round(time.time()-t_all,1)}s total -> {a.out}")
    print(acct.render())
    return 0 if not (miss3 or miss4) else 2


if __name__ == "__main__":
    sys.exit(main())
