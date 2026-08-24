"""Date helpers and the seasonality model."""
from datetime import date, timedelta

WINDOW_START = date(2024, 7, 1)
WINDOW_END = date(2026, 6, 30)


def months_in_window():
    out, y, m = [], 2024, 7
    while (y, m) <= (2026, 6):
        out.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


ALL_MONTHS = months_in_window()


def parse(s):
    return date(int(s[:4]), int(s[5:7]), int(s[8:10]))


def coverage_start(site):
    """Earliest date this site can generate work: the plant must exist AND be
    under contract. Ten sites reach commercial operation after the window opens,
    which gives Decoy 2 a second, independent reason for low ticket volume."""
    return max(WINDOW_START,
               parse(site["om_contract_start"]),
               parse(site["commercial_operation_date"]))


def coverage_months(site):
    cs = coverage_start(site)
    return max(1, (WINDOW_END.year - cs.year) * 12 + (WINDOW_END.month - cs.month) + 1)


def random_day(rng, y, m):
    last = [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return date(y, m, rng.randint(1, last))


# ---------------------------------------------------------------------------
# SEASONALITY
#
# Background corrective work is deliberately SUMMER-HEAVY in every hot region
# and storm-heavy in the Southeast. This is the single most important piece of
# background noise in the corpus: if routine failures were flat across months
# while the planted thermal cluster ran May-September, then `month` alone would
# separate planted from background.
# ---------------------------------------------------------------------------
#            J    F    M    A    M    J    J    A    S    O    N    D
CM_SEASON = {
    "ERCOT_WEST":   [0.6, 0.6, 0.8, 0.9, 1.3, 1.7, 1.9, 1.9, 1.6, 1.0, 0.7, 0.6],
    "ERCOT_SOUTH":  [0.7, 0.7, 0.9, 1.0, 1.4, 1.7, 1.8, 1.8, 1.6, 1.1, 0.8, 0.7],
    "CAISO_CV":     [0.7, 0.7, 0.9, 1.0, 1.3, 1.6, 1.8, 1.8, 1.5, 1.1, 0.8, 0.7],
    "CAISO_MOJAVE": [0.7, 0.8, 1.0, 1.1, 1.3, 1.6, 1.8, 1.8, 1.5, 1.1, 0.9, 0.7],
    "MISO_UMW":     [1.4, 1.3, 1.0, 0.9, 0.9, 1.1, 1.3, 1.2, 1.0, 0.9, 1.1, 1.4],
    "PJM_MATL":     [0.9, 0.9, 1.0, 1.0, 1.1, 1.4, 1.6, 1.6, 1.3, 1.0, 0.9, 0.9],
    "SE_NONISO":    [0.8, 0.8, 1.0, 1.1, 1.2, 1.5, 1.7, 1.7, 1.6, 1.2, 0.9, 0.8],
}

PM_SEASON = [0.9, 1.0, 1.2, 1.3, 1.2, 1.0, 0.8, 0.8, 1.0, 1.2, 1.1, 0.9]

VEG_SEASON = {
    "SE_NONISO":    [0.2, 0.3, 0.9, 1.5, 1.8, 1.9, 1.8, 1.7, 1.4, 0.9, 0.4, 0.2],
    "PJM_MATL":     [0.1, 0.2, 0.7, 1.4, 1.8, 1.9, 1.8, 1.6, 1.2, 0.7, 0.3, 0.1],
    "MISO_UMW":     [0.1, 0.1, 0.4, 1.1, 1.7, 1.9, 1.8, 1.5, 1.0, 0.5, 0.2, 0.1],
    "ERCOT_WEST":   [0.3, 0.4, 0.8, 1.2, 1.4, 1.2, 0.9, 0.8, 0.9, 0.8, 0.5, 0.3],
    "ERCOT_SOUTH":  [0.4, 0.5, 1.0, 1.4, 1.6, 1.4, 1.1, 1.0, 1.1, 0.9, 0.6, 0.4],
    "CAISO_CV":     [0.3, 0.4, 0.9, 1.4, 1.5, 1.2, 0.8, 0.7, 0.8, 0.8, 0.5, 0.3],
    "CAISO_MOJAVE": [0.2, 0.2, 0.5, 0.7, 0.8, 0.6, 0.4, 0.4, 0.4, 0.4, 0.3, 0.2],
}

HOT_MONTHS = {5, 6, 7, 8, 9}
