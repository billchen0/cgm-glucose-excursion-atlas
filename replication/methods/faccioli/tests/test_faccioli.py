"""Synthetic and equivalence tests for the Faccioli STMD detector.

Usage (from replication/): python methods/faccioli/tests/test_faccioli.py
Default thresholds: Th_Res = 1.0 mg/dL, Th_Der = 0.2 mg/dL/min (the permissive grid corner).
Cases 1-7 use the night gain rule (F5a; a flat night gives L = 0.02). Case 8 checks that the
grid gain (F5b) with L set to the night value gives the same detections, and case 9 checks
detect_grid against detect in both modes.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from common.evaluation import detectors, load_config  # noqa: E402
from methods.faccioli.src import faccioli as F  # noqa: E402

CFG = load_config(*detectors.config_paths("faccioli"))
FX = {**F.fixed_params(CFG), "gain_rule": "night"}
FXG = F.fixed_params(CFG)                          # committed: gain_rule "grid"
DAY = pd.Timestamp("2025-01-01")
T = pd.date_range(DAY, periods=288, freq="5min")
MIN = np.arange(288) * 5.0
P = dict(th_res=1.0, th_der=0.2)
FAILS = []
RNG = np.random.default_rng(5)


def det(g, **kw):
    return ((F.detect(T, g, {**FX, **P, **kw}) - DAY) / pd.Timedelta(minutes=1)).astype(int).tolist()


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name:58s} {info}")
    if not ok:
        FAILS.append(name)


def meal(base=95.0, start=480, acc=0.1, peak_slope=2.0, rise_min=45, fall=1.0):
    t = np.clip(MIN - start, 0, rise_min)
    t_acc = peak_slope / acc
    up = np.where(t < t_acc, 0.5 * acc * t ** 2, 0.5 * acc * t_acc ** 2 + peak_slope * (t - t_acc))
    down = np.clip(MIN - start - rise_min, 0, None) * fall
    return np.maximum(base + up - down, base)


def main():
    # 1. clean meal rise: detected shortly after the start
    d = det(meal())
    check("clean meal rise detected", len(d) >= 1 and 480 <= d[0] <= 515, f"{d}")

    # 2. flat glucose: residual 0, no detection
    s = F.signals(T, np.full(288, 100.0), FX)
    check("flat glucose: residual 0", np.nanmax(np.abs(s["res"])) == 0, f"L {s['L']:.3f} (floor)")
    check("flat glucose: no detection", det(np.full(288, 100.0)) == [])

    # 3. slow drift 0.3 mg/dL/min from 08:00 for 4 h: residual near 0, no detection
    g = 90 + 0.3 * np.clip(MIN - 480, 0, 240)
    s = F.signals(T, g, FX)
    after = s["res"][(MIN >= 540) & (MIN <= 700)]
    check("slow drift: |Res| < 1 everywhere, 0 once settled",
          np.nanmax(np.abs(s["res"])) < 1.0 and np.allclose(after, 0),
          f"max |Res| {np.nanmax(np.abs(s['res'])):.2f}")
    check("slow drift: no detection", det(g) == [], f"{det(g)}")

    # 4. single noise spike (+20 mg/dL at one 5-min sample): removed by the median filter
    g = np.full(288, 110.0)
    g[144] = 130.0
    s = F.signals(T, g, FX)
    check("single spike: median-filtered trace is flat", np.allclose(s["cgm"][2:], 110.0), "")
    check("single spike: no detection", det(g) == [], f"{det(g)}")
    raw = {**FX, "median_points": 1}
    check("single spike without the median filter: Res responds",
          np.nanmax(F.signals(T, g, raw)["res"]) > 1.0,
          f"max Res {np.nanmax(F.signals(T, g, raw)['res']):.2f}")

    # 5. missing-data gap: restart, no detection touching the gap, a later meal still found
    g = meal(start=600)
    g[132:136] = np.nan                  # 11:00-11:15
    s = F.signals(T, g, FX)
    check("gap: Res missing inside the gap and right after (median)",
          np.isnan(s["res"][132:138]).all() and np.isfinite(s["res"][138]), "")
    d = det(g)
    check("gap: meal after the gap detected, none at the gap",
          len(d) >= 1 and 600 <= d[0] <= 635 and not any(655 <= x <= 690 for x in d), f"{d}")

    # 6. implicit observer satisfies Faccioli Eq. 4 at every step
    y = 120 + np.cumsum(RNG.normal(0, 2, 288))
    L, h = 0.3, 5.0
    res, lam, _ = F.observer(y, L, h)
    st = y - res
    k1, k2 = 1.5 * np.sqrt(L), 1.1 * L
    u = np.cumsum(h * k2 * np.r_[0.0, lam[1:]])
    lhs = st[1:] - st[:-1]
    rhs = h * u[1:] + h * k1 * np.sqrt(np.abs(res[1:])) * lam[1:]
    ok = np.allclose(lhs, rhs, atol=1e-9) and np.all(np.abs(lam) <= 1 + 1e-12) and \
        np.all((res == 0) | (np.sign(res) == lam))
    check("observer: implicit Eq. 4 holds, lambda in msign(res)", ok,
          f"max error {np.max(np.abs(lhs - rhs)):.1e}")

    # 7. gain rule: L = max over the night of g~(k-1) / h^2 (non-saturated observer)
    g = 100 + np.cumsum(RNG.normal(0, 1.5, 288))
    cgm = F.median3(g)
    _, _, gt = F.observer(cgm, FX["l_provisional"], 5.0)
    fh = np.r_[np.nan, gt[:-1] / 25.0]
    expect = max(np.nanmax(fh[MIN < 420]), FX["l_floor"])
    got = F.day_gain(cgm, MIN, FX)
    check("gain rule: L = max night F_hat", np.isclose(got, expect), f"L {got:.3f}")

    # 8. grid gain with L = the night value gives the same detections as the night rule
    from common.evaluation.data import build_cohort
    cohort = build_cohort(CFG)
    days = [(T, meal()), (T, 120 + np.cumsum(RNG.normal(0, 2, 288)))]
    days += [cohort.day_series(d, 5) for d in cohort.days.sample(8, random_state=6).index]
    n_bad = 0
    for t, g in days:
        L = F.signals(t, g, FX)["L"]
        a = F.detect(t, g, {**FX, **P})
        b = F.detect(t, g, {**FXG, **P, "l_bound": L})
        n_bad += not a.equals(b)
    check(f"grid gain with L = night value equals night rule ({len(days)} days)", n_bad == 0)

    # 9. detect_grid == detect: night mode on every point, grid mode on 150 random points
    import copy
    cfg_n = copy.deepcopy(CFG)
    cfg_n["methods"]["faccioli"]["observer"]["gain_rule"] = "night"
    del cfg_n["methods"]["faccioli"]["grid"]["l_bound"]
    for label, cfg, fx in [("night", cfg_n, FX), ("grid", CFG, FXG)]:
        grid = F.param_grid(cfg)
        pts = range(len(grid)) if label == "night" else RNG.choice(len(grid), 150, replace=False)
        n_bad = n_det = 0
        for t, g in days:
            fast = F.detect_grid(t, g, cfg)
            assert len(fast) == len(grid)
            for i in pts:
                slow = np.flatnonzero(np.isin(t, F.detect(t, g, {**fx, **grid[i]})))
                n_bad += not np.array_equal(slow, fast[i])
                n_det += len(slow)
        check(f"detect_grid equals detect, {label} gain, {len(pts)} of {len(grid)} points x {len(days)} days",
              n_bad == 0, f"{n_det} detections compared")

    print("all faccioli tests passed" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
