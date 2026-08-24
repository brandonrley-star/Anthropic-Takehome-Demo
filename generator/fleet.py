"""
Fleet construction: sites, serial-level inverter registry, technicians.

DESIGN NOTE - why the site/asset tables are hand-specified rather than sampled:
the whole difficulty of Finding 1 depends on precise control of which sites
carry defect-window hardware and which of those actually fail. Sampling that
would give up the control. RNG is used for the finer detail (exact serials,
unit numbering, commissioning dates within a month, per-site equipment mix).
"""

from datetime import date
from config import substream
import taxonomy as tx

# ---------------------------------------------------------------------------
# SITES
# (name, region, mwdc, cod, contract_start or None = covered whole window)
# ---------------------------------------------------------------------------
SITES = [
    # ERCOT West Texas
    ("Caprock Mesa",        "ERCOT_WEST",   180, "2017-06", None),
    ("Ryegate Plains",      "ERCOT_WEST",   230, "2021-04", None),
    ("Bitter Draw",         "ERCOT_WEST",   165, "2019-09", None),
    ("Hollowell Ranch",     "ERCOT_WEST",   250, "2025-04", None),
    ("Sablewood Ridge",     "ERCOT_WEST",   195, "2022-08", "2025-01"),
    ("Blackfoot Draw",      "ERCOT_WEST",   140, "2018-03", "2025-10"),
    ("Sandhill Bend",       "ERCOT_WEST",   225, "2025-02", None),
    ("Pecan Fork",          "ERCOT_WEST",   175, "2020-11", None),
    # ERCOT South Texas
    ("Tidemarsh Bay",       "ERCOT_SOUTH",  210, "2024-10", None),
    ("Coralito Flats",      "ERCOT_SOUTH",  155, "2019-05", None),
    ("Amberline Flats",     "ERCOT_SOUTH",  240, "2024-11", "2025-08"),
    ("Salt Fork Landing",   "ERCOT_SOUTH",  190, "2021-09", None),
    # CAISO Central Valley
    ("Kernwood Basin",      "CAISO_CV",     200, "2018-07", None),
    ("Dry Creek Junction",  "CAISO_CV",     160, "2016-10", None),
    ("Almond Row",          "CAISO_CV",     230, "2024-12", None),
    ("Vireo Valley",        "CAISO_CV",     145, "2020-06", None),
    ("Two Rivers Crossing", "CAISO_CV",     185, "2021-12", "2025-05"),
    # CAISO Mojave
    ("Sundowner Mesa",      "CAISO_MOJAVE", 220, "2019-11", None),
    ("Joshua Fork",         "CAISO_MOJAVE", 215, "2025-01", None),
    ("Ashvale Dry Lake",    "CAISO_MOJAVE", 150, "2017-04", None),
    # MISO Upper Midwest
    ("Kettle Run",          "MISO_UMW",     130, "2020-08", "2025-03"),
    ("Birch Coulee",        "MISO_UMW",     175, "2022-05", None),
    ("Northfield Bend",     "MISO_UMW",      95, "2018-09", None),
    ("Frostline Prairie",   "MISO_UMW",     205, "2025-03", None),
    # PJM Mid-Atlantic
    ("Wren Hollow",         "PJM_MATL",     110, "2021-06", "2026-01"),
    ("Blue Slate Ridge",    "PJM_MATL",     160, "2019-03", None),
    ("Marlow Crossing",     "PJM_MATL",      85, "2016-05", None),
    ("Chestnut Hollow",     "PJM_MATL",     145, "2025-05", None),
    # Southeast non-ISO
    ("Cypress Landing",     "SE_NONISO",    200, "2022-10", None),
    ("Palmetto Bend",       "SE_NONISO",    180, "2020-02", None),
    ("Red Clay Flats",      "SE_NONISO",    120, "2017-08", None),
    ("Sawgrass Reach",      "SE_NONISO",    400, "2025-03", None),
    ("Tallow Branch",       "SE_NONISO",     90, "2016-11", None),
    ("Pine Hollow Station", "SE_NONISO",    165, "2024-09", None),
]

# ---------------------------------------------------------------------------
# DEFECT-WINDOW HARDWARE PLACEMENT  (generator-internal, never emitted)
#
# 74 KVP-3600 units carry the defect-window firmware. They are placed so that
# NO single column separates them:
#   - 52 sit at hot-region sites, 22 at cool-region sites (region alone fails)
#   - of the 12 hot sites holding them, only 9 produce failures (site alone fails)
#   - 6 host sites are recent CODs, 4 are older sites taking replacement units,
#     so site age does not separate them either
# ---------------------------------------------------------------------------
DEFECT_UNITS_BY_SITE = {
    # hot region, failures observed (the 9 Finding-1 sites)
    "Sandhill Bend": 5, "Hollowell Ranch": 6, "Pecan Fork": 5, "Bitter Draw": 5,
    "Tidemarsh Bay": 4, "Almond Row": 5, "Vireo Valley": 6, "Joshua Fork": 5,
    "Ashvale Dry Lake": 5,
    # hot region, no failures yet - at risk, and the reason "site" is not the key
    "Amberline Flats": 4, "Ryegate Plains": 2, "Kernwood Basin": 2,
    # cool region, no failures - the reason "batch" alone is not the key
    "Frostline Prairie": 5, "Chestnut Hollow": 4, "Sawgrass Reach": 7,
    "Pine Hollow Station": 4,
}

SIGNAL1_SITES = [
    "Sandhill Bend", "Hollowell Ranch", "Pecan Fork", "Bitter Draw",
    "Tidemarsh Bay", "Almond Row", "Vireo Valley", "Joshua Fork",
    "Ashvale Dry Lake",
]

SIGNAL2_SITE = "Caprock Mesa"
DECOY1_SITE = "Sundowner Mesa"

# Sites carrying Pinnacle PS-500M modules. Caprock Mesa is the only pre-2020
# install; the rest are young enough that no degradation pattern is expected.
# This stops "module model" from being a shortcut to Finding 2.
PS500M_SITES = ["Caprock Mesa", "Salt Fork Landing", "Birch Coulee",
                "Kettle Run", "Two Rivers Crossing", "Palmetto Bend"]

# Central inverter model population targets across the whole fleet.
# 2024 is deliberately a heavy procurement year for EVERY model, so that
# "manufacture year 2024" is not by itself an anomalous bucket.
MODEL_POPULATION = {"KVP-3600": 340, "CE-4000": 300, "MG-3300": 290, "KVP-2400": 180}


def build_sites():
    rng = substream("sites")
    out = []
    for i, (name, region, mw, cod, contract) in enumerate(SITES, start=1):
        site_id = f"NRS-{i:03d}"
        cod_date = f"{cod}-{rng.randint(1, 28):02d}"
        out.append({
            "site_id": site_id,
            "site_name": name,
            "region": region,
            "region_label": tx.REGIONS[region]["label"],
            "capacity_mwdc": mw,
            "commercial_operation_date": cod_date,
            "om_contract_start": (contract + "-01") if contract else "2024-07-01",
            "tracker_model": None,      # filled by build_equipment
            "module_models": [],
            "central_inverter_models": [],
            "string_inverter_model": None,
            "bess": False,
        })
    return out


def build_equipment(sites):
    """Attach module / tracker / BESS profiles to each site."""
    rng = substream("equipment")
    bess_sites = {"Hollowell Ranch", "Joshua Fork", "Almond Row", "Cypress Landing",
                  "Sawgrass Reach", "Frostline Prairie", "Tidemarsh Bay"}
    for s in sites:
        name = s["site_name"]
        # modules: primary + occasional secondary on multi-phase sites
        if name in PS500M_SITES:
            mods = ["PS-500M"]
        else:
            mods = [rng.choice(["AX-540", "AX-455", "KP-530"])]
        if s["capacity_mwdc"] >= 200 and rng.random() < 0.45:
            alt = rng.choice([m for m in tx.MODULES if m not in mods])
            mods.append(alt)
        s["module_models"] = mods
        # trackers: Auster skews older/west, Ridgeway skews newer
        cod_year = int(s["commercial_operation_date"][:4])
        s["tracker_model"] = "Trackline H2" if (cod_year <= 2019 or rng.random() < 0.38) else "RS-Track"
        s["bess"] = name in bess_sites
        # string inverters appear at a minority of sites, mostly smaller ones
        if s["capacity_mwdc"] <= 165 and rng.random() < 0.55:
            s["string_inverter_model"] = rng.choice(["ST-250", "CE-275"])
        elif s["region"] in ("SE_NONISO", "PJM_MATL") and rng.random() < 0.35:
            s["string_inverter_model"] = "ST-250"

    # The Soltera comms distractor has to span several sites to be a credible
    # "systemic defect" candidate, so guarantee ST-250 presence at a spread of
    # humid sites rather than leaving it to the draw.
    forced = ["Cypress Landing", "Palmetto Bend", "Red Clay Flats",
              "Blue Slate Ridge", "Chestnut Hollow", "Coralito Flats"]
    for s in sites:
        if s["site_name"] in forced:
            s["string_inverter_model"] = "ST-250"
    return sites


# ---------------------------------------------------------------------------
# SERIAL-LEVEL INVERTER REGISTRY
#
# Batch letters cycle QUARTERLY by manufacture week, globally, for every model:
#   A = wk 01-13, B = wk 14-26, C = wk 27-39, D = wk 40-52
# This is a deliberate change from the original spec (which implied letter "B"
# ran the length of the defect window). Because the defect window is weeks
# 18-36, it spans letters B and C, so the batch LETTER carries no information
# about the defect and GROUP BY letter reveals nothing. It also reflects how
# firmware actually gets loaded: by production date, not by batch label.
# The spec's example serial (KVP36-2418B-...) remains valid under this rule.
# ---------------------------------------------------------------------------

def batch_letter(week: int) -> str:
    return tx.BATCH_LETTERS[min((week - 1) // 13, 3)]


def _is_defect_window(yy: int, ww: int) -> bool:
    return yy == tx.DEFECT_YEAR and tx.DEFECT_WEEK_LO <= ww <= tx.DEFECT_WEEK_HI


def _months_before(iso_ym: str, months: int):
    y, m = int(iso_ym[:4]), int(iso_ym[5:7])
    total = y * 12 + (m - 1) - months
    return total // 12, total % 12 + 1


def _yearweek_for_cod(cod: str, rng, lead_lo=5, lead_hi=11):
    """Pick a plausible manufacture year/week given a commissioning month."""
    y, m = _months_before(cod, rng.randint(lead_lo, lead_hi))
    week = min(52, max(1, (m - 1) * 4 + rng.randint(1, 4)))
    return y % 100, week


def build_assets(sites):
    """Return serial-level records for every central inverter in the fleet."""
    rng = substream("assets")
    by_name = {s["site_name"]: s for s in sites}
    assets = []
    unit_counter = {}

    def serial(model, yy, ww):
        pfx = tx.CENTRAL_INVERTERS[model]["prefix"]
        key = (model, yy, ww)
        unit_counter[key] = unit_counter.get(key, rng.randint(80, 400)) + rng.randint(1, 4)
        return f"{pfx}-{yy:02d}{ww:02d}{batch_letter(ww)}-{unit_counter[key]:04d}"

    def add(site, model, yy, ww, comm_date):
        a_id = serial(model, yy, ww)
        spec = tx.CENTRAL_INVERTERS[model]
        assets.append({
            "asset_id": a_id,
            "site_id": site["site_id"],
            "site_name": site["site_name"],
            "asset_class": "central_inverter",
            "manufacturer": spec["mfr"],
            "model": model,
            "rated_mw": spec["mw"],
            "commissioned_date": comm_date,
            "warranty_parts_expiry": f"{int(comm_date[:4]) + 5}{comm_date[4:]}",
            # generator-internal, stripped at emit:
            "_defect_window": (model == "KVP-3600") and _is_defect_window(yy, ww),
            "_mfg_yy": yy, "_mfg_ww": ww,
        })
        return a_id

    for s in sites:
        name = s["site_name"]
        cod = s["commercial_operation_date"][:7]
        mwac = s["capacity_mwdc"] / 1.30
        if s["string_inverter_model"]:
            mwac *= rng.uniform(0.55, 0.80)

        n_defect = DEFECT_UNITS_BY_SITE.get(name, 0)
        mwac = max(mwac - n_defect * 3.6, mwac * 0.35)   # defect units take their own share

        pool = list(tx.CENTRAL_INVERTERS)                # KVP-3600, KVP-2400, CE-4000, MG-3300
        primary = rng.choices(pool, weights=[17, 26, 30, 27])[0]
        models = [primary]
        if s["capacity_mwdc"] >= 220 and rng.random() < 0.35:
            models.append(rng.choice([m for m in pool if m != primary]))
        # A defect site must ALSO carry non-defect KVP-3600 units, otherwise
        # (site AND model) would isolate the defect units exactly.
        forced_kvp = False
        if n_defect and "KVP-3600" not in models:
            models.append("KVP-3600")
            forced_kvp = True

        shares = [rng.uniform(0.8, 1.2) for _ in models]
        if forced_kvp:
            # a forced KVP-3600 presence is a partial phase, not an equal third
            shares[-1] = rng.uniform(0.22, 0.42)
        tot = sum(shares)
        for model, sh in zip(models, shares):
            n = max(1, round(mwac * sh / tot / tx.CENTRAL_INVERTERS[model]["mw"]))
            for _ in range(n):
                yy, ww = _yearweek_for_cod(cod, rng)
                # Only KVP-3600 is barred from the defect window, because only
                # KVP-3600 units built then carry the affected firmware. Other
                # models populate weeks 18-36 of 2024 freely, so the raw week
                # window is not by itself a discriminator.
                if model == "KVP-3600" and _is_defect_window(yy, ww):
                    ww = rng.choice([9, 11, 13, 15, 38, 41, 45, 49])
                add(s, model, yy, ww, f"{cod}-{rng.randint(1, 28):02d}")

        cod_year = int(cod[:4])
        for _ in range(n_defect):
            if cod_year >= 2024:
                ww = rng.randint(tx.DEFECT_WEEK_LO, tx.DEFECT_WEEK_HI)
            else:
                # A site swapping inverters mid-2024 takes whatever the depot
                # already has on the shelf, which skews to earlier build weeks.
                ww = rng.choices(range(tx.DEFECT_WEEK_LO, tx.DEFECT_WEEK_HI + 1),
                                 weights=[max(1, 22 - abs(w - 21)) for w in
                                          range(tx.DEFECT_WEEK_LO, tx.DEFECT_WEEK_HI + 1)])[0]
            if cod_year >= 2024:
                comm = f"{cod}-{rng.randint(1, 28):02d}"
            else:
                # Replacement swaps turn around fast, and a unit built in week 18
                # shipped months before one built in week 36. Tying install date to
                # build week is what lets the defect start appearing in the summer
                # of 2024 instead of only from 2025 on.
                if ww <= 24:
                    ry, rm = rng.choice([(2024, 7), (2024, 7), (2024, 8), (2024, 8), (2024, 10)])
                elif ww <= 30:
                    ry, rm = rng.choice([(2024, 9), (2024, 10), (2024, 12), (2025, 3)])
                else:
                    ry, rm = rng.choice([(2024, 11), (2025, 1), (2025, 3), (2025, 5)])
                comm = f"{ry}-{rm:02d}-{rng.randint(1, 28):02d}"
            add(s, "KVP-3600", tx.DEFECT_YEAR, ww, comm)

    # Minority-fleet pass: give a further set of NON-defect sites a small
    # KVP-3600 population (phased builds, partial repowers). Without this,
    # "site carries KVP-3600" would be nearly synonymous with "site carries
    # defect-window units", which is a site-level collinearity.
    covered = {a["site_name"] for a in assets if a["model"] == "KVP-3600"}
    candidates = [s for s in sites if s["site_name"] not in covered]
    rng.shuffle(candidates)
    for s in candidates[:9]:
        cod = s["commercial_operation_date"][:7]
        for _ in range(rng.randint(4, 11)):
            yy, ww = _yearweek_for_cod(cod, rng)
            if _is_defect_window(yy, ww):
                ww = rng.choice([9, 11, 13, 15, 38, 41, 45, 49])
            add(s, "KVP-3600", yy, ww, f"{cod}-{rng.randint(1, 28):02d}")

    return assets


# ---------------------------------------------------------------------------
# TECHNICIANS
#
# IDs run in global hire order (which is why the newest tech has the highest
# number) and therefore carry no region information. Techs are region-bound
# except for three travelling specialists, so a tech does not service PJM and
# the Mojave in the same week.
#
# `voice` is a generator-internal prose description. Narratives are authored
# against it, so it has to be specific enough to actually write from.
# ---------------------------------------------------------------------------
TECHNICIANS = [
    ("TECH-0044", "ERCOT_WEST", "2015-04", "fragment",
     "Almost never writes a full sentence. Six to fifteen words, all lowercase, no "
     "terminal punctuation. Heavy abbreviation. Often just states the action taken."),
    ("TECH-0051", "CAISO_CV", "2015-09", "clipped",
     "Short declarative sentences, proper capitalization, ends with a period. Rarely "
     "over thirty words. Uses 'per SCADA' and 'ok on retest' a lot."),
    ("TECH-0063", "SE_NONISO", "2016-02", "narrative",
     "Writes in run-on sentences with commas where periods belong. Mentions weather and "
     "road conditions unprompted. Forty to eighty words."),
    ("TECH-0072", "ERCOT_WEST", "2016-06", "clipped",
     "Terse, ALL CAPS for fault names and codes, mixed case elsewhere. Types 'invertor' "
     "consistently. Twelve to thirty words."),
    ("TECH-0088", "MISO_UMW", "2016-11", "narrative",
     "Chatty. Talks about snow, gate access, and the drive. Buries the actual finding in "
     "the middle. Fifty to ninety words."),
    ("TECH-0095", "PJM_MATL", "2017-03", "fragment",
     "Telegraphic. Noun phrases separated by slashes or dashes. Under twelve words often."),
    ("TECH-0103", "CAISO_MOJAVE", "2017-08", "clipped",
     "Dry and consistent. Always leads with the asset. Twenty to forty words. Occasional "
     "'temperture' typo."),
    ("TECH-0110", "ERCOT_SOUTH", "2018-01", "narrative",
     "Rambling, friendly, lots of 'went ahead and'. Mentions lunch, escorts, and the "
     "wildlife. Forty to one hundred words."),
    ("TECH-0117", "ERCOT_WEST", "2018-05", "thorough",
     "One of the two genuinely thorough techs. Structured but not templated: what was "
     "found, what was checked, what was ruled out, what to watch. Eighty to two hundred "
     "words. Proper punctuation. Notes firmware and part numbers when he sees them."),
    ("TECH-0124", "CAISO_CV", "2018-09", "clipped",
     "Efficient. Lowercase start, no caps. Fifteen to thirty-five words. Uses 'chkd' and 'rplcd'."),
    ("TECH-0131", "ERCOT_WEST", "2019-02", "fragment",
     "Very short. Sometimes a single noun phrase. Frequently leaves parts_used blank even "
     "when parts were used."),
    ("TECH-0138", "MISO_UMW", "2019-06", "clipped",
     "Plain and readable, twenty to forty-five words, complete sentences, no flourishes."),
    ("TECH-0145", "PJM_MATL", "2019-10", "narrative",
     "Long-winded about process, short on findings. Mentions LOTO and permits constantly. "
     "Forty to seventy words."),
    ("TECH-0152", "TRAVEL", "2020-01", "thorough",
     "The second thorough tech. Commissioning and HV specialist, travels fleet-wide. "
     "Writes like an engineer: measurements with units, sequence of tests, explicit "
     "conclusion and explicit uncertainty. Ninety to two hundred words."),
    ("TECH-0159", "ERCOT_SOUTH", "2020-04", "clipped",
     "Blunt. Twelve to twenty-eight words. Swears mildly about the heat. Types 'contacter'."),
    ("TECH-0166", "CAISO_CV", "2020-08", "fragment",
     "Bullet-ish fragments run together with semicolons. Under twenty words usually."),
    ("TECH-0173", "SE_NONISO", "2021-01", "narrative",
     "Storyteller. Vegetation and storm work mostly. Fifty to ninety words, lots of "
     "'again' and 'same as last time'."),
    ("TECH-0180", "ERCOT_WEST", "2021-05", "clipped",
     "Consistent format-ish but never identical. Twenty to forty words. Notes ambient temp "
     "casually when it is extreme."),
    ("TECH-0187", "TRAVEL", "2021-09", "clipped",
     "Regional floater, mostly tracker and mechanical work. Twenty-five to fifty words."),
    ("TECH-0194", "CAISO_MOJAVE", "2022-02", "fragment",
     "Minimal. Eight to eighteen words. Almost never fills parts_used."),
    ("TECH-0201", "MISO_UMW", "2022-06", "clipped",
     "Careful about dates and times, mentions 'second trip' and 'came back after lunch'. "
     "Twenty-five to forty-five words."),
    ("TECH-0208", "SE_NONISO", "2022-10", "narrative",
     "Wordy but vague. Forty to seventy words that often do not say what was actually wrong."),
    ("TECH-0215", "SE_NONISO", "2023-03", "clipped",
     "Newer, still writes fairly completely. Twenty to forty words. Occasional 'idk' and 'tbd'."),
    ("TECH-0222", "ERCOT_SOUTH", "2023-08", "fragment",
     "Short and inconsistent. Sometimes eight words, occasionally fifty when annoyed."),
    ("TECH-0229", "CAISO_CV", "2024-01", "clipped",
     "Twenty to thirty-five words. Very literal. Reports exactly what the HMI said."),
    ("TECH-0231", "CAISO_MOJAVE", "2025-03", "clipped",
     "Newest hire at the Mojave sites. Fifteen to thirty words, tidy, proper capitalization. "
     "Logs one work order PER TRACKER ROW where his colleagues log one per zone - this is "
     "his consistent habit across all his tracker work, not something specific to any event."),
    ("TECH-0236", "ERCOT_WEST", "2025-06", "fragment",
     "Very new. Ten to twenty words, terse, occasionally uses the wrong resolution code."),
    ("TECH-0240", "TRAVEL", "2025-09", "narrative",
     "Newest travelling tech, module and PV-side specialist. Thirty-five to sixty words."),
]

THOROUGH_TECHS = ["TECH-0117", "TECH-0152"]
PER_ROW_LOGGER = "TECH-0231"


def build_technicians():
    rng = substream("technicians")
    out = []
    for tid, region, hired, register, voice in TECHNICIANS:
        out.append({
            "technician_id": tid,
            "home_region": region,
            "hire_date": f"{hired}-{rng.randint(1, 28):02d}",
            "_register": register,
            "_voice": voice,
        })
    return out
