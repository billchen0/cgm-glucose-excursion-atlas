"""Popp et al. 2024 simulation-based meal detection (SBE, after Zheng 2019), as in the Hochsmann
2026 review (Supplementary Methods "Algorithm by Popp et al.", Supplementary Table 1 Eqs. 11-13).
Details: methods/popp/docs/deviations.md.

Model: Dalla Man 2007 meal model of the glucose-insulin system (the "GIM" of Popp and Zheng), normal
subject, equations and population parameters as in the curated BioModels SBML BIOMD0000000379.
Insulin is endogenous (beta-cell secretion model); there is no insulin input. Meals are ingested at
a constant rate over the meal duration (Zheng 2019 Eq. 8).

Per 1-min sample i (P3-P6):
  anchor a = i - max(zeta, tau); the model starts at its basal steady state at a, so the no-meal
  prediction is G'(k) = G(a) for k > a.
  Div(i) = (1/zeta) sum_{j=0}^{zeta-1} |G(i-j) - G'(i-j)| / G'(i-j)                       (Eq. 11)
  m_st = earliest k in [i - tau, i] with G(j) > G'(j) for all j in [k, i] (back-search)
  G'_m(k) = G(a) + dG_m(k - m_st), dG_m = model response to load m from basal, m in {25, 50, 75, 100} g
  D(m) = sqrt( (1/n) sum_{k=m_st}^{i} (G'_m(k) - G(k))^2 ), n = i - m_st + 1                (Eq. 12)
  MDA(i) = 1 if Div(i) > phi and min_m D(m) < epsilon                                       (Eq. 13)
A detection is the first sample of each run of MDA = 1 (rising edge), at time i; m_st is kept.
"""
import itertools
from functools import lru_cache

import numpy as np
import pandas as pd

PARAMS = ["phi_pct", "tau_min", "eps"]


# ---------------------------------------------------------------- config
def _axis(spec):
    if isinstance(spec, dict):
        return np.round(np.asarray(spec["values"], float), 6)
    start, stop, step = spec
    return np.round(np.arange(start, stop + step / 2, step), 6)


def grid_axes(cfg):
    g = cfg["methods"]["popp"]["grid"]
    return {p: _axis(g[p]) for p in PARAMS}


def param_grid(cfg):
    ax = grid_axes(cfg)
    return [dict(zip(PARAMS, map(float, v))) for v in itertools.product(*(ax[p] for p in PARAMS))]


def fixed_params(cfg):
    m = cfg["methods"]["popp"]
    return {"sampling_min": m["sampling_min"], "zeta_min": m["zeta_min"],
            "loads_g": tuple(m["loads_g"]), "meal_duration_min": m["meal_duration_min"]}


# ---------------------------------------------------------------- Dalla Man 2007 model
# BioModels BIOMD0000000379 (Dalla Man, Rizza, Cobelli 2007), normal subject
DM = dict(V_G=1.88, k_1=0.065, k_2=0.079, G_b=95.0, V_I=0.05, m_1=0.19, m_2=0.484, m_4=0.194,
          m_5=0.0304, m_6=0.6471, I_b=25.0, S_b=1.8, k_max=0.0558, k_min=0.008, k_abs=0.057,
          k_gri=0.0558, f=0.9, b=0.82, d=0.01, BW=78.0, k_p1=2.7, k_p2=0.0021, k_p3=0.009,
          k_p4=0.0618, k_i=0.0079, U_ii=1.0, V_m0=2.5, V_mX=0.047, K_m0=225.59, p_2U=0.0331,
          part=0.2, K=2.3, alpha=0.05, beta=0.11, gamma=0.5)
# state: G_p, G_t, I_l, I_p, Q_sto1, Q_sto2, Q_gut, I_1, I_d, X, I_po, Y (SBML initial values)
X0 = np.array([178.0, 135.0, 4.5, 1.25, 0.0, 0.0, 0.0, 25.0, 25.0, 0.0, 3.6, 0.0])


def rhs(x, ingest, dose):
    """Dalla Man 2007 right-hand side (SBML form). ingest: mg/min into Q_sto1; dose: total meal (mg)."""
    p = DM
    Gp, Gt, Il, Ip, Qs1, Qs2, Qg, I1, Id, X, Ipo, Y = x
    G, I = Gp / p["V_G"], Ip / p["V_I"]
    EGP = p["k_p1"] - p["k_p2"] * Gp - p["k_p3"] * Id - p["k_p4"] * Ipo
    Uid = (1 - p["part"]) * (p["V_m0"] + p["V_mX"] * X) * Gt / (p["K_m0"] + Gt)
    S = p["gamma"] * Ipo
    HE = -p["m_5"] * S + p["m_6"]
    m3 = HE * p["m_1"] / (1 - HE)
    Qsto = Qs1 + Qs2
    if dose > 0:
        aa = 2.5 / (1 - p["b"]) / dose
        cc = 2.5 / p["d"] / dose
        kempt = p["k_min"] + (p["k_max"] - p["k_min"]) / 2 * (
            np.tanh(aa * (Qsto - p["b"] * dose)) - np.tanh(cc * (Qsto - p["d"] * dose)) + 2)
    else:
        kempt = p["k_max"]
    Ra = p["f"] * p["k_abs"] * Qg / p["BW"]
    dGp = EGP + Ra - p["U_ii"] - p["k_1"] * Gp + p["k_2"] * Gt          # E = 0 (SBML)
    Spo = Y + p["K"] * dGp / p["V_G"] + p["S_b"]
    return np.array([
        dGp,
        -Uid + p["k_1"] * Gp - p["k_2"] * Gt,
        -(p["m_1"] + m3) * Il + p["m_2"] * Ip + S,
        -(p["m_2"] + p["m_4"]) * Ip + p["m_1"] * Il,
        -p["k_gri"] * Qs1 + ingest,
        -kempt * Qs2 + p["k_gri"] * Qs1,
        -p["k_abs"] * Qg + kempt * Qs2,
        -p["k_i"] * (I1 - I),
        -p["k_i"] * (Id - I1),
        -p["p_2U"] * X + p["p_2U"] * (I - p["I_b"]),
        -p["gamma"] * Ipo + Spo,
        -p["alpha"] * (Y - p["beta"] * (G - p["G_b"])),
    ])


def simulate(x0, minutes, load_g=0.0, duration_min=90.0, dt=0.25):
    """RK4 integration; returns plasma glucose G (mg/dL) at t = 0, 1, ..., minutes."""
    dose = load_g * 1000.0
    rate = dose / duration_min if dose > 0 else 0.0
    x = np.array(x0, float)
    out = [x[0] / DM["V_G"]]
    steps = int(round(1 / dt))
    t = 0.0
    for _ in range(minutes):
        for _ in range(steps):
            u = rate if t < duration_min else 0.0
            u2 = rate if t + dt / 2 < duration_min else 0.0
            k1 = rhs(x, u, dose)
            k2 = rhs(x + dt / 2 * k1, u2, dose)
            k3 = rhs(x + dt / 2 * k2, u2, dose)
            u4 = rate if t + dt < duration_min else 0.0
            k4 = rhs(x + dt * k3, u4, dose)
            x = x + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            t += dt
        out.append(x[0] / DM["V_G"])
    return np.array(out)


@lru_cache(maxsize=None)
def basal_state():
    """Basal steady state: the SBML initial state run without a meal for 3000 min."""
    x = np.array(X0, float)
    dt = 0.25
    for _ in range(int(3000 / dt)):
        k1 = rhs(x, 0, 0)
        k2 = rhs(x + dt / 2 * k1, 0, 0)
        k3 = rhs(x + dt / 2 * k2, 0, 0)
        k4 = rhs(x + dt * k3, 0, 0)
        x = x + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    return tuple(x)


@lru_cache(maxsize=None)
def meal_response(load_g, duration_min, minutes=120):
    """dG_m(t): model glucose minus basal glucose after a meal starting at t = 0 from basal."""
    x0 = np.array(basal_state())
    g = simulate(x0, minutes, load_g, duration_min)
    return g - x0[0] / DM["V_G"]


# ---------------------------------------------------------------- detector
def _responses(fx, n):
    return np.stack([meal_response(float(m), float(fx["meal_duration_min"]))[:n] for m in fx["loads_g"]])


def candidate_signals(glucose, fx, tau):
    """Per sample i for one tau: Div(i), min_m D(m), m_st index (NaN / -1 where undefined)."""
    y = np.asarray(glucose, float)
    n = len(y)
    zeta = int(fx["zeta_min"])
    tau = int(tau)
    back = max(zeta, tau)
    R = _responses(fx, tau + 1)                              # (loads, tau + 1)
    div = np.full(n, np.nan)
    dmin = np.full(n, np.nan)
    mst = np.full(n, -1)
    for i in range(back, n):
        a = i - back
        seg = y[a:i + 1]
        if np.isnan(seg).any():
            continue
        g0 = y[a]
        div[i] = np.mean(np.abs(y[i - zeta + 1:i + 1] - g0)) / g0          # Eq. 11, G' = G(a)
        above = y[i - tau:i + 1] > g0
        if not above[-1]:
            continue                                         # glucose not above G': no meal start
        k = tau
        while k > 0 and above[k - 1]:
            k -= 1
        m = i - tau + k                                      # earliest k with G > G' through i
        obs = y[m:i + 1]
        pred = g0 + R[:, :i - m + 1]
        dmin[i] = np.sqrt(np.mean((pred - obs) ** 2, axis=1)).min()       # Eq. 12, best load
        mst[i] = m
    return div, dmin, mst


def rising(flag):
    prev = np.zeros(flag.shape, bool)
    prev[..., 1:] = flag[..., :-1]
    return flag & ~prev


def flags(div, dmin, phi_pct, eps):
    with np.errstate(invalid="ignore"):
        return (div > phi_pct / 100.0) & (dmin < eps)                       # Eq. 13


def detect_details(times, glucose, params):
    """(detection indices, m_st indices) for one parameter set (plain path, one tau)."""
    div, dmin, mst = candidate_signals(glucose, params, params["tau_min"])
    idx = np.flatnonzero(rising(flags(div, dmin, params["phi_pct"], params["eps"])))
    return idx, mst[idx]


def detect(times, glucose, params):
    idx, _ = detect_details(times, glucose, params)
    return pd.DatetimeIndex(times)[idx]


def detection_extras(times, glucose, params):
    """Extra per-detection columns for the export: excursion_start = m_st."""
    t = pd.DatetimeIndex(times)
    idx, mst = detect_details(times, glucose, params)
    return pd.DataFrame({"detection_time": t[idx], "excursion_start": t[mst]})


def detect_grid(times, glucose, cfg):
    """Detection sample indices for every point of param_grid(cfg): signals once per tau."""
    ax = grid_axes(cfg)
    fx = fixed_params(cfg)
    sig = {tau: candidate_signals(glucose, fx, tau) for tau in ax["tau_min"]}
    out = []
    for phi, tau, eps in itertools.product(ax["phi_pct"], ax["tau_min"], ax["eps"]):
        div, dmin, _ = sig[tau]
        out.append(np.flatnonzero(rising(flags(div, dmin, phi, eps))))
    return out
