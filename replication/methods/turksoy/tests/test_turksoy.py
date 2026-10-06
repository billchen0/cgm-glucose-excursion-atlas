"""Synthetic, stability and equivalence tests for the Turksoy UKF detector.

Usage (from replication/): python methods/turksoy/tests/test_turksoy.py
Default threshold: Threshold_Ra = 1.5 mg/dL/min (the permissive grid end).
Outputs start after the 120-min warm-up (deviations T8). On flat glucose R_a settles near 0.4,
not 0: trimming sigma points at R_a >= 0 and I_eff >= 0 biases the mean upward (T7).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from common.evaluation import detectors, load_config  # noqa: E402
from methods.turksoy.src import turksoy as T  # noqa: E402

CFG = load_config(*detectors.config_paths("turksoy"))
FX = T.fixed_params(CFG)
DAY = pd.Timestamp("2025-01-01")
TT = pd.date_range(DAY, periods=1440, freq="1min")
MIN = np.arange(1440, dtype=float)
P = dict(th_ra=1.5)
FAILS = []


def det(g, **kw):
    return ((T.detect(TT, g, {**FX, **P, **kw}) - DAY) / pd.Timedelta(minutes=1)).astype(int).tolist()


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name:58s} {info}")
    if not ok:
        FAILS.append(name)


def interp5(native):
    x5 = np.arange(0, 1440, 5)
    return np.interp(MIN, x5, native[x5])


def meal(base=95.0, start=480, slope=2.0, rise_min=40, fall=1.0):
    up = np.clip(MIN - start, 0, rise_min) * slope
    down = np.clip(MIN - start - rise_min, 0, None) * fall
    return interp5(np.maximum(base + up - down, base))


def main():
    lo, hi = np.array(FX["ukf_lo"]), np.array(FX["ukf_hi"])

    # 1. clean meal rise: R_a rises, detected shortly after the start
    g = meal()
    s = T.ukf(g, FX)
    d = det(g)
    check("clean meal rise: R_a > 1.5 during the rise", np.nanmax(s["R_a"][480:520]) > 1.5,
          f"max R_a {np.nanmax(s['R_a'][480:520]):.2f}")
    check("clean meal rise: detected within 30 min", len(d) >= 1 and 480 <= d[0] <= 510, f"{d}")

    # 2. flat glucose: R_a below the lowest threshold after warm-up, no detection
    g = np.full(1440, 110.0)
    s = T.ukf(g, FX)
    check("flat glucose: R_a < 1.5 (lowest threshold) after warm-up", np.nanmax(s["R_a"][120:]) < 1.5,
          f"max R_a {np.nanmax(s['R_a'][120:]):.2f}, at 24 h {s['R_a'][-1]:.2f}")
    check("flat glucose: outputs missing during the 120-min warm-up", np.isnan(s["R_a"][:120]).all()
          and np.isfinite(s["R_a"][120]))
    check("flat glucose: no detection", det(g) == [], f"{det(g)}")

    # 3. slow drift 0.3 mg/dL/min from 08:00 for 4 h. R_a responds to a sustained rise (G_b lags
    #    30-60 min, and the filter can trade p1 against R_a), reaching about 1.6: a drift can
    #    trigger at the low end of the grid (T10). It stays below the grid top.
    g = interp5(110 + 0.3 * np.clip(MIN - 480, 0, 240))
    s = T.ukf(g, FX)
    hits = {th: det(g, th_ra=th) for th in [1.5, 1.6, 1.7, 2.0]}
    check("slow drift 0.3 mg/dL/min: R_a < 2.5, none at Threshold_Ra 2.0", np.nanmax(s["R_a"][480:]) < 2.5
          and hits[2.0] == [], f"max R_a {np.nanmax(s['R_a'][480:]):.2f}; detections by threshold {hits}")

    # 4. noise spike: one bad 5-min reading (+20 mg/dL; a 10-min triangle at 1 min)
    nat = np.full(1440, 130.0)
    nat[600] = 150.0
    g = interp5(nat)
    s = T.ukf(g, FX)
    d = det(g)
    check("5-min spike: at most one detection, at the spike", len(d) <= 1 and all(595 <= x <= 610 for x in d),
          f"{d}; max R_a {np.nanmax(s['R_a'][590:620]):.2f}")

    # 5. missing-data gap: restart with a 120-min warm-up, a later meal is still found
    g = meal(start=660)
    g[400:420] = np.nan                  # 06:40-06:59
    s = T.ukf(g, FX)
    d = det(g)
    check("gap: outputs missing in the gap and for 120 min after",
          np.isnan(s["R_a"][400:540]).all() and np.isfinite(s["R_a"][540]), "")
    check("gap: meal after the warm-up detected, none at the restart",
          len(d) >= 1 and 660 <= d[0] <= 690 and not any(540 <= x < 660 for x in d), f"{d}")

    # 6. a rise below 100 mg/dL: R_a passes the threshold but the G_s condition blocks it
    g = meal(base=50.0, slope=2.0, rise_min=20)          # 50 -> 90 mg/dL
    s = T.ukf(g, FX)
    check("rise below 100 mg/dL: R_a > 1.5", np.nanmax(s["R_a"][480:]) > 1.5,
          f"max R_a {np.nanmax(s['R_a'][480:]):.2f}")
    check("rise below 100 mg/dL: no detection", det(g) == [], f"{det(g)}")
    g2 = meal(base=100.0, slope=2.0, rise_min=20)        # the same rise from 100 mg/dL: detected
    check("the same rise from 100 mg/dL: detected", len(det(g2)) >= 1, f"{det(g2)}")

    # 7. stability over 5 real full days: no NaN, positive variances, states within bounds
    from common.evaluation.data import build_cohort
    cohort = build_cohort(CFG)
    real = [cohort.day_series(d, 1) for d in cohort.days.sample(5, random_state=7).index]
    ok, info = True, []
    for t, g in real:
        s = T.ukf(g, FX)
        valid = np.isfinite(g)
        est = np.column_stack([s[k] for k in T.STATES])
        var = np.column_stack([s[f"var_{k}"] for k in T.STATES])
        m = np.isfinite(est).all(1)
        ok &= m.sum() >= valid.sum() - 120 * (1 + np.sum(np.diff(valid.astype(int)) == 1))
        ok &= bool((var[m] > 0).all())
        ok &= bool(((est[m] >= lo - 1e-9) & (est[m] <= hi + 1e-9)).all())
        info.append(f"floors {s['n_floor']}")
    check("stability: 5 real days, no NaN, variances > 0, within bounds", ok, ", ".join(info))

    # 8. detect_grid == detect on every grid point
    days = [(TT, meal()), (TT, interp5(130 + np.cumsum(np.random.default_rng(3).normal(0, 2, 1440))))]
    days += real
    grid = T.param_grid(CFG)
    n_bad = n_det = 0
    for t, g in days:
        fast = T.detect_grid(t, g, CFG)
        for i, p in enumerate(grid):
            slow = np.flatnonzero(np.isin(t, T.detect(t, g, {**FX, **p})))
            n_bad += not np.array_equal(slow, fast[i])
            n_det += len(slow)
    check(f"detect_grid equals detect, all {len(grid)} points x {len(days)} days", n_bad == 0,
          f"{n_det} detections compared")

    print("all turksoy tests passed" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
