"""Shared excursion definition (2026-10-01), used by the ``excursion_end`` adjacent rule and by
the recovery features (``[features] segmentation = "excursion"``). Parameters: ``[excursion]``.

For an anchor a (a detection, or the logged meal start for the reference) on the QC'd 1-min
glucose:
* baseline b = min glucose over the valid minutes in [a - lookback, a];
* running peak P(t) = max glucose in (a, t] (first time of the maximum on ties);
* the excursion ends at the earliest of
  1. return:  glucose(t) <= b + max(abs_tol, rel_tol * (P(t) - b)), t after the time of P(t);
  2. trough:  t after the time of P(t), (P(t) - glucose(t)) >= trough_drop * (P(t) - b), and
              glucose rises to >= glucose(t) + trough_rise within (t, t + trough_confirm]
              without first going below glucose(t) and without missing minutes (so t is the
              local minimum). The rise check may look past a + max_event;
  3. censor:  a + max_event.
  Rise gate (added 2026-10-01 after the first run, see deviations): a return or a trough counts
  only once P(t) - b >= abs_tol, i.e. the excursion must first rise. If it never rises that far
  within max_event, end_type = "no_rise" and the end is a + max_event.
  Fall requirement (added 2026-10-01, second post-result fix): any end (return or trough) also
  needs P(t) - glucose(t) >= trough_drop * (P(t) - b), so a 1 mg/dL dip after a small rise is
  not an end. The definition is frozen after this change.
  If return and trough fall on the same minute, the end type is "returned".
  Missing minutes never count as a return or a trough.
* end_type: returned | trough | trough_interrupted | censored | no_rise. A trough is
  "interrupted" when a new start lies in the given window around the trough time.
"""
import numpy as np
import pandas as pd

MIN = pd.Timedelta(minutes=1)


def trough_confirmed(v, rise, confirm):
    """conf[j]: glucose rises to >= v[j] + rise within (j, j + confirm] without first going
    below v[j] and with no missing minute on the way."""
    n = len(v)
    ok = np.zeros(n, bool)
    alive = np.isfinite(v)
    with np.errstate(invalid="ignore"):
        for k in range(1, confirm + 1):
            x = np.full(n, np.nan)
            x[:n - k] = v[k:]
            alive = alive & np.isfinite(x)
            ok |= alive & (x >= v + rise)
            alive = alive & (x >= v)
    return ok


class Trace:
    """A participant's QC'd 1-min series with the trough confirmation precomputed."""

    def __init__(self, series_1min, ecfg):
        self.ecfg = ecfg
        pad = int(ecfg["lookback_min"]) + int(ecfg["max_event_min"]) + int(ecfg["trough_confirm_min"]) + 1
        idx = pd.date_range(series_1min.index[0] - pad * MIN, series_1min.index[-1] + pad * MIN,
                            freq="1min")
        self.t0 = idx[0]
        self.v = series_1min.reindex(idx).to_numpy(float)
        self.conf = trough_confirmed(self.v, ecfg["trough_rise_mg_dl"], int(ecfg["trough_confirm_min"]))

    def index_of(self, t):
        return int((pd.Timestamp(t).floor("min") - self.t0) / MIN)

    def excursion(self, a, new_starts=None, start_window=(0, 30), closed_lo=False):
        """Excursion anchored at a. ``new_starts``: times that mark a new start; a trough at t_m
        is interrupted if one lies in (t_m + lo, t_m + hi] ([.. if ``closed_lo``)."""
        e = self.ecfg
        lb, h = int(e["lookback_min"]), int(e["max_event_min"])
        a = pd.Timestamp(a).floor("min")
        ia = self.index_of(a)
        fallback = not np.isfinite(self.v[ia - lb:ia]).any()
        w = self.v[ia - lb:ia + 1]
        b = float(np.nanmin(w)) if np.isfinite(w).any() else np.nan
        g = self.v[ia + 1:ia + 1 + h]                      # minutes a+1 .. a+h
        c = self.conf[ia + 1:ia + 1 + h]
        idx = np.arange(h)
        gg = np.where(np.isnan(g), -np.inf, g)
        P = np.maximum.accumulate(gg)
        new = gg > np.concatenate([[-np.inf], P[:-1]])
        tp = np.maximum.accumulate(np.where(new, idx, 0))
        valid = np.isfinite(g)
        with np.errstate(invalid="ignore"):
            after = (idx > tp) & (P - b >= e["abs_tol_mg_dl"])      # rise gate
            fell = (P - g) >= e["trough_drop"] * (P - b)            # fall requirement
            ret = after & valid & fell & (g <= b + np.maximum(e["abs_tol_mg_dl"], e["rel_tol"] * (P - b)))
            tro = after & valid & c & fell
        ir = np.flatnonzero(ret)
        it = np.flatnonzero(tro)
        ir = int(ir[0]) if len(ir) else h
        it = int(it[0]) if len(it) else h
        if ir == h and it == h:
            rose = bool(P[-1] - b >= e["abs_tol_mg_dl"])
            i, end_type = h - 1, ("censored" if rose else "no_rise")
        elif ir <= it:
            i, end_type = ir, "returned"
        else:
            i, end_type = it, "trough"
        end_min = i + 1                                    # minutes after a
        end = a + end_min * MIN
        if end_type == "trough" and new_starts is not None and len(new_starts):
            lo, hi = end + start_window[0] * MIN, end + start_window[1] * MIN
            ns = pd.DatetimeIndex(new_starts)
            hit = ((ns >= lo) if closed_lo else (ns > lo)) & (ns <= hi)
            if hit.any():
                end_type = "trough_interrupted"
        return dict(baseline=b, fallback=fallback, peak=float(P[i]), peak_min=int(tp[i]) + 1,
                    end=end, end_min=end_min, end_type=end_type,
                    censored=end_type == "censored")
