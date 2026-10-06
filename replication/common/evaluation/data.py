"""Analysis cohort for CGMacros (plan v3 sections 2-3), built on common/qc/build_cohort_flow.py.

* Valid days and participants come from ``build_cohort_flow.process`` (rules 1-3) plus
  the minimum-valid-day rule from the config (rule 4).
* The CGM series is the cohort-flow 1-min Dexcom series with gaps <= 30 min linearly
  interpolated and the 24-h post-insertion warm-up set to missing.
* 5-min detector input: the native Dexcom readings, i.e. the 1-min series sampled at the
  day's native minute phase (identified with ``cgmacros._native_dexcom``).
* Meals: ``cgmacros.load_subject`` (entries < 30 min apart merged, start = first entry),
  breakfast and lunch on valid days.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import load_config  # noqa: F401  (sets sys.path for the imports below)
import build_cohort_flow as B  # noqa: E402
import cgmacros as C  # noqa: E402


@dataclass
class Cohort:
    participants: pd.DataFrame          # subject, group, n_days
    days: pd.DataFrame                  # one row per valid day (day_id index)
    meals: pd.DataFrame                 # breakfast/lunch on valid days
    series_1min: dict = field(repr=False)   # subject -> pd.Series (QC'd 1-min)
    day_5min: dict = field(repr=False)      # day_id -> (DatetimeIndex, np.ndarray)

    def day_series(self, day_id, sampling_min=5):
        if sampling_min == 5:
            return self.day_5min[day_id]
        d = self.days.loc[day_id]
        s = self.series_1min[d.subject]
        t = pd.date_range(d.date, periods=1440, freq="1min")
        return t, s.reindex(t).to_numpy(float)


def qc_series(subject):
    """Cohort-flow 1-min series: interpolated short gaps, warm-up removed. Also returns raw."""
    g = B.load_1min(subject)
    warm = np.zeros(len(g), bool)
    for a in B.sensor_starts(g):
        warm[a:a + B.WARMUP_MIN] = True
    gi = B.interpolate_short(g)
    gi[warm] = np.nan
    return gi, g


def build_cohort(cfg):
    dcfg, scfg = cfg["data"], cfg["scoring"]
    bio = C.load_bio().set_index("subject")
    parts, day_rows, meal_rows, s1, d5 = [], [], [], {}, {}
    for subject in C.list_subjects():
        _, qc_days, _ = B.process(subject)
        valid = qc_days[qc_days.valid]
        if len(valid) < dcfg["min_valid_days"]:
            continue
        gi, graw = qc_series(subject)
        s1[subject] = gi
        grp = bio.loc[subject, "group"]
        parts.append(dict(subject=subject, group=grp, n_days=len(valid)))
        meals = C.load_subject(subject, merge_min=dcfg["meal_merge_min"])["meals"]
        meals = meals[meals["Meal Type"].isin(dcfg["ground_truth_meals"])]
        for day in valid.day:
            date = pd.Timestamp(day)
            day_id = f"{subject}_{date.date()}"
            raw = graw[date:date + pd.Timedelta(minutes=1439)]
            nat_t, _, res = C._native_dexcom(raw.index, raw.to_numpy(float))
            phase = int(nat_t[0].minute % 5)
            t5 = pd.date_range(date + pd.Timedelta(minutes=phase), periods=288, freq="5min")
            d5[day_id] = (t5, gi.reindex(t5).to_numpy(float))
            dm = meals[meals.Timestamp.dt.normalize() == date]
            lunch_last = dm.loc[dm["Meal Type"] == "lunch", "Timestamp"].max()
            ws = date + pd.Timedelta(hours=scfg["window_start_h"])
            we = min(lunch_last + pd.Timedelta(minutes=scfg["window_end_after_lunch_min"]),
                     date + pd.Timedelta(hours=scfg["night_start_h"]))
            day_rows.append(dict(day_id=day_id, subject=subject, group=grp, date=date,
                                 phase=phase, phase_residual=res,
                                 window_start=ws, window_end=we,
                                 scored=we > ws,        # False if lunch is logged before ~04:00
                                 scored_hours=max((we - ws).total_seconds() / 3600, 0.0)))
            for _, m in dm.iterrows():
                meal_rows.append(dict(day_id=day_id, subject=subject, group=grp,
                                      meal_type=m["Meal Type"], start=m.Timestamp,
                                      carbs=m.Carbs))
    days = pd.DataFrame(day_rows).set_index("day_id")
    meals = pd.DataFrame(meal_rows)
    meals["meal_id"] = meals.day_id + "_" + meals.meal_type
    return Cohort(pd.DataFrame(parts), days, meals, s1, d5)
