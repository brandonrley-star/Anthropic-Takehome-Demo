# Field Intelligence

An AI-assisted fleet intelligence demo: a four-stage Claude pipeline reads 2,398
unstructured solar O&M technician reports across a synthetic 34-site, 6.1 GW
fleet and returns three kinds of answer — **escalate, deprioritize, or decline** —
each with a dollar figure, an exposed-asset count, a named commercial action, and
citations back to the field reports that support it. The whole environment is
invented; the analysis that produced the findings is a real Claude model run,
costing $30.86 and 20.3 minutes, whose outputs are committed to this repository.

### ▶ [Open the live demo](https://brandonrley-star.github.io/Anthropic-Takehome-Demo/)

### 🎥 Walkthrough video

_Loom link to be added._

---

## Run it locally (adds live Claude Q&A)

```bash
python3 demo_ui/serve.py
```

Opens at `http://127.0.0.1:8000`. Python 3.11+, no installation, no build step,
no dependencies beyond the standard library. `Ctrl-C` stops it.

Or **double-click `Launch-Demo.command`** (macOS) / **`Launch-Demo.bat`** (Windows).

The local version adds one feature the hosted version cannot have: *Ask Claude
about this finding*, a live, bounded question against a single finding and only
the work orders it cites. It needs an API key:

```bash
set -a && . ./.env && set +a && python3 demo_ui/serve.py
```

Without a key everything else is fully functional.

---

## What is real and what is not

| | |
|---|---|
| **The fleet** | Synthetic. Every site, manufacturer, model, technician and work order is invented. No real company's operational data appears anywhere. |
| **The analysis** | A real `claude-opus-5` run — 2,388 extraction calls plus 64 reasoning calls, $30.86, 20.3 minutes. Outputs committed under `demo/live_run/`. |
| **The hosted site** | A replay of those committed outputs. **No model calls are made by the hosted static site.** |
| **Financial figures** | Deterministic code, not model output. The model supplies quantities; `pipeline/cost_model.py` applies costs from stated assumptions. |
| **Live Claude Q&A** | Local only. |

---

## Why `eval/GROUND_TRUTH.md` is public on purpose

This repository contains its own answer key, and that is deliberate.

The corpus has planted findings — real signals, decoys that look meaningful but
are benign, and real-but-minor patterns that should be deprioritised rather than
escalated. Publishing the key lets anyone check the scoring in
`demo/SCORING.md` instead of taking my word for it.

The detector never saw it:

- `pipeline/paths.py` raises `PermissionError` on any read under `eval/`. It is
  blocked in code, not by convention.
- Ground truth was opened once, **after** the code freeze at commit `27e37cf`,
  from outside the pipeline.
- **The commit order in git is the proof.** `27e37cf` freezes the pipeline;
  `a12ecac` adds the scoring. Nothing under `pipeline/` changed between them.

A detector built while looking at the answers is not a detector. The sequence is
verifiable rather than asserted.

---

## How the repository is organised

```
corpus/     the ONLY directory the detection pipeline may read
eval/       ground truth and audits — the pipeline is code-blocked from this
generator/  how the synthetic corpus was built
pipeline/   the four-stage detection pipeline
demo/       committed model runs, three-tier scoring, presenter runbook
demo_ui/    Field Intelligence — the browser application
docs/       the static build published to GitHub Pages
```

`demo/live_run/` is **immutable** — it holds the committed model outputs this
project is evidenced on. Replay it with `python3 demo/replay.py`, which writes to
a scratch directory and verifies the source of truth is untouched. Check at any
time with `python3 demo/verify_immutable.py`.

The browser UI never reads `eval/`, never recomputes a finding, never asks a
model for a dollar figure, and never writes to disk. `Shift+D` toggles Demo Mode,
a step strip that walks the intended presentation order.

To regenerate the hosted static site after changing anything:

```bash
python3 demo_ui/export_static.py    # rewrites docs/ from the same data the local app serves
```

Analysis run time is **20.3 minutes** (1,217.2s), the measured total of the two
invocations that made live model calls, recorded in
`demo/live_run/run_manifest.json` under `runtime` with the archived stdout of
both runs under `demo/live_run/provenance/`.

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
