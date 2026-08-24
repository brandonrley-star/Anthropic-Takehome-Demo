# Synthetic Solar O&M Field Report Corpus

A corpus of 2,398 utility-scale solar O&M work orders across a fictional 34-site,
6.1 GW fleet, containing four deliberately planted findings. Built to demonstrate
fleet-wide pattern detection.

**Every manufacturer, model, site and person in this corpus is invented.**

```
corpus/     ← the ONLY directory a detection pipeline may read
eval/       ← ground truth and audits. NEVER expose this to the pipeline.
generator/  ← the build
.checkpoints/  resumable generation state (committed: the narratives live here)
```

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
