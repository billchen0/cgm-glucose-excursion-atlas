"""Samadi et al. 2018 fuzzy-logic meal detector (increase of glucose trend, IGT), simplified as in
the Hochsmann 2026 review (Supplementary Methods "Algorithm by Samadi et al.", Supplementary
Table 1 Equations 14-15). Details: methods/samadi/docs/deviations.md.

Per 5-min sample i:
  1. quadratic least-squares fit to the four most recent glucose points (t = -15, -10, -5, 0 min);
     d1G(i) = slope and d2G(i) = second derivative of the fit at t = 0 (S2);
  2. fuzzy sets negative / zero / positive for d1G with centres -gamma1, 0, +gamma1 (mg/dL/min),
     and for d2G with centres -gamma2, 0, +gamma2, gamma2 = gamma1 / 15 min (S3, S4);
  3. seven shapes (Samadi 2018 Fig. 2), membership = product of the two sign memberships (S5):
     B = N1*N2, F = N1*Z2, C = N1*P2, G = Z1, A = P1*N2, E = P1*Z2, D = P1*P2;
  4. IGT(i) = (-3B - 2F - C + A + 2E + 3D) / (A + B + C + D + E + F + G)      (Eq. 14)
  5. MDA(i) = 1 if IGT(i) > Threshold_act                                     (Eq. 15)
A detection is the first sample of each run of MDA = 1 (rising edge). The activation, pause and
deactivation logic of the original is omitted, as in the review (S1).
"""
import itertools

import numpy as np
import pandas as pd

PARAMS = ["gamma1", "th_act"]
SHAPES = ["B", "F", "C", "G", "A", "E", "D"]
WEIGHTS = {"B": -3, "F": -2, "C": -1, "G": 0, "A": 1, "E": 2, "D": 3}


def _axis(spec):
    start, stop, step = spec
    return np.round(np.arange(start, stop + step / 2, step), 6)


def grid_axes(cfg):
    g = cfg["methods"]["samadi"]["grid"]
    return {p: _axis(g[p]) for p in PARAMS}


def param_grid(cfg):
    ax = grid_axes(cfg)
    return [dict(zip(PARAMS, map(float, v))) for v in itertools.product(*(ax[p] for p in PARAMS))]


def fixed_params(cfg):
    m = cfg["methods"]["samadi"]
    return {"fit_points": m["fit_points"], "d2_scale_min": m["d2_scale_min"],
            "sampling_min": m["sampling_min"]}


def derivatives(glucose, fit_points=4, dt=5.0):
    """(d1G, d2G) of the quadratic least-squares fit to the last ``fit_points`` samples,
    evaluated at the newest sample. NaN if any of those samples is missing."""
    g = np.asarray(glucose, float)
    n = len(g)
    t = dt * np.arange(-(fit_points - 1), 1)              # e.g. -15, -10, -5, 0
    X = np.column_stack([np.ones(fit_points), t, t ** 2])
    W = np.linalg.pinv(X)                                  # 3 x fit_points: coefficients = W @ y
    d1, d2 = np.full(n, np.nan), np.full(n, np.nan)
    if n >= fit_points:
        win = np.lib.stride_tricks.sliding_window_view(g, fit_points)   # rows: samples i-3..i
        d1[fit_points - 1:] = win @ W[1]                   # b
        d2[fit_points - 1:] = 2 * (win @ W[2])             # 2c
    return d1, d2


def sign_memberships(x, centre):
    """Linear negative / zero / positive sets with centres -centre, 0, +centre (sum to 1)."""
    with np.errstate(invalid="ignore"):
        pos = np.clip(x / centre, 0, 1)
        neg = np.clip(-x / centre, 0, 1)
    return neg, 1 - pos - neg, pos


def shapes(d1, d2, gamma1, d2_scale_min):
    """Membership of each of the seven shapes (dict of arrays)."""
    n1, z1, p1 = sign_memberships(d1, gamma1)
    n2, z2, p2 = sign_memberships(d2, gamma1 / d2_scale_min)
    return dict(B=n1 * n2, F=n1 * z2, C=n1 * p2, G=z1, A=p1 * n2, E=p1 * z2, D=p1 * p2)


def igt(d1, d2, gamma1, d2_scale_min):
    """Eq. 14."""
    m = shapes(d1, d2, gamma1, d2_scale_min)
    num = sum(WEIGHTS[s] * m[s] for s in SHAPES)
    den = sum(m[s] for s in SHAPES)
    with np.errstate(invalid="ignore", divide="ignore"):
        return num / den


def rising(flag):
    prev = np.zeros(flag.shape, bool)
    prev[..., 1:] = flag[..., :-1]
    return flag & ~prev


def detect(times, glucose, params):
    d1, d2 = derivatives(glucose, int(params["fit_points"]), float(params["sampling_min"]))
    with np.errstate(invalid="ignore"):
        flag = igt(d1, d2, params["gamma1"], params["d2_scale_min"]) > params["th_act"]
    return pd.DatetimeIndex(times)[np.flatnonzero(rising(flag))]


def detect_grid(times, glucose, cfg):
    """Detection sample indices for every point of param_grid(cfg), in the same order.
    The derivatives are computed once; IGT once per gamma1."""
    ax = grid_axes(cfg)
    fx = fixed_params(cfg)
    d1, d2 = derivatives(glucose, int(fx["fit_points"]), float(fx["sampling_min"]))
    out = []
    for g1 in ax["gamma1"]:
        v = igt(d1, d2, g1, fx["d2_scale_min"])
        with np.errstate(invalid="ignore"):
            flags = rising(v[None, :] > ax["th_act"][:, None])
        out += [np.flatnonzero(f) for f in flags]
    return out
