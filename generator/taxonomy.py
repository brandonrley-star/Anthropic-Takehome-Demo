"""
Fictional equipment taxonomy and controlled vocabularies.

EVERY manufacturer, model and site name in this module is invented. Names were
screened against real solar-industry brands; three names from the original
design spec were changed because they collided with real referents:
  Vertex Power Systems -> Kelvara Power Systems  ("Vertex" is a real PV module line)
  Helion Trackline     -> Auster Trackline       ("Helion" is a real energy company)
  Palo Verde Flats     -> Sundowner Mesa         (real place and real power plant)
"""

# --------------------------------------------------------------- manufacturers
CENTRAL_INVERTERS = {
    "KVP-3600": {"mfr": "Kelvara Power Systems", "prefix": "KVP36", "mw": 3.6},
    "KVP-2400": {"mfr": "Kelvara Power Systems", "prefix": "KVP24", "mw": 2.4},
    "CE-4000":  {"mfr": "Calderon Energy Systems", "prefix": "CES40", "mw": 4.0},
    "MG-3300":  {"mfr": "Meridian Grid",           "prefix": "MGX33", "mw": 3.3},
}

STRING_INVERTERS = {
    "ST-250": {"mfr": "Soltera",                 "prefix": "SLT25", "mw": 0.25},
    "CE-275": {"mfr": "Calderon Energy Systems", "prefix": "CES27", "mw": 0.275},
}

MODULES = {
    "AX-540": {"mfr": "Auralux",              "watts": 540, "bifacial": True},
    "AX-455": {"mfr": "Auralux",              "watts": 455, "bifacial": False},
    "PS-500M": {"mfr": "Pinnacle Solar",      "watts": 500, "bifacial": False},
    "KP-530": {"mfr": "Kestrel Photovoltaics", "watts": 530, "bifacial": True},
}

TRACKERS = {
    "Trackline H2": {"mfr": "Auster", "axis": "single"},
    "RS-Track":     {"mfr": "Ridgeway Solar Systems", "axis": "single"},
}

BESS = {"CX-Series": {"mfr": "Cascade Energy Storage"}}

# ------------------------------------------------------------ controlled lists
RESOLUTION_CODES = [
    "RESET", "PART-REPL", "SW-UPDATE", "NO-FAULT-FOUND",
    "CLEANED", "ADJUSTED", "ESCALATED", "VENDOR-REFERRED", "OTHER",
]

WO_TYPES = ["PM", "CM", "Emergency", "Inspection", "Vegetation", "Warranty"]
PRIORITIES = ["P1", "P2", "P3", "P4"]

# ------------------------------------------------------------------- regions
REGIONS = {
    "ERCOT_WEST":   {"label": "ERCOT / West Texas",       "hot": True,  "n_sites": 8},
    "ERCOT_SOUTH":  {"label": "ERCOT / South Texas",      "hot": True,  "n_sites": 4},
    "CAISO_CV":     {"label": "CAISO / Central Valley CA","hot": True,  "n_sites": 5},
    "CAISO_MOJAVE": {"label": "CAISO / Mojave",           "hot": True,  "n_sites": 3},
    "MISO_UMW":     {"label": "MISO / Upper Midwest",     "hot": False, "n_sites": 4},
    "PJM_MATL":     {"label": "PJM / Mid-Atlantic",       "hot": False, "n_sites": 4},
    "SE_NONISO":    {"label": "Southeast / Non-ISO",      "hot": False, "n_sites": 6},
}

# Serial batch convention: {PREFIX}-{YYWW}{LETTER}-{UNIT}
# e.g. KVP36-2418B-0447  ->  KVP-3600, 2024 week 18, batch letter B, unit 447
BATCH_LETTERS = ["A", "B", "C", "D"]

# The defect window. NOTE: this constant lives in the generator only and is
# never emitted. It spans 19 distinct week-codes, so a naive GROUP BY on the
# full batch token yields ~19 small groups rather than one conspicuous one.
DEFECT_YEAR = 24
DEFECT_WEEK_LO = 18
DEFECT_WEEK_HI = 36
DEFECT_LETTER = "B"
