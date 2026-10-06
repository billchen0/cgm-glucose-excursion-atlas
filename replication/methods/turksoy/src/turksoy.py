"""Turksoy et al. 2016 meal detector: unscented Kalman filter (UKF) on a modified Bergman minimal
model, meal when the estimated rate of glucose appearance R_a exceeds a threshold
(Hochsmann 2026 Supplementary Methods "Algorithm by Turksoy et al.", Supplementary Table 1 Eq. 16;
model and UKF from Turksoy 2016, IEEE JBHI 20(1):47-54). Details: methods/turksoy/docs/deviations.md.

State x = [I_eff, G_s, R_a(k), R_a(k-1), p1, p2, p4, tau] (Turksoy Eqs. 4-8, 22), h = 1 min:
  G_s(k+1)   = G_s + h (-p1 G_s - p2 I_eff G_s + p1 G_b(k) + R_a)            (Eq. 4)
  I_eff(k+1) = I_eff - h p2 I_eff  (+ h p3 I_p, with I_p = p3 = 0 by Eq. 7)  (Eq. 5)
  R_a(k+1)   = 2 R_a / a - R_a(k-1) / a^2  (+ h C / (V a tau^2), C = V = 0)  (Eq. 6)
  p1, p2, p4, tau: random walks (Eq. 7); a = exp(h / tau)
  G_b(k) = 100 for the first 2l/h samples, then the mean of the measured CGM over samples
           k - 2l/h + 1 ... k - l/h (l = 30 min)                             (Eq. 8)
  y(k) = G_s(k) + v(k)
UKF (Eqs. 10-21): alpha = 1, beta = 2, kappa = 0; prior sigma points trimmed to bounds (Eq. 12);
the generated sigma points are also clipped before propagation (T7b).
Meal flag: R_a_hat(i) > Threshold_Ra and CGM(i) > 100 mg/dL (Eq. 16); detection = rising edge.
"""
import itertools

import numpy as np
import pandas as pd

PARAMS = ["th_ra"]
STATES = ["I_eff", "G_s", "R_a", "R_a_prev", "p1", "p2", "p4", "tau"]
_CACHE = {}


def _axis(spec):
    start, stop, step = spec
    return np.round(np.arange(start, stop + step / 2, step), 6)


def grid_axes(cfg):
    g = cfg["methods"]["turksoy"]["grid"]
    return {p: _axis(g[p]) for p in PARAMS}


def param_grid(cfg):
    ax = grid_axes(cfg)
    return [dict(zip(PARAMS, map(float, v))) for v in itertools.product(*(ax[p] for p in PARAMS))]


def fixed_params(cfg):
    m = cfg["methods"]["turksoy"]
    u = m["ukf"]
    return {"sampling_min": m["sampling_min"], "glucose_min": m["glucose_min"],
            "gb_window_min": m["gb_window_min"], "gb_default": m["gb_default"],
            "ukf_alpha": u["alpha"], "ukf_beta": u["beta"], "ukf_kappa": u["kappa"],
            "ukf_x0": tuple(u["x0"]), "ukf_qp": tuple(u["qp"]), "ukf_p0": u["p0"], "ukf_qm": u["qm"],
            "ukf_lo": tuple(u["lower"]), "ukf_hi": tuple(u["upper"]),
            "ukf_eig_floor": u["eig_floor"], "ukf_warmup_min": u["warmup_min"]}


def _key(glucose, fx):
    return (np.asarray(glucose, float).tobytes(),
            tuple(sorted((k, v) for k, v in fx.items() if k.startswith(("ukf", "gb", "sampling")))))


# ---------------------------------------------------------------- model
def f(X, gb, h):
    """Propagate sigma points X (n x 8) one step (Turksoy Eqs. 4-7, inputs I_p = C = 0)."""
    ieff, gs, ra, ra1, p1, p2, p4, tau = X.T
    a = np.exp(h / tau)
    out = np.empty_like(X)
    out[:, 0] = ieff - h * p2 * ieff
    out[:, 1] = gs + h * (-p1 * gs - p2 * ieff * gs + p1 * gb + ra)
    out[:, 2] = 2 * ra / a - ra1 / a ** 2
    out[:, 3] = ra
    out[:, 4:] = X[:, 4:]
    return out


def _sqrt_psd(P, floor):
    """Symmetrise P and return (P, lower Cholesky factor), flooring eigenvalues if needed."""
    P = 0.5 * (P + P.T)
    try:
        return P, np.linalg.cholesky(P)
    except np.linalg.LinAlgError:
        w, V = np.linalg.eigh(P)
        P = (V * np.maximum(w, floor)) @ V.T
        P = 0.5 * (P + P.T)
        return P, np.linalg.cholesky(P)


def ukf(glucose, fx):
    """Run the UKF over one participant-day. Returns a dict of per-sample arrays:
    the eight states, their variances, ``n_floor`` (eigenvalue floors applied) and ``valid``.
    Restarts at the first valid sample after a missing one; outputs are NaN at missing samples
    and for the first ``ukf_warmup_min`` minutes of each run. Results are cached per input."""
    key = _key(glucose, fx)
    if key in _CACHE:
        return _CACHE[key]
    y = np.asarray(glucose, float)
    n, L = len(y), 8
    h = float(fx["sampling_min"])
    alpha, beta, kappa = fx["ukf_alpha"], fx["ukf_beta"], fx["ukf_kappa"]
    mu = alpha ** 2 * (L + kappa)                          # Eq. 10 notation
    gamma = np.sqrt(L + mu)
    wx = np.full(2 * L + 1, 1 / (2 * (L + mu)))
    wy = wx.copy()
    wx[0] = mu / (L + mu)
    wy[0] = mu / (L + mu) + (1 - alpha ** 2 + beta)
    Qp = np.diag(fx["ukf_qp"])
    Qm = float(fx["ukf_qm"])
    lo, hi = np.array(fx["ukf_lo"]), np.array(fx["ukf_hi"])
    floor = float(fx["ukf_eig_floor"])
    lag2, lag1 = int(2 * fx["gb_window_min"] / h), int(fx["gb_window_min"] / h)
    warm = int(np.ceil(fx["ukf_warmup_min"] / h))

    est, var = np.full((n, L), np.nan), np.full((n, L), np.nan)
    n_floor = 0
    x = P = None
    start = 0
    for k in range(n):
        if np.isnan(y[k]):
            x = None
            continue
        if x is None:                                      # (re)start, Turksoy Eq. 22
            x = np.array(fx["ukf_x0"], float)
            x[1] = y[k]
            P = np.eye(L) * fx["ukf_p0"]
            start = k
        else:
            j = k - 1 - start                              # G_b at the previous sample (Eq. 8)
            gb = (fx["gb_default"] if j < lag2
                  else float(np.mean(y[k - 1 - lag2 + 1:k - 1 - lag1 + 1])))
            P, S = _sqrt_psd(P, floor)
            X = np.vstack([x, x + gamma * S.T, x - gamma * S.T])      # Eq. 11 (columns of S)
            X = np.clip(X, lo, hi)              # also before f: keeps tau > 0 (T7b, stability)
            Xp = np.clip(f(X, gb, h), lo, hi)                          # Eq. 12 (box trimming)
            xm = wx @ Xp                                               # Eq. 13
            D = Xp - xm
            Pm = (D.T * wy) @ D + Qp                                   # Eq. 14
            Yp = Xp[:, 1]                                              # Eq. 15, g = G_s
            ym = wx @ Yp                                               # Eq. 16
            dy = Yp - ym
            Pyy = wy @ (dy * dy) + Qm                                  # Eq. 17
            Pxy = (D.T * wy) @ dy                                      # Eq. 18
            K = Pxy / Pyy                                              # Eq. 19
            x = np.clip(xm + K * (y[k] - ym), lo, hi)                  # Eq. 20, then bounds
            P = Pm - np.outer(K, K) * Pyy                              # Eq. 21
            P = 0.5 * (P + P.T)
            w, V = np.linalg.eigh(P)
            if w.min() < floor:                                        # keep P positive definite
                n_floor += 1
                P = (V * np.maximum(w, floor)) @ V.T
                P = 0.5 * (P + P.T)
        if k - start >= warm:
            est[k], var[k] = x, np.diag(P)
    out = {s: est[:, i] for i, s in enumerate(STATES)}
    out.update({f"var_{s}": var[:, i] for i, s in enumerate(STATES)})
    out["n_floor"] = n_floor
    _CACHE[key] = out
    return out


# ---------------------------------------------------------------- detector
def rising(flag):
    prev = np.zeros(flag.shape, bool)
    prev[..., 1:] = flag[..., :-1]
    return flag & ~prev


def detect(times, glucose, params):
    s = ukf(glucose, params)
    g = np.asarray(glucose, float)
    with np.errstate(invalid="ignore"):
        flag = (s["R_a"] > params["th_ra"]) & (g > params["glucose_min"])
    return pd.DatetimeIndex(times)[np.flatnonzero(rising(flag))]


def detect_grid(times, glucose, cfg):
    """Detection sample indices for every point of param_grid(cfg): one UKF pass per day."""
    fx = fixed_params(cfg)
    s = ukf(glucose, fx)
    g = np.asarray(glucose, float)
    th = grid_axes(cfg)["th_ra"]
    with np.errstate(invalid="ignore"):
        flags = rising((s["R_a"][None, :] > th[:, None]) & (g > fx["glucose_min"])[None, :])
    return [np.flatnonzero(fl) for fl in flags]
