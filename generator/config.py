"""
Central configuration for the Northlight Renewable Services synthetic O&M corpus.

REPRODUCIBILITY CONTRACT
------------------------
Every structured field in the corpus is a deterministic function of MASTER_SEED.
We use stdlib `random.Random` (Mersenne Twister), which is stable across CPython
versions, rather than numpy, whose generator defaults have changed historically.

Substreams are derived by hashing (MASTER_SEED, stage_name) with SHA-256 rather
than by sequential spawning. This is deliberate: it makes each stage's stream
independent of how many other stages exist, so adding a generation stage later
does not perturb the output of stages written earlier.
"""

import hashlib
import random

MASTER_SEED = 20260824

CORPUS_VERSION = "1.0.0"
OPERATOR_NAME = "Northlight Renewable Services"

# ---------------------------------------------------------------- time window
WINDOW_START = "2024-07-01"
WINDOW_END = "2026-06-30"
WINDOW_MONTHS = 24


def substream(name: str) -> random.Random:
    """Return an independent, reproducible RNG for a named generation stage."""
    digest = hashlib.sha256(f"{MASTER_SEED}:{name}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


# ------------------------------------------------------------- corpus budget
# Total is approximate; the scheduler hits it within a small tolerance because
# per-site volume is driven by capacity x coverage-months x reporting culture.
TARGET_WORK_ORDERS = 2400

BUDGET = {
    "signal_1_thermal": 48,        # Kelvara KVP-3600 batch thermal defect
    "signal_2_backsheet": 26,      # Caprock Mesa backsheet degradation
    "decoy_1_tracker": 31,         # Sundowner Mesa wind event + logging artifact
    "distractor_slew_drive": 38,   # Auster slew drive grease - real, minor
    "distractor_comms": 44,        # Soltera ST-250 comms dropouts - real, minor
    # decoy_2 (normalization trap) is structural: it consumes no WO budget,
    # it is expressed through coverage windows on six sites.
}

# --------------------------------------------------------- narrative batching
# Batches are stratified shuffles across site/tech/month/plant-class, never
# contiguous slices. A batch that was all-planted would let batch-level style
# drift correlate with plant status.
NARRATIVE_BATCH_SIZE = 120

# ------------------------------------------------------------ leakage control
# Fields that must be distribution-matched between planted work orders and
# their matched background controls. Enforced in balance.py BEFORE narrative
# generation so that target lengths are matched by construction, not patched.
BALANCED_FIELDS = [
    "labor_hours",
    "narrative_target_words",
    "lost_production_present",
    "lost_production_magnitude",
    "parts_used_present",
    "priority",
    "field_completeness",
]

# Tokens that must never appear in anything written to corpus/.
# emit.py greps the serialized bytes for these and aborts on a hit.
FORBIDDEN_CORPUS_TOKENS = [
    "plant_class", "signal_id", "signal_1", "signal_2", "decoy",
    "distractor", "ground_truth", "GROUND_TRUTH", "planted",
    "narrative_brief", "severity_stage", "is_signal", "batch_defect",
]

# ------------------------------------------------------------------ paths
import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
CORPUS_DIR = _os.path.join(_ROOT, "corpus")
EVAL_DIR = _os.path.join(_ROOT, "eval")   # detection pipeline must never read this
CHECKPOINT_DIR = _os.path.join(_ROOT, ".checkpoints")
