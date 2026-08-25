# Three-tier scoring against ground truth

**Ground truth (`eval/ground_truth.json`) was read for the first time after the
code freeze at commit `27e37cf`.** Nothing under `pipeline/`, `corpus/`, or
`generator/` was modified afterwards. Both reference runs predate the read.

Recall is the fraction of a planted finding's work orders covered by clusters
the tier surfaced. Every score cites the candidate ID or finding text that
justifies it, so it can be re-verified without reading the key.

## The three tiers

| Tier | What it is | Cost |
|---|---|---|
| **T1 raw aggregation** | Rank sites by ticket count and equipment model by ticket count; act on the top 10 of each. No exposure normalisation, no extraction, no verification. Everything surfaced is implicitly escalated — there is no decline path. | $0 |
| **T2 rules + authored** | `demo/reference_run` — deterministic regex extraction, full 4-stage pipeline, hand-authored reasoning. | $0 |
| **T3 live** | `demo/live_run` — `claude-opus-5` throughout, 2,398 extraction calls + 62 reasoning calls. | $30.86 |

## Scorecard

| # | Rubric item | Required outcome | T1 raw | T2 rules+authored | T3 live |
|---|---|---|---|---|---|
| 1 | `signal_1_kelvara_thermal`<br>TRUE SIGNAL (strong), 48 WOs | detect **and escalate** | ⚠️ **94% recall, escalated for the wrong reason** | ✅ **65% recall, escalated** | ✅ **98% recall, escalated** |
| 2 | `signal_2_caprock_backsheet`<br>TRUE SIGNAL (weak), 26 WOs | detect | ❌ **site surfaced, mechanism missed** | ❌ **0% — not detected at all** | ⚠️ **54% recall, escalated, mechanism half-named** |
| 3 | `decoy_1_sundowner_wind`<br>DECOY, 31 WOs | must **NOT** be called systemic | ❌ **escalated as fleet's #1 problem** | ✅ **declined ×3 + 1 deprioritised** | ✅ **declined ×4, unanimous** |
| 4 | `decoy_2_normalization`<br>DECOY | must **NOT** produce a false ranking | ❌ **trap site ranked 24/34** | ✅ **trap site ranked 1/34** | ✅ **trap site ranked 1/34** |
| 5 | `distractor_slew_drive`<br>REAL but minor, 38 WOs | must be **deprioritised** | ❌ **escalated** | ✅ **deprioritised ×4** | ⚠️ **1 deprioritised, 3 declined** |
| 6 | `distractor_comms`<br>REAL but minor, 44 WOs | must be **deprioritised** | ❌ **escalated ×3** | ⚠️ **14% recall, deprioritised** | ⚠️ **14% recall, deprioritised** |
| | **Passed** | | **0 / 6** | **3.5 / 6** | **4 / 6** |

## Audit trail — every score above, justified

### 1. Kelvara thermal defect (strong signal, must escalate)

- **T1 — ⚠️** `RAW-MODEL-KVP-3600/CM` overlaps 41 of 48. High recall, but it is
  simply "the most common model has the most tickets." KVP-3600 is the largest
  installed model in the fleet, so this bucket would rank first whether or not a
  defect existed. It carries no build window, no rate per unit, no baseline —
  and no way to distinguish itself from item 5 and 6, which it escalates too.
- **T2 — ✅** `CAND-011` (overtemperature_trip, ov=9), `CAND-002`
  (component_thermal_damage, ov=8), `CAND-010` (thermal_derate, ov=7) all
  escalated; `CAND-014` (cooling_airflow_low, ov=7) deprioritised. Recall 31/48.
  The symptom-by-symptom split is why recall caps at 65%.
- **T3 — ✅ best score.** `CAND-006` "KVP-3600 manufactured 24Q3 (44 units)"
  escalated with ov=22, plus `CAND-002` and `CAND-014` escalated. Recall 47/48.
  The serial-cohort regrouping is what produced the large-overlap clusters.
  **Caveat, stated plainly:** `CAND-003` (24Q2, ov=25) was **declined** — the
  single largest true-signal cluster in any tier was rejected. Its stated reason
  is sound on the evidence shown ("the controls look like the members… WO-2026-00571
  week 20 in-cohort vs control WO-2026-00586 week 27, near-identical") but the
  control set was drawn from the same defective population, which is a
  methodological weakness, not a reasoning error. See Finding A below.

### 2. Caprock backsheet degradation (weak signal — the hard one)

Ground truth: backsheet degradation on Pinnacle PS-500M modules, which the site
reads as soiling and vegetation. **No work order states a diagnosis.**

- **T1 — ❌** Caprock Mesa is raw rank 2 of 34, so the *site* surfaces — but T1
  produces a site name and a ticket count. It cannot say what is wrong, and the
  ranking is driven by site size, not by the defect.
- **T2 — ❌ complete miss, 0/26.** The rules extractor returned
  `partial_improvement` on **0** of 2,398 tickets, so no efficacy-decay cluster
  scored above the examination threshold. This finding is structurally invisible
  to T2.
- **T3 — ⚠️ detected and escalated, mechanism half-named.** `CAND-017` covers 10
  of the 26 (all from the `cleaning_benefit_decay` thread), escalated:

  > "Washing blocks B01 and B03 now returns about 1–2% instead of the historical
  > ~5%, with technicians confirming clean glass and re-washing to no effect — the
  > remaining deficit is likely **not soiling** and warrants a module diagnostic
  > before further wash spend."

  Recommended action: "IV-curve sampling plus EL or handheld IR on representative
  strings… to separate **irreversible optical/electrical loss** from wash cadence."

  It never says "backsheet." But it correctly rejects the site's own soiling
  reading and prescribes exactly the diagnostic that would find backsheet
  degradation. `CAND-026` picks up 4 more from the `rising_ground_fault_readings`
  thread but does not connect them. **No tier connected the five evidence threads
  into one finding.** See Finding B.

### 3. Sundowner wind decoy (must not be called systemic)

- **T1 — ❌ worst possible outcome.** Sundowner Mesa is raw rank **1 of 34**. A
  raw-count approach escalates the decoy as the fleet's number one reliability
  problem.
- **T2 — ✅** `CAND-001` declined, `CAND-005` (temporal burst) declined,
  `CAND-019` declined, `CAND-003` (TECH-0231 logging) deprioritised. 28/31 covered.
- **T3 — ✅ cleanest result on the board.** Four clusters, **all declined**:
  `CAND-004` (ov=27), `CAND-005` (ov=21), `CAND-001` (ov=20), `CAND-015` (ov=3).
  Both planted benign causes were separately identified — the microburst and the
  per-row logging habit.

### 4. Normalisation decoy (must not produce a false ranking)

Trap site: **Blackfoot Draw**, under contract only from 2025-10-01.

- **T1 — ❌** raw rank **24 of 34**. Reads as an unremarkable, healthy site.
- **T2 / T3 — ✅** exposure-normalised rank **1 of 34** — correctly the worst site
  in the fleet per GW-month of contracted coverage. Both tiers share
  `corpus_io.site_exposure_gw_months`, and `demo/01_naive_ranking.py` shows the
  inversion directly.

### 5. Slew-drive grease (real but minor — must be deprioritised)

- **T1 — ❌** escalates `RAW-SITE-Dry Creek Junction` with no severity judgment.
- **T2 — ✅ exactly right.** `CAND-007`, `CAND-008`, `CAND-009` all
  **deprioritised**, 23/38 covered.
- **T3 — ⚠️ over-corrected.** `CAND-008` deprioritised, but `CAND-007` (Ashvale)
  and `CAND-009` (Red Clay) were **declined**. The rubric asks for
  "real but deprioritised"; declining understates a real, if minor, pattern.
  Same recall as T2 (23/38), worse verdict placement. See Finding C.

### 6. Soltera comms dropouts (real but minor — must be deprioritised)

- **T1 — ❌** escalates three separate humid sites on ticket volume.
- **T2 — ⚠️** `CAND-015` (Palmetto Bend, reporting_dropout) deprioritised — correct
  verdict, but only 6 of 44 covered.
- **T3 — ⚠️** `CAND-011` (Coralito Flats, comms_loss) deprioritised — same 14% recall.

Both pipeline tiers get the *verdict* right and the *scope* wrong. The finding
spans six sites; both tiers saw it as one site's problem. Grouping is per-site,
so a low-rate pattern spread thinly across many sites never aggregates. See
Finding D.

## What the scoring says overall

**T1 scores zero.** It is not merely less accurate — it is actively
anti-correlated. It escalates the decoy first, misses the normalisation trap
entirely, and escalates both distractors. Every one of its "findings" is site
size or fleet share wearing a reliability costume. This is the strongest
argument in the deck for why the pipeline exists.

**T2 → T3 is a real but uneven gain.** T3 wins decisively on the two things that
matter most commercially — near-total recall on the strong signal (98% vs 65%),
and the only detection of the weak signal in any tier. It is slightly worse than
T2 on distractor placement, declining two clusters that should have been
deprioritised.

**The weak signal is the honest headline.** Caprock backsheet degradation is the
finding a human analyst would most plausibly miss: no work order names it, the
site's own interpretation is wrong, and it has no failure cluster to count. T1
and T2 do not find it at all. T3 finds it, escalates it, and prescribes the right
diagnostic — while never naming the mechanism and connecting only one of five
evidence threads.

## Findings — documented, deliberately not fixed

Fixing these after reading the key would destroy the property the freeze
protects. They are written down, not acted on.

**Finding A — controls are drawn from the same defective population.**
`matched_controls()` selects on same site / model / component / season. For a
model-wide manufacturing defect, the nearest neighbours are *other defective
units*, so the control set argues against the finding. This is what led T3 to
decline `CAND-003`. Fix: for serial-cohort candidates, force controls from
other manufacture windows of the same model.

**Finding B — no cross-thread synthesis.** Ground truth carries five distinct
evidence threads for Caprock (wash decay, SCADA underperformance, IR scans
called unremarkable, backsheet observations closed as cosmetic, rising ground
faults). Stage 2 generates one cluster per dimension and Stage 3 sees one
cluster at a time, so nothing can assemble them. This is an architectural
limit, not a tuning problem.

**Finding C — decline/deprioritise boundary is uncalibrated.** T3 declined two
clusters T2 correctly deprioritised. The Stage 4 prompt defines deprioritise as
"real but low financial impact" and decline as "not a systemic finding," but
offers no test for "real yet minor," so the model splits inconsistently.

**Finding D — thin, wide patterns never aggregate.** The comms distractor spans
six sites at low per-site rates. `site_symptom` fragments it below
`MIN_CLUSTER`; there is no equipment-model-across-sites generator for
non-serialised components. Both tiers cap at 14% recall for the same structural
reason.

**Finding E — recall is capped by symptom-level grouping.** Even at 98%, T3
spreads the Kelvara signal across four clusters with three different verdicts.
The cohort is one physical population; the report presents it as four findings.
