"""Glucose Rate Increase Detector (GRID), Harvey et al. 2014, as implemented in the
Hochsmann 2026 review (Supplementary Methods "Algorithm by Harvey et al.", Supplementary
Table 1 Equation 8).

Per 5-min sample k (Harvey 2014 Eqs. 1-4):
  1. noise-spike filter: the step from the previous filtered value is clipped to +/- dG,
     dG = 3 mg/dL per minute of sampling period (15 mg/dL at 5 min);
  2. low-pass filter: GF(k) = dt/(tau_F+dt) * GF_NS(k) + (1 - dt/(tau_F+dt)) * GF(k-1);
  3. ROC G'F(k): derivative of the 3-point Lagrange polynomial through k-2, k-1, k,
     evaluated at t(k);
  4. GRID+(k) = GF(k) > G_min and (G'F(k-2:k) > G'_min,3 or G'F(k-1:k) > G'_min,2).
A detection is the first sample of each run of GRID+ = 1 (deviations.md D-H4). Filters
restart at the first reading after every missing stretch (D-H3).
"""
import itertools

import numpy as np
import pandas as pd

PARAMS = ["tau_F", "G_min", "Gp_min_3", "Gp_min_2"]


def _axis(spec):
    start, stop, step = spec
    return np.round(np.arange(start, stop + step / 2, step), 6)


def grid_axes(cfg):
    g = cfg["methods"]["harvey"]["grid"]
    return {p: _axis(g[p]) for p in PARAMS}


def param_grid(cfg):
    ax = grid_axes(cfg)
    return [dict(zip(PARAMS, map(float, v))) for v in itertools.product(*(ax[p] for p in PARAMS))]


def fixed_params(cfg):
    """Detector settings that are not tuned (passed to ``detect`` with every grid point)."""
    return {"spike_max_roc_mg_dl_per_min": cfg["methods"]["harvey"]["spike_max_roc_mg_dl_per_min"]}


def filter_and_roc(times, glucose, tau_F, spike_per_min=3.0):
    """Return (GF, ROC) arrays; NaN where not defined."""
    t = (pd.DatetimeIndex(times).asi8 // 60_000_000_000).astype(float)   # minutes
    g = np.asarray(glucose, float)
    n = len(g)
    gf = np.full(n, np.nan)
    roc = np.full(n, np.nan)
    ns_prev = f_prev = np.nan
    run = 0                                     # length of the current finite run
    for k in range(n):
        if np.isnan(g[k]):
            run = 0
            continue
        if run == 0:
            ns = f = g[k]
        else:
            dt = t[k] - t[k - 1]
            dg = spike_per_min * dt
            ns = min(max(g[k], ns_prev - dg), ns_prev + dg)
            a = dt / (tau_F + dt)
            f = a * ns + (1 - a) * f_prev
        gf[k] = f
        run += 1
        if run >= 3:
            t0, t1, t2 = t[k - 2], t[k - 1], t[k]
            roc[k] = ((t2 - t1) / ((t0 - t1) * (t0 - t2)) * gf[k - 2]
                      + (t2 - t0) / ((t1 - t0) * (t1 - t2)) * gf[k - 1]
                      + (2 * t2 - t0 - t1) / ((t2 - t1) * (t2 - t0)) * gf[k])
        ns_prev, f_prev = ns, f
    return gf, roc


def _last_min(roc, m):
    """min(roc[k-m+1..k]); NaN if any is NaN or k < m-1."""
    out = np.full(len(roc), np.nan)
    if len(roc) >= m:
        w = np.lib.stride_tricks.sliding_window_view(roc, m)
        out[m - 1:] = w.min(axis=1)         # NaN propagates
    return out


def _rising(flag):
    prev = np.concatenate([[False], flag[..., :-1]], axis=-1) if flag.ndim == 1 else \
        np.concatenate([np.zeros(flag.shape[:-1] + (1,), bool), flag[..., :-1]], axis=-1)
    return flag & ~prev


def detect(times, glucose, params):
    gf, roc = filter_and_roc(times, glucose, params["tau_F"],
                             params.get("spike_max_roc_mg_dl_per_min", 3.0))
    with np.errstate(invalid="ignore"):
        flag = (gf > params["G_min"]) & ((_last_min(roc, 3) > params["Gp_min_3"]) |
                                         (_last_min(roc, 2) > params["Gp_min_2"]))
    return pd.DatetimeIndex(times)[np.flatnonzero(_rising(flag))]


def detect_grid(times, glucose, cfg):
    """Detection sample indices for every point of param_grid(cfg), in the same order."""
    ax = grid_axes(cfg)
    spike = cfg["methods"]["harvey"]["spike_max_roc_mg_dl_per_min"]
    nG, n3, n2 = len(ax["G_min"]), len(ax["Gp_min_3"]), len(ax["Gp_min_2"])
    per_tau = nG * n3 * n2
    out = [np.empty(0, int)] * (len(ax["tau_F"]) * per_tau)
    for ti, tau in enumerate(ax["tau_F"]):
        gf, roc = filter_and_roc(times, glucose, tau, spike)
        with np.errstate(invalid="ignore"):
            A = gf[None, :] > ax["G_min"][:, None]
            B3 = _last_min(roc, 3)[None, :] > ax["Gp_min_3"][:, None]
            B2 = _last_min(roc, 2)[None, :] > ax["Gp_min_2"][:, None]
        flag = A[:, None, None, :] & (B3[None, :, None, :] | B2[None, None, :, :])
        a, b, c, k = np.nonzero(_rising(flag))
        combo = ti * per_tau + (a * n3 + b) * n2 + c
        order = np.argsort(combo, kind="stable")
        combo, k = combo[order], k[order]
        cuts = np.flatnonzero(np.diff(combo)) + 1
        for cid, ks in zip(combo[np.r_[0, cuts]] if len(combo) else [], np.split(k, cuts)):
            out[cid] = ks
    return out
