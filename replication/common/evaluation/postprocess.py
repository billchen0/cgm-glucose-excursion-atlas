"""Label-free adjacent-detection rules, applied to a day's detections BEFORE scoring.

Selected by ``[scoring] adjacent_rule`` in the config:
* ``tp_lockout``           - no post-processing; the scorer ignores unmatched detections
                             within ``lockout_min`` after each TP (Hochsmann 2026; reference run).
* ``meal_window_max_peak`` - one detection per fixed clock-time meal window, the one with the
                             highest peak (max glucose in (t, t + horizon]); ties -> earlier;
                             detections outside every window are dropped (Lim 2026).
* ``refractory``           - drop a detection within ``refractory_min`` of the previous kept one.
* ``baseline_return``      - a detection opens an event (anchor d0); later detections are merged
                             into it until glucose returns near the pre-anchor baseline, or until
                             ``max_event_min`` (censored). See ``event_close``.
* ``excursion_end``        - as baseline_return, but the event ends at the shared excursion end
                             (return, confirmed trough or censor; ``excursion.py``, ``[excursion]``).
None of the label-free rules uses meal labels.
"""
import numpy as np
import pandas as pd

from .excursion import Trace

MIN = pd.Timedelta(minutes=1)


def uses_tp_lockout(cfg):
    return cfg["scoring"]["adjacent_rule"] == "tp_lockout"


def _hhmm(s):
    h, m = map(int, s.split(":"))
    return 60 * h + m


def forward_peak(series_1min, times, horizon_min):
    """Max of the 1-min series in (t, t + horizon] for each t; NaN if no data."""
    v = series_1min.reindex(pd.date_range(pd.Timestamp(times[0]).floor("min"),
                                           pd.Timestamp(times[-1]).floor("min")
                                           + pd.Timedelta(minutes=horizon_min), freq="1min"))
    arr = v.to_numpy(float)
    start = ((pd.DatetimeIndex(times).floor("min") - v.index[0]) / MIN).astype(int)
    out = np.full(len(start), np.nan)
    for i, a in enumerate(start):
        w = arr[a + 1:a + 1 + horizon_min]
        if np.isfinite(w).any():
            out[i] = np.nanmax(w)
    return out


def event_close(series_1min, times, rc):
    """Closing time of a baseline_return event anchored at each time in ``times``.

    Baseline b = min glucose in [d0 - lookback, d0]. If [d0 - lookback, d0) has no valid data,
    b = glucose at d0 and the event is flagged ``fallback``.
    Running peak P(t) = max glucose in (d0, t]. The event closes at the first minute t after
    the time of P(t) with glucose(t) <= b + max(abs_tol, rel_tol * (P(t) - b)); missing minutes
    never close it. Not closed by d0 + max_event -> closes there, censored.
    Returns a DataFrame indexed like ``times``: baseline, fallback, peak, close, censored.
    """
    lb, h = int(rc["lookback_min"]), int(rc["max_event_min"])
    times = pd.DatetimeIndex(times).floor("min")
    if len(times) == 0:
        return pd.DataFrame(columns=["baseline", "fallback", "peak", "close", "censored"])
    v = series_1min.reindex(pd.date_range(times[0] - pd.Timedelta(minutes=lb),
                                          times[-1] + pd.Timedelta(minutes=h), freq="1min"))
    arr = v.to_numpy(float)
    rows = []
    for t in times:
        a = int((t - v.index[0]) / MIN)                 # index of d0
        fallback = not np.isfinite(arr[a - lb:a]).any()
        b = arr[a] if fallback else np.nanmin(arr[a - lb:a + 1])
        g = arr[a + 1:a + 1 + h]                        # minutes d0+1 .. d0+h
        gg = np.where(np.isnan(g), -np.inf, g)
        P = np.maximum.accumulate(gg)
        idx = np.arange(len(g))
        new = gg > np.concatenate([[-np.inf], P[:-1]])  # strictly new running max
        tp = np.maximum.accumulate(np.where(new, idx, 0))
        with np.errstate(invalid="ignore"):
            thr = b + np.maximum(rc["abs_tol_mg_dl"], rc["rel_tol"] * (P - b))
            ok = (idx > tp) & np.isfinite(g) & (g <= thr)
        hit = np.flatnonzero(ok)
        censored = not len(hit)
        close = t + pd.Timedelta(minutes=h if censored else int(hit[0]) + 1)
        rows.append(dict(baseline=b, fallback=fallback, peak=float(P[-1]) if len(P) else np.nan,
                         close=close, censored=censored))
    return pd.DataFrame(rows, index=times)


def keep_mask(det_min, peaks, cfg, close_min=None):
    """Boolean mask of kept detections. det_min: sorted minutes since midnight.

    ``close_min`` (baseline_return only): event closing minute for each detection as anchor.
    """
    rule = cfg["scoring"]["adjacent_rule"]
    det_min = np.asarray(det_min, float)
    n = len(det_min)
    if rule == "tp_lockout" or n == 0:
        return np.ones(n, bool)
    rc = cfg["adjacent_rules"][rule]
    keep = np.zeros(n, bool)
    if rule == "meal_window_max_peak":
        pk = np.where(np.isnan(peaks), -np.inf, peaks)
        for lo, hi in rc["windows"].values():
            idx = np.flatnonzero((det_min >= _hhmm(lo)) & (det_min <= _hhmm(hi)))
            if len(idx):
                keep[idx[np.argmax(pk[idx])]] = True       # argmax -> earliest on ties
        return keep
    if rule == "refractory":
        last = -np.inf
        for i, t in enumerate(det_min):
            if t - last > rc["refractory_min"]:
                keep[i] = True
                last = t
        return keep
    if rule in EVENT_RULES:
        open_until = -np.inf
        for i, t in enumerate(det_min):
            if t >= open_until:                          # event closed: t opens a new one
                keep[i] = True
                open_until = close_min[i]
        return keep
    raise ValueError(rule)


EVENT_RULES = ("baseline_return", "excursion_end")
_TRACES = {}


def trace_for(series_1min, ecfg):
    """Cached excursion Trace of a participant series (keyed by the series object)."""
    key = id(series_1min)
    hit = _TRACES.get(key)
    if hit is None or hit[0] is not series_1min or hit[1] != ecfg:
        hit = _TRACES[key] = (series_1min, dict(ecfg), Trace(series_1min, ecfg))
    return hit[2]


def needs_close(cfg):
    return cfg["scoring"]["adjacent_rule"] in EVENT_RULES


def event_info(series_1min, times, cfg, raw_detections=None):
    """Per anchor time: baseline, fallback, peak, close, censored (+ end_type for excursion_end).

    ``raw_detections``: all detections of the day, used to label interrupted troughs.
    """
    if cfg["scoring"]["adjacent_rule"] == "baseline_return":
        return event_close(series_1min, times, cfg["adjacent_rules"]["baseline_return"])
    ecfg = cfg["excursion"]
    tr = trace_for(series_1min, ecfg)
    w = (0, int(ecfg["interrupt_window_min"]))
    rows = [tr.excursion(t, raw_detections, w) for t in times]
    out = pd.DataFrame(rows, index=pd.DatetimeIndex(times).floor("min"))
    return out.rename(columns={"end": "close"})[["baseline", "fallback", "peak", "close",
                                                  "censored", "end_type"]]


def close_minutes(series_1min, times, date, cfg):
    """Event closing minute (since ``date`` midnight) for each time; NaN array if not needed."""
    if not needs_close(cfg) or len(times) == 0:
        return np.full(len(times), np.nan)
    if cfg["scoring"]["adjacent_rule"] == "baseline_return":
        ev = event_close(series_1min, times, cfg["adjacent_rules"]["baseline_return"])
        return np.asarray((pd.DatetimeIndex(ev.close) - date) / MIN)
    tr = trace_for(series_1min, cfg["excursion"])
    return np.array([(tr.excursion(t)["end"] - date) / MIN for t in pd.DatetimeIndex(times)])


def needs_peaks(cfg):
    return cfg["scoring"]["adjacent_rule"] == "meal_window_max_peak"


def peak_horizon(cfg):
    return cfg["adjacent_rules"]["meal_window_max_peak"]["peak_horizon_min"]
