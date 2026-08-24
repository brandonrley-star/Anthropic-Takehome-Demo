==============================================================================
FREQUENCY AUDIT
==============================================================================

total work orders: 2398

  [OK ] signal_1               48  (intended 48)
  [OK ] signal_2               26  (intended 26)
  [OK ] decoy_1                31  (intended 31)
  [OK ] distractor_slew        38  (intended 38)
  [OK ] distractor_comms       44  (intended 44)
  [OK ] background           2211

SIGNAL 1 — Kelvara KVP-3600 defect-window thermal degradation
  work orders            48
  distinct units         30   (intended 30)
  distinct sites         9   (intended 9)
  sites match spec       True
  max WOs at any site    9  (Vireo Valley)
  distinct technicians   15
  distinct symptom types 12
  distinct resolution cd 8
  span                   2024-09-15 -> 2026-06-30
  by year                {2024: 4, 2025: 23, 2026: 21}
  by month               {3: 1, 4: 1, 5: 6, 6: 15, 7: 10, 8: 5, 9: 9, 10: 1}
  outside May-Sep        3
  severity stage mix     {1: 14, 2: 21, 3: 13}
  repeat visits/unit     {1: 17, 2: 9, 3: 3, 4: 1}
  firmware mentions      4
  fan-control guesses    2

  defect-window units in fleet   74
    at hot-region sites          54
    at cool-region sites         20
    sites holding them           16  (only 9 show failures)
    with failure history         30
    at risk, no failure yet      44

SIGNAL 2 — Caprock Mesa backsheet degradation read as soiling
  work orders            26  all at ['Caprock Mesa']
  kinds                  {'wash': 10, 'scada': 5, 'ir': 4, 'cosmetic': 3, 'gf': 4}
  per half-year          {(2024, 1): 4, (2025, 0): 4, (2025, 1): 8, (2026, 0): 10}  (rising)
  in older blocks B01-04 21 of 26
  distinct technicians   6

DECOY 1 — Sundowner Mesa wind event plus a logging artifact
  work orders            31  at ['Sundowner Mesa']
  window                 2025-03-15 -> 2025-04-28
  per-row vs per-zone    {'per_row': 21, 'per_zone': 10}
  logged by TECH-0231    22
  narratives naming event3
  carrying claim ref     2
  TECH-0231 per-row work OUTSIDE the event window: 16
  mean labor_hours       per-row 2.9  per-zone 8.6

DECOY 2 — normalization trap (structural, consumes no work orders)
  lowest RAW count (the naive 'most reliable' list):
    Wren Hollow            raw=   9  cov= 6mo  norm= 13.6
    Marlow Crossing        raw=  31  cov=24mo  norm= 15.2
    Chestnut Hollow        raw=  32  cov=14mo  norm= 15.8
    Amberline Flats        raw=  35  cov=11mo  norm= 13.3
    Kettle Run             raw=  39  cov=16mo  norm= 18.8
    Frostline Prairie      raw=  41  cov=16mo  norm= 12.5
  highest NORMALIZED (WO per GW per month):
    Blackfoot Draw         norm= 43.7  raw=  55  cov= 9mo
    Caprock Mesa           norm= 28.2  raw= 122  cov=24mo
    Sundowner Mesa         norm= 26.5  raw= 140  cov=24mo
    Red Clay Flats         norm= 24.7  raw=  71  cov=24mo

DISTRACTOR — Auster slew drive grease
  work orders 38 across 5 sites: ['Ashvale Dry Lake', 'Dry Creek Junction', 'Marlow Crossing', 'Red Clay Flats', 'Tallow Branch']
  lost production recorded on 8/38, total 10.5 MWh

DISTRACTOR — Soltera ST-250 comms dropouts
  work orders 44 across 6 sites: ['Blue Slate Ridge', 'Chestnut Hollow', 'Coralito Flats', 'Cypress Landing', 'Palmetto Bend', 'Red Clay Flats']
  lost production recorded on 6/44, total 0.7 MWh

==============================================================================
ADVERSARIAL AGGREGATION AUDIT   (no narrative reading)
==============================================================================

--- SIGNAL 1: Kelvara KVP-3600 defect-window thermal failures ---

  (a) LEAKAGE: how strongly does each column correlate with the plant?
      Uses ground truth, so it measures leakage, not what an analyst sees.
      wo_type        top=Emergency    4/   94 lift=  2.1x  covers   8%
      priority       top=P2          18/  421 lift=  2.1x  covers  38%
      res            top=ESCALATED    9/  158 lift=  2.8x  covers  19%
      tech           top=TECH-0103    5/   79 lift=  3.2x  covers  10%
      site           top=Sandhill Bend   6/   50 lift=  6.0x  covers  12%
      region         top=CAISO_CV    15/  390 lift=  1.9x  covers  31%
      month          top=6           15/  246 lift=  3.0x  covers  31%
      prefix         top=KVP36       48/  181 lift= 13.2x  covers 100%
      batch_letter   top=B           26/  160 lift=  8.1x  covers  54%
      yr_letter      top=24C         22/   44 lift= 25.0x  covers  46%
      batch_token    top=2432C        9/   11 lift= 40.9x  covers  19%
      mfg_quarter    top=24Q3        22/   44 lift= 25.0x  covers  46%

  (b) ANALYST VIEW: rankings computable WITHOUT the labels.
      This is the real test of discoverability.
      tickets per installed unit, by model:
        KVP-3600    181/ 376 = 0.481
        CE-4000     125/ 327 = 0.382
        MG-3300     103/ 287 = 0.359
        KVP-2400     89/ 388 = 0.229
      -> top model is 1.26x the next. suggestive at best, not conclusive
      tickets per installed unit, by (model, manufacture quarter):
                              units  tickets  per_unit
        model    mfg_quarter                          
        KVP-3600 24Q2            53     48.0  0.905660
                 24Q3            44     34.0  0.772727
        KVP-2400 19Q2            38     13.0  0.342105
        CE-4000  24Q1            35     11.0  0.314286
        KVP-3600 24Q1            45     13.0  0.288889
                 24Q4            37     10.0  0.270270
      -> top cell is 2.65x the third. This ranking requires parsing
         the serial AND joining assets.json for the denominator.

  (c) RAW COUNT rankings (the laziest possible attack):
      by model prefix           {'KVP36': np.int64(147), 'CES40': np.int64(87), 'MGX33': np.int64(72)}
      by manufacture quarter    {'24Q2': np.int64(62), '24Q3': np.int64(37), '24Q1': np.int64(25)}
      by exact batch token      {'2432C': np.int64(11), '2423B': np.int64(10), '2413A': np.int64(9)}
      -> raw counts track how many units of each kind exist, not defect rate.

  (d) The answer, once known: filter KVP36 + 2024 wk18-36
      -> 75 work orders, 48 are signal_1 (precision 64%, recall 100%)

    VERDICT
      single ungrounded sort: does NOT find it (best model-level separation 1.26x)
      serial-parse + asset-registry join: SURFACES the cluster (2.65x over the third-ranked cell)
      What that join yields: 'KVP-3600 built in 2024 Q2/Q3 fail more'.
      What it does NOT yield: the week-18-36 boundary, the firmware
      revision, the thermal mechanism, the ambient/seasonal link, the
      per-unit severity progression, or the at-risk population. Those
      require reading narratives.

--- SIGNAL 2: Caprock Mesa backsheet degradation ---
  group by site: top=Caprock Mesa 26/122 lift=19.7x
  Caprock Mesa normalized-rate rank: 2 of 34
  -> aggregation CAN flag the site as busy. It cannot say why.
     The diagnosis (degradation, not soiling) rests on cleaning-benefit
     decay stated only in narrative text. Checking that it is not in a column:
       wash tickets at Caprock Mesa: 10
       any column holding recovery %? NO
       lost_production populated on washes: 1/10

--- DECOY 1: Sundowner Mesa cluster (SHOULD be aggregation-visible) ---
  Sundowner Mesa tickets in Mar-Apr 2025: 39
  site's average tickets/month: 5.8  -> spike factor 3.3x
  tickets by TECH-0231 in that window: 23
  TECH-0231 total tickets: 97, of which tracker-row-tagged outside the window: 16
  -> correctly visible. Resolving it needs the narratives (one wind event)
     plus the per-row/per-zone labour comparison.

--- DECOY 2: normalization trap (SHOULD be aggregation-visible) ---
  six lowest by raw count: ['Wren Hollow', 'Marlow Crossing', 'Chestnut Hollow', 'Amberline Flats', 'Kettle Run', 'Frostline Prairie']
  of those, short-coverage sites: 5/6
  Blackfoot Draw: raw rank 11, normalized rank 1
  -> raw ranking misleads in both directions, as intended.

==============================================================================
No TRUE signal (1 or 2) is discoverable by simple aggregation alone.
Both decoys are aggregation-visible, which is their purpose.
==============================================================================

==============================================================================
STRUCTURAL AND LEXICAL LEAKAGE AUDIT
==============================================================================

Signal 1 vs matched controls (hot-region inverter corrective work):
  signal_1                   n=  48  hours med=  4.7 | words med=   24 mean=  28.3 | parts  44% | lost  29% | open  15%
  matched controls           n= 203  hours med=  4.9 | words med=   16 mean=  23.8 | parts  36% | lost  23% | open   5%

  distribution tests (a low p-value means the two are separable):
    labor_hours            KS p=0.859  MW p=0.998  -> not separable
    narrative word count   KS p=0.000  MW p=0.006  -> SEPARABLE

  field completeness (share of records with the field populated):
    parts_used             signal   44%   control   36%   delta +8%
    asset_id               signal  100%   control  100%   delta +0%
    lost_production        signal   29%   control   23%   delta +6%
    still open             signal   15%   control    5%   delta +9%

  technician register mix:
    signal_1     clipped=50%  fragment=40%  narrative=4%  thorough=6%
    controls     clipped=52%  fragment=36%  narrative=2%  thorough=9%

  wo_id ordering: does the identifier sequence carry plant information?
    signal_1 ids span 163-920, mean gap 16.1 vs corpus mean gap 0.53 -> not clustered

  LEXICAL
    full-text char n-gram AUC 0.98
      Expected to be high and NOT a defect: these tickets describe a
      different failure mode, so their vocabulary differs. A classifier
      learning that has learned the finding, not an artifact.
    STYLE-ONLY AUC 0.69 (+/- 0.08)
      (punctuation rates, casing, word length, function-word density -
       no subject-matter vocabulary at all)
    -> no style leak: planted text is written like the rest of the corpus

Signal 2 vs other work at the same site:
  signal_2                   n=  26  hours med=  6.7 | words med=   26 mean=  27.1 | parts  12% | lost  12% | open   0%
  Caprock Mesa background    n=  96  hours med=  4.5 | words med=   20 mean=  28.5 | parts  28% | lost  15% | open   5%
  narrative length KS p=0.673
