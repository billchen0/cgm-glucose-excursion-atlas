"""CGMacros loader shared by all replications.

Conventions (see docs/evaluation_plan_v3.md, section 2):
* Only the Dexcom G6 Pro channel (`Dexcom GL`) is used, down-sampled back to its native
  5-min grid. The CSVs linearly interpolate Dexcom to 1 min; the native samples are
  the rows whose minute-phase (minutes since epoch mod 5) reproduces every other row
  by linear interpolation. Each subject has exactly one such phase (residual 0).
* Missing Dexcom samples stay NaN; timestamps missing from the CSV are reindexed as NaN.
* Meal log = every row with a `Meal Type` (snacks included). Entries logged < 30 min
  after the previous kept entry are merged into it (photos of the same meal / before-
  after photos); the earliest timestamp is kept as the meal start.
"""
import os
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]


def _data_dir():
    """CGMacros folder: env CGMACROS_DIR, else common/configs/paths.toml (relative to REPO)."""
    p = os.environ.get("CGMACROS_DIR")
    if not p:
        with open(REPO / "common" / "configs" / "paths.toml", "rb") as f:
            p = tomllib.load(f)["cgmacros_dir"]
    return (REPO / Path(p).expanduser()).resolve()


CGMACROS_DIR = _data_dir()
SAMPLE_MIN = 5
MEAL_MERGE_MIN = 30


def list_subjects():
    return sorted(p.name for p in CGMACROS_DIR.glob("CGMacros-*") if p.is_dir())


def _normalize_meal_type(s):
    s = str(s).strip().lower()
    if s.startswith("snack"):
        return "snack"
    return s


def _native_dexcom(ts, g):
    """Return (times, values) of the native 5-min Dexcom grid."""
    full = pd.Series(g, index=ts)
    full = full.reindex(pd.date_range(ts.min(), ts.max(), freq="1min"))
    vals = full.to_numpy(dtype=float)
    minutes = (full.index.astype("int64") // 60_000_000_000).to_numpy()
    ok = ~np.isnan(vals)
    best, best_res = None, np.inf
    for p in range(SAMPLE_MIN):
        idx = np.flatnonzero((minutes % SAMPLE_MIN) == p)
        sel = idx[ok[idx]]
        if len(sel) < 2:
            continue
        interp = np.interp(np.arange(len(vals)), sel, vals[sel])
        res = np.median(np.abs(interp - vals)[ok])
        if res < best_res:
            best, best_res = p, res
    idx = np.flatnonzero((minutes % SAMPLE_MIN) == best)
    return full.index[idx], vals[idx], best_res


def load_subject(subject, merge_min=MEAL_MERGE_MIN):
    """Return dict with 5-min Dexcom trace and merged meal log for one subject."""
    f = CGMACROS_DIR / subject / f"{subject}.csv"
    d = pd.read_csv(f)
    d.columns = [c.strip() for c in d.columns]
    d["Timestamp"] = pd.to_datetime(d["Timestamp"])
    d = d.drop_duplicates("Timestamp").sort_values("Timestamp")

    t, g, res = _native_dexcom(d["Timestamp"], d["Dexcom GL"].to_numpy(dtype=float))
    # trim leading/trailing NaN
    ok = np.flatnonzero(~np.isnan(g))
    t, g = t[ok[0]:ok[-1] + 1], g[ok[0]:ok[-1] + 1]

    m = d[d["Meal Type"].notna()][["Timestamp", "Meal Type", "Calories", "Carbs"]].copy()
    m["Meal Type"] = m["Meal Type"].map(_normalize_meal_type)
    m = m.sort_values("Timestamp").reset_index(drop=True)
    n_raw = len(m)
    keep, last = [], None
    for i, ts in enumerate(m["Timestamp"]):
        if last is None or (ts - last) >= pd.Timedelta(minutes=merge_min):
            keep.append(i)
            last = ts
    meals = m.iloc[keep].reset_index(drop=True)
    return {
        "subject": subject,
        "time": pd.DatetimeIndex(t),
        "glucose": g,
        "phase_residual": res,
        "meals": meals,
        "n_meal_rows_raw": n_raw,
    }


def load_bio():
    b = pd.read_csv(CGMACROS_DIR / "bio.csv")
    b.columns = [c.strip() for c in b.columns]
    b["subject"] = b["subject"].map(lambda s: f"CGMacros-{int(s):03d}")
    a1c = b["A1c PDL (Lab)"]
    b["group"] = np.where(a1c < 5.7, "healthy", np.where(a1c < 6.5, "prediabetes", "T2D"))
    return b[["subject", "A1c PDL (Lab)", "group"]]
