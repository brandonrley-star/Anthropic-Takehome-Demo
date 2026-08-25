# Demo runbook

## Two reference runs — do not confuse them

| | `demo/reference_run/` | `demo/live_run/` |
|---|---|---|
| **Stage 1** | `rules` — deterministic stand-in, **no model** | `claude-opus-5`, 2,398 live calls |
| **Stages 3-4** | `authored` — human-written responses replayed | `claude-opus-5`, 62 live calls |
| Candidates | 43 generated, 15 examined | 71 generated, **31 examined** |
| Unclassified symptoms | 24.7% | **6.9%** |
| Outcome | 3 escalate / 6 deprioritise / 6 decline | **6 escalate / 5 deprioritise / 20 decline** |
| Cost to produce | $0.00 | **$37.10** across two runs |
| Reproduces offline | yes, in 0.4s | yes, from `demo/live_run/cache/` |

**`reference_run` is the demo-safe skeleton.** It proves the pipeline shape end
to end with no API key, no network and no spend. Its findings are *authored by
hand*, so it demonstrates the machinery, not model judgment.

**`live_run` is the real result.** Every extraction and every verdict came from
`claude-opus-5`. This is the one to show and to defend. Its Stage 1, 3 and 4
responses are committed under `demo/live_run/cache/`, so it replays for free.

Never present `reference_run`'s findings as model output. Never present
`live_run` as something that runs instantly — it took 20 minutes and $37 to
produce, and only replays quickly because the responses are committed.


Two things to show, in this order. The first sets up why the second is
credible. Total live runtime is under a second — **nothing in this demo
depends on a live API call.**

---

## Before you start

```bash
cd <repo root>
python3 --version        # 3.11+
```

No dependencies to install for the reference path. No API key required.
No network. Every path resolves from `__file__`, so the repo runs from
any directory.

---

## Act 1 — the denominator problem (30 seconds)

```bash
python3 demo/01_naive_ranking.py
```

**What to say while it runs:** "Everyone ranks sites by ticket count. Ticket
count measures how big a site is and how long it's been under contract. It
barely measures how the site is running."

**What to point at in the output:**

| | |
|---|---|
| Raw #1 | Sundowner Mesa, 140 tickets, 220 MWdc |
| Normalised #1 | Blackfoot Draw, 43.7 tickets/GW-month — **raw rank 24 of 34** |
| Biggest move down | Sawgrass Reach, raw 12 → normalised 33 |

The site with the worst reliability rate in the fleet sits in the bottom
third of the count ranking. A site in the top half of the count ranking is
actually one of the healthiest. **Raw counts mislead in both directions.**

Land it: "Every count in the detection pipeline is normalised on this basis.
Exposure is `max(window start, O&M contract start, COD)` to window end,
times site capacity. Same function, one place in the code — the demo and the
detector cannot disagree."

---

## Act 2 — the pipeline (1 minute)

Show the **live** run. It is the real result.

```bash
less demo/live_run/report.txt
```

To re-run it from the committed cache (free, no API key, a few seconds):

```bash
cp demo/live_run/cache/*.jsonl .pipeline_cache/
python3 -m pipeline.run --stage1-backend anthropic --backend anthropic --out demo/live_run
```

The demo-safe skeleton, if you need a run that touches nothing:

```bash
python3 -m pipeline.run --stage1-backend rules --backend authored --out demo/reference_run
```

### The four stages, in one sentence each

1. **Extract** — one call per work order turns a free-text narrative into
   closed-vocabulary fields. Deterministic pre-pass pulls equipment tags,
   serial attributes and firmware versions with regex; the model handles the
   judgment fields.
2. **Aggregate** — no model calls at all. Groups extractions along five
   occurrence dimensions plus an efficacy-decay dimension, normalises every
   count by exposure, joins the asset registry for installed-base
   denominators, and ranks candidates by `volume × anomaly`.
3. **Hypothesise** — for each surviving candidate, generates 2–4 competing
   explanations. **At least one must be benign.** A pipeline that can only
   produce "this is a defect" is a confirmation-bias engine.
4. **Verify** — tests each hypothesis against member narratives *and* a
   matched control set (same site, same equipment, same season). Can return
   `decline`.

### The three output categories

Scroll to each. This is the part that separates a detector from a keyword
search.

- **COMMERCIAL SUMMARY** — de-duplicated totals across 6 escalated findings:
  $232,909-$287,656 already incurred, 262 units exposed, $16.2M replacement
  exposure, $122,850 of warranty recovery in play. Exposure is counted once per
  physical population, never summed across findings that share a fleet.
- **ESCALATED (6)** — each leads with cost, exposure, warranty and the action.
  Paste-able into an email.
- **REAL BUT DEPRIORITISED (5)** — confirmed real, with the impact estimate that
  justifies not acting.
- **EXAMINED AND DECLINED (20)** — two thirds of everything examined. **The
  declined category renders as a result, not an absence.**

### The two findings to actually show

**1. The pipeline declining its own top-ranked cohort.** Candidate rank 3 is
"KVP-3600 manufactured 24Q2, 53 units, lift 2.57" — the single most materially
ranked equipment cluster in the fleet. Stage 4 **declined it**:

> The controls look like the members. WO-2026-00571 (week 20, in-cohort)
> against control WO-2026-00586 (week 27, one week outside the Q2 boundary):
> near-identical afternoon thermal derate, OEM case opened, filters clear, all
> fans turning — the control narrative is actually the more detailed of the two.

Meanwhile rank 6 — the *adjacent quarter*, 24Q3, 44 units — **escalated**,
because there the members share one causal chain (low airflow with clean
filters → afternoon derate → power-stage thermal damage) and two assets at two
different sites show the identical 'IGBT module 2, busbar heat marked'
signature.

Same generator, adjacent build quarters, opposite verdicts, each justified by
named work orders. That is the strongest evidence on the table that this
discriminates rather than pattern-matches.

**2. Efficacy decay — the pattern occurrence-counting cannot see.** Caprock
Mesa, rank 17:

> Washing blocks B01 and B03 now returns about 1-2% instead of the historical
> ~5%, with technicians confirming clean glass and re-washing to no effect — the
> remaining deficit is likely not soiling and warrants a module diagnostic
> before further wash spend.

No cluster of failures exists here. The signal is *declining benefit from a
repeated intervention*, and it is invisible to any method that counts events.
It requires `outcome` and `quantified_benefit_pct` from Stage 1 — fields the
rules backend produced on 1 ticket out of 2,398, which is why this pattern is
completely absent from `reference_run`.

---

## If someone asks about cost and time

The bottom of the report carries a per-stage table: calls, cache hits, input
and output tokens, USD and wall-clock seconds. The reference run is $0.00
because Stages 3 and 4 replay cached, authored responses.

A live run with real API calls, measured against corpus size (387,051
narrative characters, ~102 tokens per ticket):

| Stage | Model | Cost | Notes |
|---|---|---|---|
| 1 — extract, 2,398 calls | `claude-opus-5` | ~$11 | ~$4.50 on Sonnet 5, ~$2 on Haiku 4.5; halved again via the Batch API |
| 2 — aggregate | none | $0 | deterministic |
| 3 + 4 — reason, ~30 calls | `claude-opus-5` | ~$3 | |
| **Full run** | | **$5–15** | ~5 min at 16-way concurrency, ~80 min sequential |

---

## Known weaknesses — say these before you are asked

1. **Cost estimation was wrong by 2x.** I projected $14 for the full live run;
   it cost $29.56, then $7.54 more to re-run stages 2-4 after two Stage 2 fixes.
   Total $37.10. The error was in measuring Stage 1 output tokens by
   re-tokenizing the stored parsed JSON, which strips whitespace and undercounts
   the model's actual emission by 2.6x (132 vs 339 tokens/ticket). The per-stage
   accounting in the report is measured, not estimated.
2. **Cost figures are a model of cost, not observed cost.** Every assumption -
   $95/h loaded labour, $450 per truck roll, $42/MWh, per-part prices - is
   printed at the bottom of the report with its rationale. Change the number,
   change the finding. A customer will want to substitute their own rates.
3. **The 14% lost-production reporting rate** drives the upper bound on every
   energy figure. It is an assumption about reporting discipline and it is the
   most fragile number in the model.
4. **Serial cohorts use calendar quarters.** The Kelvara build window spans
   weeks 18-36, which straddles a quarter boundary, so it surfaces as two
   candidates (24Q2 and 24Q3) rather than one. Both rank top-6 so nothing is
   lost, but a sliding window would be cleaner.
5. **Confidence is self-reported by the model.** It is not calibrated against
   outcomes. Treat 'high' as 'the evidence in front of it was consistent', not
   as a probability.

## Live-model variants

Credentials live in `.env` at the repo root, which is gitignored and never
committed. Load it into the shell first:

```bash
set -a && . ./.env && set +a
```

```bash
# live reasoning stages, cached extraction
python3 -m pipeline.run --stage1-backend rules --backend anthropic --out /tmp/live

# everything live (costs ~$14, takes ~5 min)
python3 -m pipeline.run --stage1-backend anthropic --backend anthropic \
    --model claude-opus-5 --concurrency 16 --budget 20 --out /tmp/full
```

Requires `pip install anthropic` (SDK 1.0.0 is present in this environment).
`--budget` is a hard stop in dollars.

**Do not run a live variant during the demo.** Use the reference run. The live
path exists to regenerate the reference run, not to perform in front of an
audience — it takes minutes, costs money, and depends on the network.

---

## What never happens

The pipeline cannot read `eval/`. This is enforced in code, not by
convention — `pipeline/paths.py` raises `PermissionError` on any path under
`eval/`. That directory holds the ground truth for this corpus. A detector
built while looking at the answers is not a detector.

### Ground truth was read only after the code freeze

`eval/ground_truth.json` was opened for the first time **after** the pipeline
was frozen and committed at **`27e37cf`** ("Live reference run; fix
serial-cohort grouping, budget, and cache keying"), and was read outside the
pipeline — `pipeline/paths.py` still refuses it.

Nothing under `pipeline/`, `corpus/`, or `generator/` was modified after that
read. Both reference runs in `demo/` were produced before it. The three-tier
scoring in `demo/SCORING.md` is therefore a post-freeze evaluation of a
detector that never saw the answers, not a detector tuned against them.

Weaknesses that scoring exposed are written up in `demo/SCORING.md` as
findings. They were deliberately **not** acted on, because fixing them after
reading the key would destroy exactly the property the freeze protects.
