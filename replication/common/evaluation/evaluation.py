"""Event-level evaluation following the C05 benchmark (Hochsmann 2026, Methods,
"Training, validation, testing, and performance evaluation"):

* A detection is a TP if it falls within the TP window after a logged meal start
  (default (0, 120] min; "only detections occurring after the logged meal start
  were included; negative values were not considered").
* Each meal can be matched by at most one detection and vice versa (greedy,
  chronological, earliest eligible detection).
* A 120-min lockout follows each TP detection: unmatched detections inside it are
  ignored (neither TP nor FP).
* Detections and meals between 22:00 and 07:00 are excluded.
* Remaining unmatched detections are FP; unmatched meals are FN.
* Delay = detection time - logged meal start, over TPs.

C05 also suppressed afternoon detections because afternoon snacks were not logged.
CGMacros logs snacks, so that rule is NOT applied here.
"""
import numpy as np
import pandas as pd


def in_night(ts, start_h=22, end_h=7):
    h = pd.DatetimeIndex(ts).hour
    return (h >= start_h) | (h < end_h)


def match_events(det_times, meal_times, win_before_min=0, win_after_min=120,
                 lockout_min=120, exclude_night=True):
    det = pd.DatetimeIndex(sorted(det_times))
    meals = pd.DatetimeIndex(sorted(meal_times))
    if exclude_night:
        det = det[~in_night(det)] if len(det) else det
        meals = meals[~in_night(meals)] if len(meals) else meals
    used = np.zeros(len(det), bool)
    delays, tp_det_times, tp_meals = [], [], []
    fn = 0
    for m in meals:
        lo = m - pd.Timedelta(minutes=win_before_min)
        hi = m + pd.Timedelta(minutes=win_after_min)
        cand = np.flatnonzero((~used) & (det >= lo) & (det <= hi))
        if len(cand):
            j = cand[0]
            used[j] = True
            delays.append((det[j] - m).total_seconds() / 60)
            tp_det_times.append(det[j])
            tp_meals.append(m)
        else:
            fn += 1
    locked = np.zeros(len(det), bool)
    for t in tp_det_times:
        locked |= (det > t) & (det <= t + pd.Timedelta(minutes=lockout_min))
    fp_mask = ~used & ~locked
    return {"tp": len(delays), "fn": fn, "fp": int(fp_mask.sum()), "delays": delays,
            "n_meals": len(meals), "fp_times": list(det[fp_mask]), "tp_meal_times": tp_meals}


def summarize(tp, fp, fn, days, delays):
    sens = tp / (tp + fn) if tp + fn else np.nan
    prec = tp / (tp + fp) if tp + fp else np.nan
    f1 = 2 * tp / (2 * tp + fp + fn) if (tp + fp + fn) else np.nan
    return {
        "TP": tp, "FP": fp, "FN": fn, "days": days,
        "sensitivity": sens, "precision": prec, "F1": f1,
        "FP_per_day": fp / days if days else np.nan,
        "delay_mean_min": float(np.mean(delays)) if len(delays) else np.nan,
        "delay_median_min": float(np.median(delays)) if len(delays) else np.nan,
    }
