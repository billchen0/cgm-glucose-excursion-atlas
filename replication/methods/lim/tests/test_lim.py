"""Synthetic and equivalence tests for the Lim wavelet PPGR detector.

Usage (from replication/): python methods/lim/tests/test_lim.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from common.evaluation import detectors, load_config  # noqa: E402
from methods.lim.src import lim as L  # noqa: E402

CFG = load_config(*detectors.config_paths("lim"))
FX = L.fixed_params(CFG)
DAY = pd.Timestamp("2025-01-01")
T = pd.date_range(DAY, periods=288, freq="5min")
MIN = np.arange(288) * 5.0
FAILS = []


def det(g, h=10.0):
    ds = L.detect_details(T, g, {**FX, "min_height": h})
    return [(d["window"], int(MIN[d["start"]]), int(MIN[d["peak"]]), round(d["height"], 1)) for d in ds]


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name:58s} {info}")
    if not ok:
        FAILS.append(name)


def bump(start, rise, height, fall=None, base=0.0):
    """Raised-cosine PPGR: start, rise to the peak over `rise` min, back over `fall` min."""
    fall = fall or rise
    x = MIN - start
    up = np.where((x >= 0) & (x <= rise), 0.5 * (1 - np.cos(np.pi * x / rise)), 0)
    dn = np.where((x > rise) & (x <= rise + fall), 0.5 * (1 + np.cos(np.pi * (x - rise) / fall)), 0)
    return base + height * (up + dn)


def main():
    rng = np.random.default_rng(9)

    # 1. synthetic breakfast PPGR (start 08:00, peak 09:00, +45 mg/dL), small noise: found, start close
    g = 90 + bump(480, 60, 45) + rng.normal(0, 1.0, 288)
    d = det(g)
    b = [x for x in d if x[0] == "breakfast"]
    check("breakfast PPGR: found", len(b) == 1, f"{d}")
    check("breakfast PPGR: start within 15 min of 08:00", len(b) == 1 and abs(b[0][1] - 480) <= 15,
          f"start {b[0][1] - 480 if b else None} min from 08:00")

    # 2. flat day: none
    check("flat day: no PPGR", det(np.full(288, 100.0)) == [])

    # 3. rise below 10 mg/dL: none (found at threshold 5, so the threshold is what blocks it)
    g = 95 + bump(480, 60, 8)
    check("rise of 8 mg/dL: no PPGR at 10", det(g) == [], f"at 5: {det(g, 5.0)}")

    # 4. two rises in one window: the higher one is kept
    g = 95 + bump(420, 45, 20) + bump(570, 60, 50)       # 07:00 (+20) and 09:30 (+50)
    b = [x for x in det(g) if x[0] == "breakfast"]
    check("two rises in breakfast: the higher one kept", len(b) == 1 and abs(b[0][1] - 570) <= 15
          and b[0][3] > 40, f"{b}")

    # 5. rise outside both windows (17:30): ignored
    g = 95 + bump(1050, 60, 50)
    check("rise at 17:30 (outside the windows): ignored", det(g) == [], f"{det(g)}")

    # 6. one per window at most; breakfast and lunch both found
    g = 95 + bump(480, 60, 40) + bump(750, 60, 40) + rng.normal(0, 1.0, 288)
    d = det(g)
    check("breakfast and lunch rises: one PPGR each", [x[0] for x in d] == ["breakfast", "lunch"], f"{d}")

    # 7. thresholds 20 and 30 drop the smaller rises
    g = 95 + bump(480, 60, 25) + bump(750, 60, 15)
    check("heights 25 and 15: 2 at 10, 1 at 20, 0 at 30",
          [len(det(g, h)) for h in (10, 20, 30)] == [2, 1, 0], f"{[len(det(g, h)) for h in (10, 20, 30)]}")

    # 8. a window with missing data gives no PPGR there
    g = 95 + bump(480, 60, 40) + bump(750, 60, 40)
    g[100:106] = np.nan                                  # 08:20-08:45
    check("missing data in breakfast: no breakfast PPGR, lunch kept",
          [x[0] for x in det(g)] == ["lunch"], f"{det(g)}")

    # 9. detect_grid == detect on real days
    from common.evaluation.data import build_cohort
    cohort = build_cohort(CFG)
    days = [cohort.day_series(d, 5) for d in cohort.days.sample(10, random_state=10).index]
    n_bad = n_det = 0
    for t, g in days:
        fast = L.detect_grid(t, g, CFG)
        for i, p in enumerate(L.param_grid(CFG)):
            slow = np.flatnonzero(np.isin(t, L.detect(t, g, {**FX, **p})))
            n_bad += not np.array_equal(slow, fast[i])
            n_det += len(slow)
    check("detect_grid equals detect on 10 real days", n_bad == 0, f"{n_det} detections")

    print("all lim tests passed" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
