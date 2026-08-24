# GROUND TRUTH — Northlight O&M Corpus v1.0.0

> **This file and everything else under `eval/` must never be read by the
> detection pipeline.** The pipeline's input is `corpus/` only. Contaminating it
> with this file invalidates the whole evaluation.

Master seed **20260824**. 2,398 work orders, 34 sites, 1,378 registered central
inverters, 28 technicians, window 2024-07-01 → 2026-06-30.

Machine-readable version with full work-order ID lists: `eval/ground_truth.json`.

---

## Finding 1 — TRUE SIGNAL (strong)

**Kelvara Power Systems KVP-3600 central inverters manufactured in weeks 18–36
of 2024** shipped with cooling-fan controller firmware **v4.2.1**, which fails to
ramp the fan bank aggressively enough under combined high ambient temperature and
high irradiance. The result is progressive thermal stress on the IGBT modules
and, in advanced cases, DC contactor welding.

| | |
|---|---|
| Work orders | **48** |
| Sites | **9** — Sandhill Bend, Hollowell Ranch, Pecan Fork, Bitter Draw, Tidemarsh Bay, Almond Row, Vireo Valley, Joshua Fork, Ashvale Dry Lake |
| Distinct units failing | 30 |
| Technicians involved | 15 |
| Apparent symptom types | 12 |
| Resolution codes used | 8 of 9 |
| Span | 2024-09-15 → 2026-06-30 |
| Max at any one site | 9 (Vireo Valley) |

**Population at risk** — derivable only by parsing serials and joining
`assets.json`:

| | |
|---|---|
| Defect-window units fleet-wide | **74** |
| At hot-region sites | 54 |
| At cool-region sites (no failures) | 20 |
| Sites holding them | **16** (only 9 show failures) |
| Units with failure history | 30 |
| **At risk, not yet failed** | **44** |
| Still inside parts warranty at window end | 74 |

**Observed cost floor:** 256.8 labour hours, 187.9 MWh of recorded lost
production. Lost production is populated on a minority of tickets, so the true
figure is higher.

**Severity progresses with cumulative thermal exposure, per unit.** 14 tickets
at stage 1 (overtemp trip, comms dropout, unexplained derate), 21 at stage 2
(low airflow, repeat trips, fan replacement, vendor call), 13 at stage 3 (IGBT
replacement, welded DC contactor, hard shutdown). 13 units were ticketed more
than once; four have three or more. **The per-unit escalation timeline is the
strongest single piece of true evidence in the corpus** and does not exist in
any single column.

**Firmware:** four narratives quote a revision on affected units (three say
`4.2.1`, one says "a 4.2.x build"). Roughly 26 further narratives across every
inverter model quote other revisions, so "narrative mentions firmware" is not a
useful filter on its own.

**Two unescalated hunches:** two technicians at different sites independently
wonder in writing whether fan control is ramping late. Neither escalates.

### Why a human misses it
Nine sites, 22 months, 15 technicians, 12 apparent symptoms. No site has enough
incidents to look systemic. Every ticket was closed correctly at the work-order
level.

### What the detection system should surface
1. The cluster exists and is scoped to a **manufacturing window**, not to the model.
2. Correlation with ambient heat and season (inferable from month + narrative language; there is deliberately no temperature column).
3. The firmware revision link.
4. Cumulative cost: truck rolls, parts, lost production.
5. **44 units at risk that have not failed yet.**
6. Two commercial actions: a warranty claim against Kelvara, and a proactive fleet-wide firmware remediation campaign scoped as billable corrective maintenance.

---

## Finding 2 — TRUE SIGNAL (weak)

**Caprock Mesa** (COD 2017, 180 MWdc, ERCOT West Texas) is losing output to
**backsheet degradation on its Pinnacle Solar PS-500M modules**, concentrated in
the older array sections (blocks B01–B04). The site reads it as soiling and
vegetation. **No work order states a diagnosis.**

26 work orders, all at this one site, rising in frequency: 4 / 4 / 8 / 10 across
the four half-years. 21 of 26 fall in the older blocks.

Five evidence threads, none conclusive alone:

| Thread | n | What it shows |
|---|---|---|
| Module washing | 10 | Recovery decays from ~4–5% early to "maybe half a percent" late, with coverage explicitly verified as good |
| SCADA underperformance | 5 | Strings soft across the board, no failed component, nothing to clear |
| IR scans | 4 | Scattered warm cells, each below reporting threshold, count rising between flights |
| Backsheet observations | 3 | Chalking / yellowing on older modules, closed as cosmetic |
| Ground fault readings | 4 | Elevated, reseating helps briefly, insulation resistance "low side of normal" |

### Why it's harder
Single site, so there is no cross-fleet pattern. The signal is a **trend in the
effectiveness of an intervention**, not a cluster of identical events. Getting
it requires connecting cleaning-benefit decay to the IR trend, the ground-fault
drift, and three throwaway cosmetic remarks.

### What the detection system should surface
Cleaning at this site shows declining marginal benefit while coverage quality is
verified — inconsistent with a soiling explanation. The physical observations fit
module degradation. Recommend a formal degradation assessment and open a
repowering / partial module replacement conversation with the owner. **Highest
commercial value in the corpus if confirmed.**

---

## Finding 3 — DECOY 1 (must NOT be flagged as systemic)

**Sundowner Mesa**, 31 tracker work orders between 2025-03-15 and 2025-04-28 —
a 3.3× spike over the site's baseline. It looks like an Auster Trackline H2
defect. It is not. Two benign causes are stacked:

1. **A microburst on 2025-03-14.** Named outright in three narratives ("wind gauge at the met station peaked around 71 mph"), referenced obliquely in eight more ("storm damage", "post event walkdown"). Two P1 tickets carry insurance claim ref **NRS-PL-2025-0417**.
2. **A reporting artifact.** TECH-0231 logs **one work order per tracker row**; his colleagues log one per zone. 21 of the 31 are his per-row tickets. Mean labour is 2.9 h on per-row tickets versus 8.6 h per-zone — roughly threefold inflation of the event count.

**The per-row habit is a standing practice, not an artifact of the event:**
TECH-0231 logs 16 further per-row tracker tickets outside the window. Other
technicians logged per-zone tracker work at this site throughout 2024, which is
the comparison group.

> **Deviation from the design spec, deliberate:** the spec called for a hailstorm.
> The spec's own regional table lists hail only for West Texas and describes the
> Mojave as heat and wind. A microburst catching rows mid-stow is the realistic
> mechanism at this site, so the event was changed to wind.

### Correct behaviour
Identify the cluster; determine it is time-bounded rather than ongoing; trace it
to a discrete weather event plus a logging artifact; **explicitly decline** to
recommend a warranty claim or fleet action. Optionally raise the logging
inconsistency as a data-quality finding.

---

## Finding 4 — DECOY 2 (normalization trap)

Six sites came under contract partway through the window; ten reached commercial
operation after it opened. Exposure is
`max(window start, om_contract_start, commercial_operation_date)` → window end.

| Site | Contract start |
|---|---|
| Sablewood Ridge | 2025-01 |
| Kettle Run | 2025-03 |
| Two Rivers Crossing | 2025-05 |
| Amberline Flats | 2025-08 |
| Blackfoot Draw | 2025-10 |
| Wren Hollow | 2026-01 |

Five of the six lowest sites by raw ticket count are short-coverage sites. A
naive ranking calls them the fleet's most reliable assets.

**The trap runs both ways.** **Blackfoot Draw** ranks 11th of 34 on raw count —
entirely unremarkable — and **1st on WO per GW per month at 43.7, roughly 1.5×
the next worst site.** It is genuinely the worst-performing asset in the fleet
and raw volume hides it completely.

> **Addition to the spec:** the spec's trap only prevented a false positive. The
> inverted case makes normalisation produce a *true* finding as well, which is a
> better test.

### Correct behaviour
Normalise by exposure (per MW per month of coverage), avoid ranking by raw
volume, and flag the varying coverage windows explicitly.

---

## Distractors — real, multi-site, commercially minor

| Cluster | n | Sites | Recorded lost production |
|---|---|---|---|
| Auster Trackline H2 slew drive grease degradation (2016–2019 vintage rows) | 38 | 5 | 10.5 MWh |
| Soltera ST-250 comms module dropouts at humid sites | 44 | 6 | **0.7 MWh** |

The comms cluster generates **nearly as many tickets as the thermal defect while
costing essentially nothing**. A system that ranks by cluster size rather than
financial impact will surface it above Finding 1. That is the test.

---

## Scoring rubric

| # | Criterion | Expected | Weight |
|---|---|---|---|
| 1 | Finding 1 identified as a cluster | Yes | High |
| 2 | Scoped to the **manufacturing window**, not the model | Yes | High |
| 3 | Environmental / seasonal correlation identified | Yes | Medium |
| 4 | Firmware revision link identified | Yes | **High (hardest)** |
| 5 | At-risk population quantified (44 units) | Yes | Medium |
| 6 | Per-unit severity progression recognised | Yes | Medium |
| 7 | Finding 2 site identified | Yes | *Medium* |
| 8 | Finding 2 diagnosed as degradation, **not** soiling | Yes | **High** |
| 9 | Decoy 1 correctly declined | No flag | High |
| 10 | Decoy 1 traced to weather event + logging artifact | Yes | Medium |
| 11 | Decoy 2 handled by normalising exposure | No false ranking | Medium |
| 12 | Blackfoot Draw surfaced despite low raw count | Yes | Medium |
| 13 | Distractor clusters deprioritised by financial impact | Deprioritised | Low |

> **Rubric change from the spec:** the spec weighted "weak signal identified" as
> High. Identification is the easy half — a per-MW-per-month ranking puts Caprock
> Mesa 2nd of 34 without reading anything. The diagnosis is the hard, valuable
> half. Split into items 7 (Medium) and 8 (High).

Use the same rubric to score a naive single-prompt baseline against the full pipeline.

---

## Deviations from the design specification

| Spec | Built | Why |
|---|---|---|
| Vertex Power Systems VPS-3600 | **Kelvara Power Systems KVP-3600** | "Vertex" is a real PV module product line; attaching it to the defective inverter is the exact attribution problem the spec's own critical rule exists to prevent |
| Helion Trackline H2 | **Auster Trackline H2** | "Helion" is a prominent real energy company |
| Palo Verde Flats | **Sundowner Mesa** | Real place name and real power plant |
| Batch codes "2418B–2436B" | Weeks 18–36 of 2024, spanning letters **B and C** | Batch letters cycle quarterly across all models, so the letter carries no defect information and `GROUP BY batch_letter` reveals nothing. Spec's example serial stays valid |
| Hailstorm at the Mojave site | **Microburst** | Spec's own climate table lists hail only for West Texas |
| ~44 work orders over 19 months | **48 over 22 months** | 19 months from the window start ends Jan 2026, leaving the final summer empty and implying an unrecorded remediation |
| Symptoms as a flat menu | **Severity ordered by cumulative thermal exposure, with recidivism** | A progressive mechanism produces repeat visits to the same unit with escalating severity. The spec discarded its strongest evidence thread |
| One narrative names the storm; one names v4.2.1 | **Three name the storm; four quote firmware** | A single keyword deciding a High-weight rubric item is a coin flip, not a difficulty gradient |
| Two backsheet remarks, one ground-fault ticket | **Three remarks, four rising ground-fault tickets** | Two passing remarks are too thin a basis to overturn a soiling explanation |
| `sites.json` + `work_orders.json` | **plus `assets.json`** | "At-risk population" is unanswerable without a serial-level installed base including units that never generated a ticket |
| — | Corpus declared a **filtered CMMS export** | 2,398 tickets for 6.1 GW over 24 months is ~10× low for a fleet this size unless PM is logged at campaign level |

---

## Known residual leakage

Reported honestly rather than hidden. Full numbers in `eval/AUDIT_REPORT.md`.

1. **Narrative length.** Finding 1 tickets run a median 24 words against 16 for
   matched hot-region inverter corrective work (KS p < 0.001). Partly subject
   matter — a thermal diagnosis genuinely takes more words than "reset it, ran
   fine" — but the gap is larger than that alone justifies. *Fix if regenerating:*
   author the planted narratives to the word targets the balance pass assigns,
   or lengthen a matched set of control narratives.
2. **Still-open rate.** 15% of Finding 1 tickets versus 5% of controls, down from
   23% after the balance pass began matching closure rates. Residual comes from
   planted work-order types with thin control pools.
3. **Manufacture-quarter cell.** Joining `assets.json` and ranking corrective
   tickets per installed unit by (model, manufacture quarter) puts KVP-3600
   2024Q2 at 2.65× the third-ranked cell. This is **intended** — it is the
   finding — and it needs four analytical steps (parse serial, bin, join, rate).
   No single ungrounded sort finds it: the best model-level separation is 1.26×.
4. **Style.** A style-only classifier (punctuation, casing, word length,
   function-word density — no subject vocabulary) reaches AUC 0.69, essentially
   all of it the length effect in item 1. No independent style leak.
