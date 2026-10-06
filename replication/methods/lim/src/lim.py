"""Lim et al. 2026 wavelet PPGR identification (J Diabetes Sci Technol 20(3):664-672), breakfast and
lunch windows. One PPGR per clock meal window. Details: methods/lim/docs/deviations.md.

Per participant-day, 5-min samples (L1-L9):
  1. Gaussian smoothing of the 24-h profile (scipy.ndimage.gaussian_filter1d, sigma in samples).
  2. Gaussian wavelet transform (PyWavelets cwt, 'gaus1', one scale), on the mean-removed profile
     with reflect padding; sign oriented so a rise gives positive coefficients.
  3. Candidate segment: each local maximum of the coefficient inside a meal window and the next
     local minimum. Peak = highest glucose in the segment; PPGR start = lowest glucose before the
     peak within the segment (QC'd glucose, not smoothed).
  4. Keep segments with height = peak - start >= min_height and a start inside the window; choose
     the highest (ties: earlier start). One PPGR per window.
Detection time = PPGR start. Extra columns: excursion_start (start), peak_time, excursion_end
(segment end, the next wavelet minimum).
"""
import itertools

import numpy as np
import pandas as pd
import pywt
from scipy import ndimage

PARAMS = ["min_height"]


def _axis(spec):
    if isinstance(spec, dict):
        return np.round(np.asarray(spec["values"], float), 6)
    start, stop, step = spec
    return np.round(np.arange(start, stop + step / 2, step), 6)


def grid_axes(cfg):
    g = cfg["methods"]["lim"]["grid"]
    return {p: _axis(g[p]) for p in PARAMS}


def param_grid(cfg):
    ax = grid_axes(cfg)
    return [dict(zip(PARAMS, map(float, v))) for v in itertools.product(*(ax[p] for p in PARAMS))]


def fixed_params(cfg):
    m = cfg["methods"]["lim"]
    return {"sampling_min": m["sampling_min"], "gauss_sigma_samples": m["gauss_sigma_samples"],
            "wavelet": m["wavelet"], "wavelet_scale": m["wavelet_scale"],
            "windows": tuple((k, v[0], v[1]) for k, v in m["windows"].items())}


def _hhmm(s):
    h, m = map(int, s.split(":"))
    return 60 * h + m


# ---------------------------------------------------------------- signals
def coefficients(glucose, fx):
    """(smoothed glucose, oriented wavelet coefficient) for one day."""
    g = np.asarray(glucose, float)
    x = np.arange(len(g))
    ok = np.isfinite(g)
    if ok.sum() < 2:
        return np.full(len(g), np.nan), np.full(len(g), np.nan)
    gi = np.interp(x, x[ok], g[ok])                    # bridge remaining gaps for the transform only
    gs = ndimage.gaussian_filter1d(gi, float(fx["gauss_sigma_samples"]))
    pad = len(gs)
    z = np.pad(gs - gs.mean(), pad, mode="reflect")
    c, _ = pywt.cwt(z, [float(fx["wavelet_scale"])], fx["wavelet"])
    c = -c[0][pad:pad + len(gs)]                       # pywt 'gaus1' is negative on a rise
    return gs, c


def _local_max(c):
    k = np.arange(1, len(c) - 1)
    return k[(c[k] > c[k - 1]) & (c[k] >= c[k + 1])]


def _local_min(c):
    k = np.arange(1, len(c) - 1)
    return k[(c[k] < c[k - 1]) & (c[k] <= c[k + 1])]


def candidates(times, glucose, fx):
    """All candidate segments per window: list of dicts (window, max, end, start, peak, height)."""
    g = np.asarray(glucose, float)
    t = pd.DatetimeIndex(times)
    minutes = np.asarray((t - t[0].normalize()) / pd.Timedelta(minutes=1))
    _, c = coefficients(g, fx)
    maxima, minima = _local_max(c), _local_min(c)
    out = []
    for name, w0, w1 in fx["windows"]:
        lo, hi = _hhmm(w0), _hhmm(w1)
        win = (minutes >= lo) & (minutes <= hi)
        if not win.any() or np.isnan(g[win]).any():
            continue                                   # window with missing data: no PPGR (L7)
        for k in maxima[win[maxima]]:
            nxt = minima[minima > k]
            j = int(nxt[0]) if len(nxt) else len(g) - 1
            seg = g[k:j + 1]
            if np.isnan(seg).any():
                continue
            p = k + int(np.argmax(seg))
            s = k + int(np.argmin(g[k:p + 1]))
            out.append(dict(window=name, max=int(k), end=j, start=s, peak=p,
                            height=float(g[p] - g[s]), start_in_window=bool(lo <= minutes[s] <= hi)))
    return out


def choose(cands, min_height):
    """One PPGR per window: highest height >= min_height with the start in the window; ties -> earlier start."""
    best = {}
    for cd in cands:
        if cd["height"] < min_height or not cd["start_in_window"]:
            continue
        b = best.get(cd["window"])
        if b is None or cd["height"] > b["height"] or (cd["height"] == b["height"] and cd["start"] < b["start"]):
            best[cd["window"]] = cd
    return sorted(best.values(), key=lambda d: d["start"])


def detect_details(times, glucose, params):
    return choose(candidates(times, glucose, params), params["min_height"])


def detect(times, glucose, params):
    t = pd.DatetimeIndex(times)
    return t[[d["start"] for d in detect_details(times, glucose, params)]]


def detection_extras(times, glucose, params):
    t = pd.DatetimeIndex(times)
    ds = detect_details(times, glucose, params)
    return pd.DataFrame({"detection_time": t[[d["start"] for d in ds]],
                         "excursion_start": t[[d["start"] for d in ds]],
                         "peak_time": t[[d["peak"] for d in ds]],
                         "excursion_end": t[[d["end"] for d in ds]]})


def detect_grid(times, glucose, cfg):
    fx = fixed_params(cfg)
    cands = candidates(times, glucose, fx)
    return [np.array([d["start"] for d in choose(cands, p["min_height"])], int) for p in param_grid(cfg)]
