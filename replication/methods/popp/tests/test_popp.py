"""Synthetic, timing and equivalence tests for the Popp SBE detector.

Usage (from replication/): python methods/popp/tests/test_popp.py
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from common.evaluation import detectors, load_config  # noqa: E402
from methods.popp.src import popp as P  # noqa: E402

CFG = load_config(*detectors.config_paths("popp"))
FX = P.fixed_params(CFG)
DAY = pd.Timestamp("2025-01-01")
T = pd.date_range(DAY, periods=1440, freq="1min")
MIN = np.arange(1440, dtype=float)
HOCH = dict(phi_pct=10.0, tau_min=20.0, eps=18.0)       # Hochsmann Table 1 global set
WIDE = dict(phi_pct=10.0, tau_min=60.0, eps=18.0)
FAILS = []
GB = P.basal_state()[0] / P.DM["V_G"]


def det(g, prm):
    idx, mst = P.detect_details(T, g, {**FX, **prm})
    return idx.tolist(), mst.tolist()


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name:60s} {info}")
    if not ok:
        FAILS.append(name)


def model_meal(load, start=480, base=GB):
    g = np.full(1440, base)
    r = P.meal_response(float(load), float(FX["meal_duration_min"]), 1440 - start - 1)
    g[start:] = base + r[:1440 - start]
    return g


def interp5(native):
    x5 = np.arange(0, 1440, 5)
    return np.interp(MIN, x5, native[x5])


def main():
    # model sanity: no drift at basal, meal responses grow with the load
    g = P.simulate(np.array(P.basal_state()), 600)
    peaks = [P.meal_response(float(m), 90.0, 240).max() for m in FX["loads_g"]]
    check("model: no drift at the basal steady state", np.ptp(g) < 1e-6, f"basal G {GB:.2f} mg/dL")
    check("model: peak rise increases with the load", np.all(np.diff(peaks) > 0),
          "peaks " + ", ".join(f"{p:.1f}" for p in peaks))

    # 1. synthetic 50 g meal built from the model itself (start 08:00)
    g = model_meal(50)
    idx, mst = det(g, WIDE)
    check("model meal 50 g: detected (tau 60)", len(idx) >= 1, f"detection +{idx[0] - 480 if idx else None} min")
    check("model meal 50 g: m_st within 30 min of the true start (tau 60)",
          len(mst) >= 1 and 480 <= mst[0] <= 510, f"m_st +{mst[0] - 480 if mst else None} min")
    idx_h, _ = det(g, HOCH)
    check("model meal 50 g, tau 20: not detected (anchor only 30 min back, P14)", idx_h == [],
          f"{idx_h}")
    # a real-like rise of 1 mg/dL/min for 60 min is detected with Hochsmann's set; a fast rise of
    # 2 mg/dL/min is not: when Div passes 10 %, the near-flat early meal curves already miss the
    # observed rise by more than epsilon (P14)
    g = interp5(np.maximum(100 + np.clip(MIN - 480, 0, 60) * 1.0 - np.clip(MIN - 540, 0, None), 100))
    idx, mst = det(g, HOCH)
    check("rise 1 mg/dL/min: detected with tau 20", len(idx) >= 1 and 480 <= idx[0] <= 540,
          f"detection +{idx[0] - 480 if idx else None}, m_st +{mst[0] - 480 if mst else None} min")
    g = interp5(np.maximum(100 + np.clip(MIN - 480, 0, 40) * 2.0 - np.clip(MIN - 520, 0, None), 100))
    hits = {p["tau_min"]: det(g, {**HOCH, "tau_min": p["tau_min"]})[0] for p in [HOCH, WIDE]}
    check("rise 2 mg/dL/min: not detected (tau 20 and 60, P14)", all(v == [] for v in hits.values()),
          f"{hits}")

    # 2. flat glucose and the model's own no-meal trajectory: none
    check("flat glucose: no detection", all(det(np.full(1440, 120.0), p)[0] == [] for p in [HOCH, WIDE]))
    x0 = np.array(P.basal_state())
    x0[0] *= 150 / GB                                      # start at 150 mg/dL, relax to basal
    g = P.simulate(x0, 1439)
    check("model's own no-meal trajectory (150 -> basal): no detection",
          all(det(g, p)[0] == [] for p in [HOCH, WIDE]), f"G {g[0]:.0f} -> {g[-1]:.0f}")

    # 3. slow drift 0.3 mg/dL/min for 4 h: none with tau 20; with tau 60 the anchor is 60 min back,
    #    the 30-min mean deviation passes 10 % and the near-flat early meal curves fit (P14)
    g = interp5(110 + 0.3 * np.clip(MIN - 480, 0, 240))
    check("slow drift 0.3 mg/dL/min: no detection with tau 20", det(g, HOCH)[0] == [],
          f"tau 60: {det(g, WIDE)[0]}")

    # 4. noise spike: one bad 5-min reading (+20 mg/dL)
    nat = np.full(1440, 110.0)
    nat[600] = 130.0
    g = interp5(nat)
    check("5-min spike: no detection", all(det(g, p)[0] == [] for p in [HOCH, WIDE]))

    # 5. missing-data gap: no signal while the window touches the gap; a later meal is found
    g = interp5(np.maximum(100 + np.clip(MIN - 600, 0, 60) * 1.0 - np.clip(MIN - 660, 0, None), 100))
    g[500:520] = np.nan
    div, dmin, _ = P.candidate_signals(g, FX, 20)
    check("gap: Div missing while the window touches the gap",
          np.isnan(div[500:550]).all() and np.isfinite(div[550]), "")
    idx, _ = det(g, HOCH)
    check("gap: meal after the gap detected", len(idx) >= 1 and 600 <= idx[0] <= 660, f"{idx}")

    # 6. timing and detect_grid == detect on 10 real days x all 50 grid points
    from common.evaluation.data import build_cohort
    cohort = build_cohort(CFG)
    days = [cohort.day_series(d, 1) for d in cohort.days.sample(10, random_state=8).index]
    t0 = time.time()
    P.detect_grid(*days[0], CFG)
    t_day = time.time() - t0
    grid = P.param_grid(CFG)
    n_bad = n_det = 0
    for t, g in days:
        fast = P.detect_grid(t, g, CFG)
        for i, p in enumerate(grid):
            slow = np.flatnonzero(np.isin(t, P.detect(t, g, {**FX, **p})))
            n_bad += not np.array_equal(slow, fast[i])
            n_det += len(slow)
    check(f"detect_grid equals detect, all {len(grid)} points x {len(days)} real days", n_bad == 0,
          f"{n_det} detections compared; detect_grid {t_day:.2f} s per day")

    print("all popp tests passed" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
