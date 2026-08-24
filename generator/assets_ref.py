"""Asset reference strings for equipment that is not in the serial-level registry.

The registry (corpus/assets.json) covers central inverters only, which is how a
lot of real CMMS asset registers actually look: major equipment is tracked by
serial, balance-of-plant is tracked by positional tag. Documented as such in the
data dictionary.
"""

def block_tag(rng, n_blocks, low_bias=False):
    if low_bias:
        b = rng.choices(range(1, n_blocks + 1),
                        weights=[max(1, n_blocks - i) for i in range(n_blocks)])[0]
    else:
        b = rng.randint(1, n_blocks)
    return f"B{b:02d}"


def combiner(rng, n_blocks=10, block=None):
    b = block or block_tag(rng, n_blocks)
    return f"CB-{b}-{rng.randint(1, 24):02d}"


def tracker_row(rng, n_blocks=10, block=None):
    b = block or block_tag(rng, n_blocks)
    return f"TR-{b}-R{rng.randint(1, 96):03d}"


def tracker_zone(rng, n_zones=12):
    return f"TR-Z{rng.randint(1, n_zones):02d}"


def transformer(rng, n_blocks=10):
    return f"XFMR-{block_tag(rng, n_blocks)}"


def bess_rack(rng):
    return f"CX-R{rng.randint(1, 24):02d}"


def string_inv(rng, model_prefix, cod_year):
    yy = (cod_year - rng.randint(0, 1)) % 100
    ww = rng.randint(1, 52)
    letter = "ABCD"[min((ww - 1) // 13, 3)]
    return f"{model_prefix}-{yy:02d}{ww:02d}{letter}-{rng.randint(100, 999):04d}"


def met_station(rng):
    return f"MET-{rng.randint(1, 4):02d}"


def n_blocks_for(mwdc):
    return max(4, min(20, round(mwdc / 22)))
