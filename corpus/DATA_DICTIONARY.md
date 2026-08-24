# Northlight Renewable Services — O&M Corpus Data Dictionary

Filtered CMMS export covering the O&M fleet from **2024-07-01 to 2026-06-30**.
2,398 work orders across 34 sites (6,120 MWdc).

## Scope and known quirks of this export

Read these before analysing. They are properties of the source system, not of
any particular finding.

1. **This is a filtered export, not every ticket the CMMS holds.** Preventative
   maintenance is logged at *campaign* level — one work order per block per PM
   campaign, not one per device — and sub-hour trivia is excluded. That is why
   a 200 MW site shows a few dozen work orders a month rather than several
   hundred.
2. **`resolution_code` is frequently wrong.** The list is coarse, crews pick
   from it in a hurry, and roughly one ticket in eight carries a code that does
   not match what the narrative describes. Do not use it as a grouping key
   without reading the narrative.
3. **Coverage windows differ by site.** Six sites came under contract partway
   through the window and ten reached commercial operation after it opened.
   A site's exposure is `max(window start, om_contract_start,
   commercial_operation_date)` to window end. Raw ticket counts are not
   comparable across sites without normalising for this **and** for capacity.
4. **Ticket volume reflects reporting culture as well as reliability.** Crews
   differ in how much they log. Two sites in comparable condition can differ
   roughly twofold in ticket count.
5. **The asset registry covers central inverters only.** Balance-of-plant is
   tracked by positional tag rather than serial, which is normal for this
   vintage of CMMS. See `asset_id` below.
6. **Narratives are free text written on a tablet in the field.** Expect
   fragments, abbreviations, inconsistent capitalisation, typos, and irrelevant
   detail. Some narratives omit facts recorded in the structured fields, and
   some record facts that appear nowhere else.
7. **Open tickets exist.** `date_closed` is null on roughly 7% of records,
   concentrated in recent months and in escalated or vendor-referred work.

---

## `work_orders.json` / `work_orders.csv`

| Field | Type | Notes |
|---|---|---|
| `wo_id` | string | `WO-YYYY-NNNNN`. Sequence is per calendar year, assigned in date order. Carries no other meaning. |
| `site_id` | string | `NRS-NNN`. Joins to `sites.json`. |
| `site_name` | string | Denormalised for convenience. |
| `date_opened` | date | ISO. Always within the window. |
| `date_closed` | date or null | Null means still open. Same-day closure is common. |
| `wo_type` | enum | `PM`, `CM`, `Emergency`, `Inspection`, `Vegetation`, `Warranty`. |
| `priority` | enum | `P1` (highest) to `P4`. Assigned at open and rarely revised. |
| `asset_id` | string | May be empty where work was site-wide or the tech did not tag it. See conventions below. |
| `technician_id` | string | `TECH-NNNN`. Joins to `technicians.json`. |
| `labor_hours` | float | Billed hours. Crew hours where more than one tech attended. |
| `parts_used` | string | Free text, often blank even where parts were fitted. `x2`/`x3` suffixes indicate quantity. |
| `narrative` | string | Free text. The substantive field. |
| `resolution_code` | enum | See list below. Frequently misapplied — quirk 2. |
| `estimated_lost_production_mwh` | float or null | Present on a minority of records only (~14%), and populated inconsistently. Absence does not mean zero. |

### `resolution_code` values

`RESET`, `PART-REPL`, `SW-UPDATE`, `NO-FAULT-FOUND`, `CLEANED`, `ADJUSTED`,
`ESCALATED`, `VENDOR-REFERRED`, `OTHER`.

### `asset_id` conventions

| Pattern | Meaning |
|---|---|
| `KVP36-2418B-0447` | Central inverter serial. Joins to `assets.json`. |
| `SLT25-2109A-0231` | String inverter serial. **Not** in the asset registry. |
| `CB-B03-14` | Combiner 14 in block 3. |
| `TR-B07-R042` | Tracker row 42 in block 7. |
| `TR-Z04` | Tracker zone 4 (a group of rows). |
| `XFMR-B02` | Medium-voltage transformer serving block 2. |
| `CX-R03` | Battery rack 3. |
| `MET-01` | Meteorological / soiling station. |
| `B05` | Array block, where work was block-wide. |
| *(empty)* | Site-wide, or not tagged. |

Note that trackers appear at **two granularities** — per row (`TR-Bnn-Rnnn`)
and per zone (`TR-Znn`). Which one a given ticket uses depends on the
technician, not on the work. This matters when counting tracker events.

### Inverter serial convention

`{MODEL_PREFIX}-{YY}{WW}{BATCH}-{UNIT}` — e.g. `KVP36-2418B-0447` is a
Kelvara KVP-3600, manufactured in **2024 week 18**, batch letter **B**, unit
447. Batch letters cycle quarterly by manufacture week (A = weeks 1–13,
B = 14–26, C = 27–39, D = 40–52) and are shared across all models. There is no
separate manufacture-date field; the serial is the only record of it.

---

## `sites.json`

| Field | Type | Notes |
|---|---|---|
| `site_id`, `site_name` | string | |
| `region` | string | ISO / geographic region. |
| `capacity_mwdc` | int | Nameplate DC, 85–400 MWdc. |
| `commercial_operation_date` | date | 2016–2025. |
| `om_contract_start` | date | When Northlight took over. Not the same as COD — see quirk 3. |
| `central_inverter_models` | list | Derived from the asset registry. |
| `string_inverter_model` | string or null | String inverters are not individually registered. |
| `module_models` | list | Phased sites carry more than one. |
| `tracker_model` | string | |
| `bess_installed` | bool | Seven sites. |

## `assets.json`

Serial-level registry of every **central inverter** in the fleet (1,378 units),
including units that have never generated a work order.

| Field | Type | Notes |
|---|---|---|
| `asset_id` | string | Serial. Joins to `work_orders.asset_id`. |
| `site_id`, `site_name` | string | |
| `asset_class` | string | Always `central_inverter` in this export. |
| `manufacturer`, `model` | string | |
| `rated_mw` | float | AC rating. |
| `commissioned_date` | date | In-service date. May be well after the site's COD where a unit was installed as a replacement. |
| `warranty_parts_expiry` | date | Commissioning + 5 years, per the standard supply terms. |

## `technicians.json`

| Field | Type | Notes |
|---|---|---|
| `technician_id` | string | Numbering follows global hire order. |
| `home_region` | string | Techs work their home region; three float fleet-wide. |
| `hire_date` | date | A tech cannot appear on a ticket before this date. |

---

## Reproducibility

Generated from master seed **20260824** (recorded in `MANIFEST.json` with
SHA-256 digests of every file). All structured fields are a deterministic
function of that seed. Narrative text was authored separately and is fixed by
the committed generation checkpoints rather than by the seed alone.

All manufacturer, model, site and personnel names are fictional.
