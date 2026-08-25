# Synthetic Solar O&M Field Report Corpus

A corpus of 2,398 utility-scale solar O&M work orders across a fictional 34-site,
6.1 GW fleet, containing four deliberately planted findings. Built to demonstrate
fleet-wide pattern detection.

**Every manufacturer, model, site and person in this corpus is invented.**

```
corpus/     ← the ONLY directory a detection pipeline may read
eval/       ← ground truth and audits. NEVER expose this to the pipeline.
generator/  ← the build
pipeline/   ← the four-stage detection pipeline
demo/       ← reference runs, scoring, runbook
demo_ui/    ← Field Intelligence — the browser demo
.checkpoints/  resumable generation state (committed: the narratives live here)
```

## Field Intelligence — the browser demo

A local, customer-facing view of the analysis. Open a terminal and run:

```bash
cd <this folder>
python3 demo_ui/serve.py
```

Your browser opens at **http://127.0.0.1:8000**. Press `Ctrl-C` in the terminal
to stop it.

No installation, no build step, no internet connection required. It uses only
the Python standard library and reads the committed results in
`demo/live_run/`.

**Optional live Claude Q&A.** Each finding page has an *Ask Claude about this
finding* panel. It works only if an API key is present:

```bash
set -a && . ./.env && set +a && python3 demo_ui/serve.py
```

Without a key the rest of the application is fully functional and the panel
says so. Set `ANTHROPIC_MODEL` to change the model (default `claude-opus-5`).

Press `Shift+D` for Demo Mode — a step strip along the bottom that walks the
intended presentation order.

The UI never reads `eval/`, never recomputes a finding, never asks a model for
a dollar figure, and never writes to disk.

**`demo/live_run/` is immutable.** It holds the committed model outputs the
project is evidenced on. Replay it with `python3 demo/replay.py`, which writes
to a scratch directory and verifies the source of truth is untouched. Never
point `pipeline.run --out` at it. To check at any time:

```bash
python3 demo/verify_immutable.py
```

Run time of the analysis is **20.3 minutes** (1,217.2s), the measured total of
the two invocations that made live model calls. It is recorded in
`demo/live_run/run_manifest.json` under `runtime`, with the per-run breakdown
and the archived stdout of both runs under `demo/live_run/provenance/`.


## corpus/

| File | |
|---|---|
| `work_orders.json` / `.csv` | 2,398 work orders. No labels, no flags, no hints. |
| `sites.json` | 34 sites: capacity, COD, O&M contract start, equipment. |
| `assets.json` | Serial-level registry of 1,378 central inverters, **including units that never generated a work order**. |
| `technicians.json` | 28 technicians. |
| `DATA_DICTIONARY.md` | Every field, and the export's quirks. Read first. |
| `MANIFEST.json` | Seed and SHA-256 of every file. |

## eval/ — do not let the pipeline near this

`GROUND_TRUTH.md` (narrative), `ground_truth.json` (work-order ID lists),
`AUDIT_REPORT.md` (self-audit output), `audit/` (the audit scripts).

## Reproducing

```bash
python3 generator/emit_corpus.py          # rebuild corpus/ from seed + checkpoints
python3 generator/check_alignment.py      # verify narratives match their work orders
cd eval/audit && python3 audit_frequency.py && python3 audit_aggregation.py \
                 && python3 audit_leakage.py
python3 eval/audit/sample_narratives.py 20
```

Master seed **20260824**. Every structured field is a deterministic function of
that seed (stdlib `random.Random`, stable across CPython versions; numpy and
sklearn are used only in `eval/`, never in generation). Narrative text was
authored separately in 20 stratified batches and is fixed by the committed
checkpoints in `.checkpoints/`, not by the seed alone — so the corpus is
reproducible as published, but re-running generation from scratch would not
re-derive the prose.
