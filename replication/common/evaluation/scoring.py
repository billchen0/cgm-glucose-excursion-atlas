"""Scoring windows and event matching (plan v3 sections 4 and 7).

Matching reuses ``common/evaluation.match_events`` (greedy, chronological; each meal takes
the earliest unused detection in its TP window; unmatched detections within ``lockout``
after a TP detection are ignored; the rest are FP). ``match_fast`` is a plain-number
re-implementation used only inside the tuning grid; ``check_fast_matcher`` asserts that
both give identical counts.
"""
import numpy as np
import pandas as pd

from . import load_config  # noqa: F401
from .evaluation import match_events  # noqa: E402
from .postprocess import uses_tp_lockout  # noqa: E402

MIN = pd.Timedelta(minutes=1)


def rule_params(cfg, rule):
    """(TP window before, after, TP lockout). The lockout is 0 unless adjacent_rule = tp_lockout."""
    r = cfg["scoring"]["rules"][rule]
    lockout = cfg["scoring"]["lockout_min"] if uses_tp_lockout(cfg) else 0
    return r["tp_before_min"], r["tp_after_min"], lockout


def scored_meals(cohort, cfg, rule):
    """Meals with a ``scored`` flag: the TP window must reach into the day's scoring window."""
    before, after, _ = rule_params(cfg, rule)
    m = cohort.meals.join(cohort.days[["window_start", "window_end"]], on="day_id")
    m["scored"] = ((m.start + after * MIN >= m.window_start) &
                   (m.start - before * MIN <= m.window_end))
    return m.drop(columns=["window_start", "window_end"])


def in_window(times, day):
    t = pd.DatetimeIndex(times)
    return t[(t >= day.window_start) & (t <= day.window_end)]


def score_day(det_times, day, day_meals, cfg, rule):
    """Full per-event scoring of one day. Returns (detection rows, meal rows)."""
    before, after, lockout = rule_params(cfg, rule)
    all_det = pd.DatetimeIndex(sorted(det_times))
    det = in_window(all_det, day)
    meals = day_meals[day_meals.scored].sort_values("start")
    r = match_events(det, meals.start, win_before_min=before, win_after_min=after,
                     lockout_min=lockout, exclude_night=False)
    tp_det = {m + pd.Timedelta(minutes=d): m for m, d in zip(r["tp_meal_times"], r["delays"])}
    fp = set(r["fp_times"])
    by_start = meals.set_index("start")
    drows = []
    for t in all_det:
        row = dict(subject=day.subject, day_id=day.name, group=day.group, detection_time=t,
                   matched_meal_id=None, matched_meal_type=None, matched_meal_start=pd.NaT,
                   delay_min=np.nan)
        if t < day.window_start or t > day.window_end:
            row["status"] = "not_scored"
        elif t in tp_det:
            m = tp_det[t]
            row.update(status="TP", matched_meal_id=by_start.loc[m, "meal_id"],
                       matched_meal_type=by_start.loc[m, "meal_type"], matched_meal_start=m,
                       delay_min=(t - m).total_seconds() / 60)
        elif t in fp:
            row["status"] = "FP"
        else:
            row["status"] = "lockout"
        drows.append(row)
    mrows = day_meals.copy()
    mrows["status"] = np.where(mrows.scored, "FN", "not_scored")
    for t, m in tp_det.items():
        k = mrows.index[mrows.start == m]
        mrows.loc[k, "status"] = "TP"
        mrows.loc[k, "detection_time"] = t
        mrows.loc[k, "delay_min"] = (t - m).total_seconds() / 60
    assert (mrows.status == "TP").sum() == r["tp"] and (mrows.status == "FN").sum() == r["fn"]
    return drows, mrows


def match_fast(det, meals, before, after, lockout):
    """Same algorithm as match_events on sorted float minutes. Returns (tp, fp, fn, delay_sum)."""
    used = [False] * len(det)
    tp_t, dsum, fn = [], 0.0, 0
    for m in meals:
        lo, hi = m - before, m + after
        for j, t in enumerate(det):
            if not used[j] and lo <= t <= hi:
                used[j] = True
                tp_t.append(t)
                dsum += t - m
                break
        else:
            fn += 1
    fp = 0
    for j, t in enumerate(det):
        if used[j]:
            continue
        if not any(a < t <= a + lockout for a in tp_t):
            fp += 1
    return len(tp_t), fp, fn, dsum


def day_minutes(cohort, meals_scored):
    """Per day: (window start, window end, scored meal starts) in minutes since midnight."""
    out = {}
    ms = meals_scored[meals_scored.scored]
    for day_id, d in cohort.days.iterrows():
        mm = ms.loc[ms.day_id == day_id, "start"].sort_values()
        out[day_id] = ((d.window_start - d.date) / MIN, (d.window_end - d.date) / MIN,
                       tuple(((mm - d.date) / MIN).tolist()))
    return out


def check_fast_matcher(cohort, cfg, rule, detections):
    """Assert match_fast == match_events on {day_id: detection times}."""
    before, after, lockout = rule_params(cfg, rule)
    ms = scored_meals(cohort, cfg, rule)
    dm = day_minutes(cohort, ms)
    for day_id, times in detections.items():
        d = cohort.days.loc[day_id]
        det = in_window(times, d)
        meals = ms[(ms.day_id == day_id) & ms.scored].start
        r = match_events(det, meals, before, after, lockout, exclude_night=False)
        f = match_fast(sorted(((det - d.date) / MIN).tolist()), dm[day_id][2], before, after, lockout)
        assert (r["tp"], r["fp"], r["fn"]) == f[:3], (day_id, r, f)
        assert abs(sum(r["delays"]) - f[3]) < 1e-6
