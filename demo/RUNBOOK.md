# Demo runbook

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

```bash
python3 -m pipeline.run --stage1-backend rules --backend authored --out demo/reference_run
```

Prints stage-by-stage progress and a cost/time table, then writes the report.

```bash
less demo/reference_run/report.txt
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

- **COMMERCIAL SUMMARY** — de-duplicated totals. Three of the escalated
  findings are three severity stages of *one* cohort fault, so their
  $3.6M replacement exposure is counted **once**, not three times. Say this
  out loud; a VP will check it.
- **ESCALATED (3)** — every finding leads with cost incurred, assets
  exposed, warranty recoverable, and the action. Technical evidence sits
  underneath. Each one is paste-able into an email.
- **REAL BUT DEPRIORITISED (6)** — confirmed real, with the impact estimate
  that justifies not acting. The tracker-logging finding costs more in
  absolute terms ($52k) than two of the escalated findings, and is still
  deprioritised, because there is no supplier exposure and no population
  failing ahead of expectation.
- **EXAMINED AND DECLINED (6)** — the storm-damage cluster at Sundowner Mesa
  is 20 tickets in six weeks and looks exactly like a tracker defect until
  you read the narratives and find a property-claim number. **The declined
  category renders as a result, not as an absence.** This is the single most
  important slide for a technical audience: it is evidence the system can be
  wrong in the safe direction.

### The headline finding

> 74 Kelvara KVP-3600 inverters from one 2024 build window are failing
> thermally while still inside parts warranty.

Derived only from what the pipeline saw: every affected serial decodes to a
2024 manufacture week between 18 and 36, the installed base holds 74 units in
that window, 16 have already presented, two units recur with escalating
severity on the same serial, and peer models co-located at the same sites show
zero equivalent tickets.

$78k–$115k already spent. $44,820 potentially recoverable from the supplier.
58 units not yet failed.

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

1. **Stage 1 runs on the `rules` backend in the reference run**, not a model.
   It leaves 24.7% of symptoms unclassified and finds `outcome=no_change` on
   exactly 1 of 2,398 tickets. The report prints this in the EXTRACTION
   QUALITY block rather than hiding it. Efficacy-decay detection depends on
   that field, so it currently has almost nothing to work with. This is the
   single highest-leverage fix and it is a backend flag, not a rewrite:
   `--stage1-backend anthropic`.
2. **Stages 3 and 4 replay authored responses** in the reference run, so it is
   reproducible and demo-safe but is not a live measurement of model
   judgment. `--backend anthropic` runs it live.
3. **Cost figures are a model of cost, not observed cost.** Every assumption
   — $95/h loaded labour, $450 per truck roll, $42/MWh, per-part prices — is
   printed at the bottom of the report with its rationale. Change the number,
   change the finding. That is deliberate: a customer will want to substitute
   their own rates.
4. **The 14% lost-production reporting rate** drives the upper bound on every
   energy figure. It is an assumption about reporting discipline, and it is
   the most fragile number in the model.

---

## Live-model variants

```bash
# live reasoning stages, cached extraction
python3 -m pipeline.run --stage1-backend rules --backend anthropic --out /tmp/live

# everything live (costs ~$14, takes ~5 min)
python3 -m pipeline.run --stage1-backend anthropic --backend anthropic \
    --model claude-opus-5 --concurrency 16 --budget 20 --out /tmp/full
```

Requires `ANTHROPIC_API_KEY` and `pip install anthropic`. `--budget` is a hard
stop in dollars.

---

## What never happens

The pipeline cannot read `eval/`. This is enforced in code, not by
convention — `pipeline/paths.py` raises `PermissionError` on any path under
`eval/`. That directory holds the ground truth for this corpus. A detector
built while looking at the answers is not a detector.
