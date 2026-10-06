"""Faccioli et al. 2022 super-twisting meal detector (STMD), as in the Hochsmann 2026 review
(Supplementary Methods "Algorithm by Faccioli et al.", Supplementary Table 1 Equation 7), with
the observer, Kalman filter and gain rule of Faccioli 2022. Details: methods/faccioli/docs/deviations.md.

Per participant-day, 5-min samples:
  1. causal 3-point median filter: cgm(k) = median(g(k-2), g(k-1), g(k))           (F3)
  2. observer bound L, k1 = 1.5 L^0.5, k2 = 1.1 L (Faccioli Eq. 3). ``[observer] gain_rule``:
     "grid" (main run, F5b, decided 2026-10-05 after the first run): L is a grid parameter
     ``l_bound`` tuned with the thresholds on Route B.
     "night" (first run, protocol_v1_nightgain, F5a): L = max of the disturbance estimate
     F_hat(k) over the day's night segment (00:00 to 07:00), F_hat(k) = k2 lambda(k-1) =
     g~(k-1) / h^2 (Faccioli Eq. 8 with h = tau = 5 min), computed with a non-saturating
     provisional gain; L >= L_floor.
  3. super-twisting observer, implicit discretisation (Faccioli Eqs. 4-7), on cgm(k):
       g(k)  = cgm_ST(k-1) + h u(k-1);  g~(k) = cgm(k) - g(k)
       |g~| <= h^2 k2:  cgm_ST(k) = cgm(k),  lambda = g~ / (h^2 k2)
       otherwise:       s = (h k1 / 2) (sqrt(1 + 4 (|g~| - h^2 k2) / (h k1)^2) - 1),
                        res = s^2 sign(g~), cgm_ST = cgm - res, lambda = sign(g~)
       u(k) = u(k-1) + h k2 lambda(k);  Res(k) = cgm(k) - cgm_ST(k)
  4. Kalman derivative (Faccioli Eqs. 9-12, common/evaluation/kalman.filter_faccioli) on cgm(k);
     dG(k) = rate (mg/dL per sample) / 5 -> mg/dL/min (F7).
  5. MDA(k) = 1 if Res(k) > Th_Res and dG(k) > Th_Der (Eq. 7). A detection is the first sample
     of each run of MDA = 1 (rising edge).
"""
import itertools

import numpy as np
import pandas as pd

from common.evaluation import kalman

PARAMS = ["th_res", "th_der", "l_bound"]       # tie-break order; l_bound only with gain_rule "grid"


def _axis(spec):
    if isinstance(spec, dict):                     # explicit values
        return np.round(np.asarray(spec["values"], float), 6)
    start, stop, step = spec
    return np.round(np.arange(start, stop + step / 2, step), 6)


def grid_axes(cfg):
    g = cfg["methods"]["faccioli"]["grid"]
    return {p: _axis(g[p]) for p in PARAMS if p in g}


def param_grid(cfg):
    ax = grid_axes(cfg)
    return [dict(zip(ax, map(float, v))) for v in itertools.product(*ax.values())]


def fixed_params(cfg):
    m = cfg["methods"]["faccioli"]
    k, o = m["kalman"], m["observer"]
    return {"sampling_min": m["sampling_min"], "median_points": m["median_points"],
            "gain_rule": o["gain_rule"],
            "night_end_h": o["night_end_h"], "l_floor": o["l_floor"], "l_provisional": o["l_provisional"],
            "kalman_sigma_w2": k["sigma_w2"], "kalman_sigma_v2": k["sigma_v2"],
            "kalman_p0_rate_sd": k["p0_rate_sd"], "kalman_p0_acc_sd": k["p0_acc_sd"],
            "kalman_warmup_samples": k["warmup_samples"]}


# ---------------------------------------------------------------- signals
def median3(g, points=3):
    """Causal running median of the last ``points`` samples; missing if any is missing."""
    g = np.asarray(g, float)
    out = np.full(len(g), np.nan)
    if len(g) >= points:
        out[points - 1:] = np.median(np.lib.stride_tricks.sliding_window_view(g, points), axis=1)
    return out


def observer(cgm, L, h):
    """Implicit super-twisting observer. Returns (res, lam, g_tilde) per sample.

    Restarts (cgm_ST = cgm, u = 0) at the first valid sample after a missing one; res is
    missing at missing samples and 0 at a restart."""
    k1, k2 = 1.5 * np.sqrt(L), 1.1 * L
    a, b = h * k1, h * h * k2
    n = len(cgm)
    res, lam, gt = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    st = u = None
    for k in range(n):
        y = cgm[k]
        if np.isnan(y):
            st = None
            continue
        if st is None:                               # (re)start
            st, u = y, 0.0
            res[k], lam[k], gt[k] = 0.0, 0.0, 0.0
            continue
        g = st + h * u
        e = y - g
        if abs(e) <= b:
            st, r, lm = y, 0.0, e / b
        else:
            s = 0.5 * a * (np.sqrt(1.0 + 4.0 * (abs(e) - b) / (a * a)) - 1.0)
            r = np.sign(e) * s * s
            st, lm = y - r, np.sign(e)
        u = u + h * k2 * lm
        res[k], lam[k], gt[k] = r, lm, e
    return res, lam, gt


def day_gain(cgm, minutes, fixed):
    """Observer bound L for the day: max F_hat over the night segment (F5)."""
    h = float(fixed["sampling_min"])
    Lp = float(fixed["l_provisional"])
    _, lam, _ = observer(cgm, Lp, h)
    f_hat = np.full(len(cgm), np.nan)
    f_hat[1:] = 1.1 * Lp * lam[:-1]                  # F_hat(k) = k2 lambda(k-1), h = tau
    night = minutes < 60 * fixed["night_end_h"]
    vals = f_hat[night & np.isfinite(f_hat)]
    L = float(vals.max()) if len(vals) else np.nan
    return max(L, float(fixed["l_floor"])) if np.isfinite(L) else np.nan


def residual(cgm, minutes, fixed, l_bound=None):
    """(Res, L): L from the night rule, or the given grid value."""
    h = float(fixed["sampling_min"])
    L = day_gain(cgm, minutes, fixed) if fixed["gain_rule"] == "night" else float(l_bound)
    if np.isfinite(L):
        return observer(cgm, L, h)[0], L
    return np.full(len(cgm), np.nan), L              # no valid night: no detection that day


def signals(times, glucose, fixed, l_bound=None):
    """cgm (median-filtered), Res, dG (mg/dL/min) and the day's L."""
    t = pd.DatetimeIndex(times)
    minutes = np.asarray((t - t[0].normalize()) / pd.Timedelta(minutes=1))
    cgm = median3(glucose, int(fixed["median_points"]))
    h = float(fixed["sampling_min"])
    res, L = residual(cgm, minutes, fixed, l_bound)
    _, rate, _ = kalman.filter_faccioli(cgm, fixed["kalman_sigma_w2"], fixed["kalman_sigma_v2"],
                                        fixed["kalman_p0_rate_sd"], fixed["kalman_p0_acc_sd"],
                                        fixed["kalman_warmup_samples"])
    return dict(cgm=cgm, res=res, dg=rate / h, L=L, minutes=minutes)


def rising(flag):
    prev = np.zeros(flag.shape, bool)
    prev[..., 1:] = flag[..., :-1]
    return flag & ~prev


def detect(times, glucose, params):
    sig = signals(times, glucose, params, params.get("l_bound"))
    with np.errstate(invalid="ignore"):
        flag = (sig["res"] > params["th_res"]) & (sig["dg"] > params["th_der"])
    return pd.DatetimeIndex(times)[np.flatnonzero(rising(flag))]


def detect_grid(times, glucose, cfg):
    """Detection sample indices for every point of param_grid(cfg), in the same order."""
    ax = grid_axes(cfg)
    fx = fixed_params(cfg)
    l_axis = ax["l_bound"] if "l_bound" in ax else [None]
    sig = signals(times, glucose, fx, l_axis[0])
    res = np.stack([sig["res"]] + [residual(sig["cgm"], sig["minutes"], fx, L)[0] for L in l_axis[1:]])
    with np.errstate(invalid="ignore"):
        r = res[None, :, :] > ax["th_res"][:, None, None]               # (R, L, T)
        d = sig["dg"][None, :] > ax["th_der"][:, None]                  # (D, T)
    flags = rising(r[:, None, :, :] & d[None, :, None, :]).reshape(-1, res.shape[-1])
    return [np.flatnonzero(f) for f in flags]
