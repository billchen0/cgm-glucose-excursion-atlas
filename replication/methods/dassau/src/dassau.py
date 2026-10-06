"""Dassau et al. 2008 meal detection, as specified in the Hochsmann 2026 review
(Supplementary Methods "Algorithms by Dassau et al.", Supplementary Table 1 Equations 1-6).
Shared indicator code for the two registered detectors dassau_2of3 and dassau_3of4.

At each 1-min sample i (methods/dassau/docs/deviations.md):
  BD(i)  = 1 if BD_raw(i) > Threshold_ROC                            (Eq. 1)
  BDK(i) = 1 if BD_Kalman(i) > Threshold_ROC                         (Eq. 2)
  KF(i)  = 1 if Threshold_ROC < G'_K(i) < Threshold_maxROC
               and G_K(i) > Threshold_Glucose                        (Eq. 3)
  ACC(i) = 1 if G''_K(i) > Threshold_Acceleration                    (Eq. 4)
BD_raw, BD_Kalman: 3-point backward difference (3 g(i) - 4 g(i-1) + g(i-2)) / (2 dt) on the
QC'd 1-min glucose and on the Kalman glucose; G_K, G'_K, G''_K from common/evaluation/kalman.py.
  2of3: MDA(i) = 1 if BD + BDK + ACC >= 2 at every sample i, ..., i+4   (Eq. 5)
  3of4: MDA(i) = 1 if BD + BDK + KF + ACC >= 3 at every sample i, ..., i+4   (Eq. 6)
A detection is the first sample i of each run of MDA = 1 (rising edge), at time t(i) as the
equations index it (D4). Missing samples make every indicator false.
"""
import itertools

import numpy as np
import pandas as pd

from common.evaluation import kalman

PARAMS = {"2of3": ["th_roc", "th_acc"],
          "3of4": ["th_glucose", "th_max_roc", "th_roc", "th_acc"]}
VOTES = {"2of3": 2, "3of4": 3}


# ---------------------------------------------------------------- config
def _axis(spec):
    start, stop, step = spec
    return np.round(np.arange(start, stop + step / 2, step), 6)


def grid_axes(cfg, name, variant):
    g = cfg["methods"][name]["grid"]
    return {p: _axis(g[p]) for p in PARAMS[variant]}


def param_grid(cfg, name, variant):
    ax = grid_axes(cfg, name, variant)
    ps = PARAMS[variant]
    return [dict(zip(ps, map(float, v))) for v in itertools.product(*(ax[p] for p in ps))]


def fixed_params(cfg, name):
    """Settings passed to detect but not tuned: Kalman defaults, window, sampling."""
    k = cfg["kalman"]["dassau"]
    return {"kalman_meas_sd_mg_dl": k["meas_sd_mg_dl"], "kalman_jerk_psd": k["jerk_psd"],
            "kalman_p0_rate_sd": k["p0_rate_sd"], "kalman_p0_acc_sd": k["p0_acc_sd"],
            "kalman_warmup_min": k["warmup_min"],
            "window_samples": cfg["methods"][name]["window_samples"],
            "sampling_min": cfg["methods"][name]["sampling_min"]}


# ---------------------------------------------------------------- signals
def backward_diff3(v, dt):
    """(3 v[i] - 4 v[i-1] + v[i-2]) / (2 dt); NaN for i < 2 or if any input is NaN."""
    out = np.full(len(v), np.nan)
    out[2:] = (3 * v[2:] - 4 * v[1:-1] + v[:-2]) / (2 * dt)
    return out


def signals(glucose, fixed):
    """Threshold-free signals of one participant-day: bd, bdk, gk, dgk, ddgk."""
    g = np.asarray(glucose, float)
    dt = float(fixed["sampling_min"])
    gk, dgk, ddgk = kalman.filter_ca(g, dt, fixed["kalman_meas_sd_mg_dl"], fixed["kalman_jerk_psd"],
                                     fixed["kalman_p0_rate_sd"], fixed["kalman_p0_acc_sd"],
                                     fixed["kalman_warmup_min"])
    return dict(bd=backward_diff3(g, dt), bdk=backward_diff3(gk, dt), gk=gk, dgk=dgk, ddgk=ddgk)


def indicators(sig, p):
    """Boolean BD, BDK, KF, ACC arrays (comparisons with NaN are False)."""
    with np.errstate(invalid="ignore"):
        bd = sig["bd"] > p["th_roc"]
        bdk = sig["bdk"] > p["th_roc"]
        acc = sig["ddgk"] > p["th_acc"]
        kf = ((sig["dgk"] > p["th_roc"]) & (sig["dgk"] < p.get("th_max_roc", np.inf))
              & (sig["gk"] > p.get("th_glucose", -np.inf)))
    return dict(BD=bd, BDK=bdk, KF=kf, ACC=acc)


def window_all(ok, w):
    """out[..., i] = all(ok[..., i:i+w]); False where the window runs past the end."""
    n = ok.shape[-1]
    out = np.zeros(ok.shape, bool)
    if n >= w:
        acc = ok[..., :n - w + 1].copy()
        for j in range(1, w):
            acc &= ok[..., j:n - w + 1 + j]
        out[..., :n - w + 1] = acc
    return out


def rising(flag):
    prev = np.zeros(flag.shape, bool)
    prev[..., 1:] = flag[..., :-1]
    return flag & ~prev


def mda(ind, variant, w):
    """Eq. 5 / Eq. 6 flag per sample."""
    if variant == "2of3":
        votes = ind["BD"].astype(int) + ind["BDK"] + ind["ACC"]
    else:
        votes = ind["BD"].astype(int) + ind["BDK"] + ind["KF"] + ind["ACC"]
    return window_all(votes >= VOTES[variant], w)


def detect(times, glucose, params, variant):
    sig = signals(glucose, params)
    flag = mda(indicators(sig, params), variant, int(params["window_samples"]))
    return pd.DatetimeIndex(times)[np.flatnonzero(rising(flag))]


def detect_grid(times, glucose, cfg, name, variant):
    """Detection sample indices for every point of param_grid, in the same order.

    Signals are computed once per day; thresholds are broadcast over the grid axes
    (shape: one axis per parameter, then time). Must equal ``detect`` (tests/test_dassau.py).
    """
    ax = grid_axes(cfg, name, variant)
    fixed = fixed_params(cfg, name)
    sig = signals(glucose, fixed)
    w = int(fixed["window_samples"])
    with np.errstate(invalid="ignore"):
        r = ax["th_roc"][:, None]
        bd, bdk = sig["bd"][None] > r, sig["bdk"][None] > r            # (R, T)
        acc = sig["ddgk"][None] > ax["th_acc"][:, None]                  # (A, T)
        if variant == "2of3":
            votes = bd[:, None].astype(np.int8) + bdk[:, None] + acc[None]            # (R, A, T)
        else:
            kf_r = sig["dgk"][None] > r                                                # (R, T)
            kf_m = sig["dgk"][None] < ax["th_max_roc"][:, None]                       # (M, T)
            kf_g = sig["gk"][None] > ax["th_glucose"][:, None]                        # (G, T)
            kf = kf_g[:, None, None] & kf_m[None, :, None] & kf_r[None, None]         # (G, M, R, T)
            base = (bd.astype(np.int8) + bdk)[None, None]                             # (1, 1, R, T)
            votes = (base + kf)[..., None, :] + acc[None, None, None]                # (G, M, R, A, T)
    flag = rising(window_all(votes >= VOTES[variant], w))
    shape = flag.shape[:-1]
    *grid_idx, k = np.nonzero(flag)
    combo = np.ravel_multi_index(grid_idx, shape) if len(k) else np.empty(0, int)
    out = [np.empty(0, int)] * int(np.prod(shape))
    order = np.argsort(combo, kind="stable")
    combo, k = combo[order], k[order]
    cuts = np.flatnonzero(np.diff(combo)) + 1
    for cid, ks in zip(combo[np.r_[0, cuts]] if len(combo) else [], np.split(k, cuts)):
        out[cid] = ks
    return out
