"""Synthetic and equivalence tests for the Dassau detectors (dassau_2of3, dassau_3of4).

Usage (from replication/): python methods/dassau/tests/test_dassau.py
Uses permissive grid-corner thresholds: Threshold_ROC 1.0, Threshold_Acceleration 0.2,
Threshold_Glucose 100, Threshold_maxROC 5.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from common.evaluation import detectors, kalman, load_config  # noqa: E402
from methods.dassau.src import dassau as D  # noqa: E402

CFG = load_config(*detectors.config_paths("dassau_2of3"))
DAY = pd.Timestamp("2025-01-01")
T = pd.date_range(DAY, periods=1440, freq="1min")
MODS = {v: detectors.get(f"dassau_{v}") for v in ["2of3", "3of4"]}
PARAMS = {"2of3": dict(th_roc=1.0, th_acc=0.2),
          "3of4": dict(th_glucose=100.0, th_max_roc=5.0, th_roc=1.0, th_acc=0.2)}
FAILS = []


def hm(h, m=0):
    return 60 * h + m


def det(v, g):
    p = {**MODS[v].fixed_params(CFG), **PARAMS[v]}
    return ((MODS[v].detect(T, g, p) - DAY) / pd.Timedelta(minutes=1)).astype(int).tolist()


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name:55s} {info}")
    if not ok:
        FAILS.append(name)


def interp5(native):
    """1-min series from 5-min native readings (as the CGMacros Dexcom column)."""
    x5 = np.arange(0, 1440, 5)
    return np.interp(np.arange(1440), x5, native[x5])


def meal(base=95.0, start=hm(8), slope=2.5, rise_min=30, fall=1.5):
    t = np.arange(1440, dtype=float)
    up = np.clip(t - start, 0, rise_min) * slope
    peak_t = start + rise_min
    down = np.clip(t - peak_t, 0, None) * fall
    return interp5(np.maximum(base + up - down, base))


def main():
    # Kalman default criterion (deviations D6)
    k = CFG["kalman"]["dassau"]
    sd = kalman.noise_response_sd(1.0, k["meas_sd_mg_dl"], k["jerk_psd"])
    check("Kalman noise-only SD: ROC <= 0.25, acceleration <= 0.05", sd[1] <= 0.25 and sd[2] <= 0.05,
          f"glucose {sd[0]:.2f}, ROC {sd[1]:.3f}, acc {sd[2]:.4f}")

    # 1. clean meal rise: detected by both, shortly after the start
    g = meal()
    for v in MODS:
        d = det(v, g)
        check(f"clean meal rise detected ({v})", len(d) == 1 and hm(8) <= d[0] <= hm(8, 20), f"{d}")

    # 2. flat glucose: none
    for v in MODS:
        d = det(v, np.full(1440, 100.0))
        check(f"flat glucose: no detection ({v})", d == [], f"{d}")

    # 3. slow drift, 0.5 mg/dL/min for 4 h (below Threshold_ROC): none
    t = np.arange(1440, dtype=float)
    g = interp5(90 + 0.5 * np.clip(t - hm(8), 0, 240))
    for v in MODS:
        d = det(v, g)
        check(f"slow drift 0.5 mg/dL/min: no detection ({v})", d == [], f"{d}")

    # 4a. one bad 5-min reading (+20 mg/dL) at baseline 85 (below Threshold_Glucose)
    nat = np.full(1440, 85.0)
    nat[hm(10)] = 105.0
    g = interp5(nat)
    d2, d3 = det("2of3", g), det("3of4", g)
    check("5-min spike at 85 mg/dL: 3of4 none (KF off below 100)", d3 == [], f"2of3 {d2}, 3of4 {d3}")
    check("5-min spike at 85 mg/dL: 2of3 at most one, at the spike", len(d2) <= 1
          and all(hm(9, 55) <= x <= hm(10, 5) for x in d2), f"{d2}")
    # 4b. the same spike at 130 mg/dL (above Threshold_Glucose): KF can vote
    g = interp5(np.where(nat == 105.0, 150.0, 130.0))
    d2, d3 = det("2of3", g), det("3of4", g)
    check("5-min spike at 130 mg/dL: detections only at the spike", all(hm(9, 55) <= x <= hm(10, 5)
          for x in d2 + d3), f"2of3 {d2}, 3of4 {d3}")
    # 4c. a single 1-min spike (one raw sample): BD flips sign, no 5-sample window passes
    g = np.full(1440, 130.0)
    g[hm(10)] = 150.0
    for v in MODS:
        d = det(v, g)
        check(f"single 1-min spike: no detection ({v})", d == [], f"{d}")

    # 5. missing-data gap: 20 min missing at 07:00; a meal at 09:00 still found, nothing in or
    #    right after the gap; a gap inside a rise blocks every window that touches it
    g = meal(start=hm(9))
    g[hm(7):hm(7, 20)] = np.nan
    for v in MODS:
        d = det(v, g)
        check(f"gap before meal: meal found, none near gap ({v})",
              len(d) == 1 and hm(9) <= d[0] <= hm(9, 20), f"{d}")
    g = meal(start=hm(9), rise_min=40)
    g[hm(9, 15):hm(9, 25)] = np.nan
    for v in MODS:
        d = det(v, g)
        bad = [x for x in d if hm(9, 11) <= x < hm(9, 35)]
        check(f"gap inside rise: no window touches the gap ({v})", bad == [], f"{d}")

    # 6. 3of4 flags imply 2of3 flags at the same Threshold_ROC / Threshold_Acceleration
    #    (3 of BD, BDK, KF, ACC true => at least 2 of BD, BDK, ACC true); clean meal + real days
    from common.evaluation.data import build_cohort
    cohort = build_cohort(CFG)
    real = [cohort.day_series(d, 1) for d in cohort.days.sample(6, random_state=3).index]
    fixed = MODS["2of3"].fixed_params(CFG)
    n2 = n3 = viol = 0
    for _, g in [(T, meal())] + real:
        sig = D.signals(g, fixed)
        f2 = D.mda(D.indicators(sig, PARAMS["2of3"]), "2of3", 5)
        f3 = D.mda(D.indicators(sig, PARAMS["3of4"]), "3of4", 5)
        n2, n3, viol = n2 + f2.sum(), n3 + f3.sum(), viol + (f3 & ~f2).sum()
    check("3of4 flags imply 2of3 flags", viol == 0 and n3 > 0, f"{n3} vs {n2} flagged samples")

    # 7. detect_grid == detect on random grid points, synthetic and real CGMacros days
    rng = np.random.default_rng(1)
    days = [(T, meal() + rng.normal(0, 0.5, 1440)), (T, meal())] + real
    for v, mod in MODS.items():
        grid = mod.param_grid(CFG)
        pts = rng.choice(len(grid), 40, replace=False)
        n_bad = n_det = 0
        for t, g in days:
            fast = mod.detect_grid(t, g, CFG)
            assert len(fast) == len(grid)
            for i in pts:
                slow = np.flatnonzero(np.isin(t, mod.detect(t, g, {**mod.fixed_params(CFG), **grid[i]})))
                n_bad += not np.array_equal(slow, fast[i])
                n_det += len(slow)
        check(f"detect_grid equals detect, 40 points x {len(days)} days ({v})", n_bad == 0,
              f"{n_det} detections compared")

    print("all dassau tests passed" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
