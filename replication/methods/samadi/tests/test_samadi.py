"""Synthetic and equivalence tests for the Samadi IGT detector.

Usage (from replication/): python methods/samadi/tests/test_samadi.py
Default thresholds: gamma1 = 1.0, Threshold_act = 1.0 (the permissive grid corner).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from common.evaluation import detectors, load_config  # noqa: E402
from methods.samadi.src import samadi as S  # noqa: E402

CFG = load_config(*detectors.config_paths("samadi"))
FX = S.fixed_params(CFG)
DAY = pd.Timestamp("2025-01-01")
T = pd.date_range(DAY, periods=288, freq="5min")
MIN = np.arange(288) * 5.0
P = dict(gamma1=1.0, th_act=1.0)
FAILS = []


def det(g, **kw):
    return ((S.detect(T, g, {**FX, **P, **kw}) - DAY) / pd.Timedelta(minutes=1)).astype(int).tolist()


def igt(g, gamma1=1.0):
    d1, d2 = S.derivatives(g, FX["fit_points"], FX["sampling_min"])
    return S.igt(d1, d2, gamma1, FX["d2_scale_min"])


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name:55s} {info}")
    if not ok:
        FAILS.append(name)


def meal(base=95.0, start=480, acc=0.1, peak_slope=2.5, rise_min=40, fall=1.0):
    """Slope grows at acc mg/dL/min^2 up to peak_slope, rises for rise_min, then falls."""
    t = np.clip(MIN - start, 0, rise_min)
    t_acc = peak_slope / acc
    up = np.where(t < t_acc, 0.5 * acc * t ** 2, 0.5 * acc * t_acc ** 2 + peak_slope * (t - t_acc))
    down = np.clip(MIN - start - rise_min, 0, None) * fall
    return np.maximum(base + up - down, base)


def main():
    # 1. clean meal rise: detected shortly after the start
    d = det(meal())
    check("clean meal rise detected (first detection at the rise)", len(d) >= 1 and 480 <= d[0] <= 500,
          f"{d} (a later one can come where the fall levels off, S8)")

    # 2. flat glucose: IGT = 0, no detection
    v = igt(np.full(288, 100.0))
    check("flat glucose: IGT = 0", np.allclose(v[3:], 0), f"max |IGT| {np.nanmax(np.abs(v)):.3f}")
    check("flat glucose: no detection", det(np.full(288, 100.0)) == [])

    # 3. slow drift 0.3 mg/dL/min: IGT = 2 * 0.3 (E shape), below Threshold_act 1.0
    g = 90 + 0.3 * np.clip(MIN - 480, 0, 240)
    v = igt(g)
    check("slow drift 0.3 mg/dL/min: IGT <= 0.6 after onset", np.nanmax(v[100:]) <= 0.6 + 1e-9,
          f"max IGT after onset {np.nanmax(v[100:]):.2f}")
    check("slow drift: at most one detection, at the onset bend", len(det(g)) <= 1
          and all(475 <= x <= 495 for x in det(g)), f"{det(g)}")

    # 4. falling segment: IGT negative, no detection
    g = np.maximum(200 - 1.5 * np.clip(MIN - 600, 0, None), 80)
    v = igt(g)
    seg = v[(MIN > 615) & (MIN < 600 + 120 / 1.5 - 5)]
    check("falling 1.5 mg/dL/min: IGT <= -2", np.all(seg <= -2 + 1e-9), f"max IGT {seg.max():.2f}")
    d = det(g)
    check("falling segment: no detection during the fall", all(not (600 < x < 680) for x in d), f"{d}")

    # 5. one bad 5-min reading (+15 mg/dL): the simplified rule has no hysteresis. The spike flags
    #    at its own sample, and again 15 min later, when it is the oldest of the 4 fit points: the
    #    end-point derivative of a quadratic through (115, 100, 100, 100) is positive and the fit
    #    is convex, so the shape reads as an accelerating increase (deviations S8)
    g = np.full(288, 100.0)
    g[120] = 115.0
    d = det(g)
    v = igt(g)
    check("5-min spike: flags at the spike and 15 min later", d == [600, 615],
          f"{d}; IGT at +0, +5, +10, +15 min: {np.round(v[120:124], 2).tolist()}")
    d1, d2 = S.derivatives(np.array([115.0, 100, 100, 100]))
    check("convex corner: end-point d1G > 0, d2G > 0", d1[-1] > 0 and d2[-1] > 0,
          f"d1G {d1[-1]:.2f}, d2G {d2[-1]:.3f}")
    check("5-min spike: none with gamma1 = 4, Threshold_act = 3.0",
          det(g, gamma1=4.0, th_act=3.0) == [], f"{det(g, gamma1=4.0, th_act=3.0)}")

    # 6. missing-data gap: no IGT when any of the last 4 samples is missing; a later meal is found
    g = meal(start=540)
    g[84:88] = np.nan                     # 07:00-07:15
    v = igt(g)
    check("gap: IGT missing while the fit window touches it", np.isnan(v[84:91]).all() and
          np.isfinite(v[91]), "")
    d = det(g)
    check("gap: meal after the gap still detected, none near the gap",
          len(d) >= 1 and 540 <= d[0] <= 560 and not any(420 <= x <= 460 for x in d), f"{d}")

    # 7. IGT range and the accelerating-rise maximum
    rng = np.random.default_rng(2)
    worst = 0.0
    for gamma1 in CFG["methods"]["samadi"]["grid"]["gamma1"][:2] + [4.0]:
        for _ in range(50):
            g = 120 + np.cumsum(rng.normal(0, 3, 288))
            v = igt(g, gamma1)
            worst = max(worst, np.nanmax(np.abs(v)))
    check("IGT stays in [-3, 3] (random walks)", worst <= 3 + 1e-9, f"max |IGT| {worst:.3f}")
    g = 100 + 0.5 * 0.2 * np.clip(MIN - 480, 0, None) ** 2          # acc 0.2 mg/dL/min^2
    v = igt(g)
    check("steady accelerating rise: IGT near 3", np.all(v[(MIN >= 500) & (MIN <= 560)] > 2.9),
          f"IGT 500-560 min: {v[(MIN >= 500) & (MIN <= 560)].min():.3f}")

    # 8. detect_grid == detect on every grid point, synthetic and real CGMacros days
    from common.evaluation.data import build_cohort
    cohort = build_cohort(CFG)
    days = [(T, meal()), (T, 120 + np.cumsum(rng.normal(0, 2, 288)))]
    days += [cohort.day_series(d, 5) for d in cohort.days.sample(8, random_state=4).index]
    grid = S.param_grid(CFG)
    n_bad = n_det = 0
    for t, g in days:
        fast = S.detect_grid(t, g, CFG)
        assert len(fast) == len(grid)
        for i, p in enumerate(grid):
            slow = np.flatnonzero(np.isin(t, S.detect(t, g, {**FX, **p})))
            n_bad += not np.array_equal(slow, fast[i])
            n_det += len(slow)
    check(f"detect_grid equals detect, all {len(grid)} points x {len(days)} days", n_bad == 0,
          f"{n_det} detections compared")

    print("all samadi tests passed" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
