"""Standard result format shared by every method (spec: common/docs/result_format.md).

* ``write_run``           validate and write one run folder (run.json + CSVs)
* ``read_run``            load one run folder
* ``discover_runs``       every run.json under methods/*/results/
* ``cohort_days``         days.csv rows from the common QC and scoring windows
* ``participant_summary`` TP / FP / FN / sensitivity / FP per day, per participant and route
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

FORMAT_VERSION = 1
DET_STATUS = ["TP", "FP", "not_scored", "removed_by_rule", "ignored_by_tp_lockout"]
MEAL_OUTCOME = ["TP", "FN", "not_scored"]
QC_STATUS = ["valid", "gap_partial", "gap_internal", "no_breakfast_lunch",
             "participant_excluded", "sensor_warmup"]
DET_COLS = ["participant", "detection_time", "route", "split", "status", "status_original",
            "matched_meal_time", "delay_min"]
DET_OPTIONAL = ["excursion_start", "peak_time", "excursion_end"]
MEAL_COLS = ["participant", "meal_time", "meal_type", "carbs", "scored", "outcome", "route", "split"]
DAY_COLS = ["participant", "date", "qc_status", "route_a_split", "window_start", "window_end", "scored"]
RUN_KEYS = ["method", "run", "title", "description", "date", "source", "routes", "adjacent_rule",
            "adjacent_rule_uses_labels", "matching_rule", "scoring_window", "parameters_file",
            "available", "comparable", "comparability_note"]
TIME_COLS = ["detection_time", "matched_meal_time", "meal_time", "window_start", "window_end",
             *DET_OPTIONAL]


def _check(df, cols, name):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name}: missing columns {missing}")


def _check_values(s, allowed, name):
    bad = sorted(set(s.dropna().unique()) - set(allowed))
    if bad:
        raise ValueError(f"{name}: unexpected values {bad} (allowed {allowed})")


def validate(meta, detections, meals=None, days=None):
    missing = [k for k in RUN_KEYS if k not in meta]
    if missing:
        raise ValueError(f"run.json: missing keys {missing}")
    if not meta["comparable"] and not meta["comparability_note"]:
        raise ValueError("run.json: comparability_note is required when comparable is false")
    _check(detections, DET_COLS, "detections.csv")
    _check_values(detections["status"], DET_STATUS, "detections.status")
    routes = set(meta["routes"])
    for name, df in [("detections", detections), ("meals", meals)]:
        if df is not None and not set(df["route"].unique()) <= routes:
            raise ValueError(f"{name}.route: {set(df['route'].unique()) - routes} not in run.json routes")
    if meals is not None:
        _check(meals, MEAL_COLS, "meals.csv")
        _check_values(meals["outcome"], MEAL_OUTCOME, "meals.outcome")
    if days is not None:
        _check(days, DAY_COLS, "days.csv")
        _check_values(days["qc_status"], QC_STATUS, "days.qc_status")
    avail = meta["available"]
    if avail.get("meals") != (meals is not None) or avail.get("days") != (days is not None):
        raise ValueError("run.json 'available' does not match the tables passed")


def _order(df, cols):
    return df[cols + [c for c in df.columns if c not in cols]]


def write_run(out_dir, meta, detections, meals=None, days=None):
    """Write one run folder. Required columns first, extra method columns kept after them."""
    meta = {"format_version": FORMAT_VERSION, **meta}
    validate(meta, detections, meals, days)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "run.json", "w") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
        f.write("\n")
    _order(detections, DET_COLS).to_csv(out / "detections.csv", index=False)
    for fname, df, cols in [("meals.csv", meals, MEAL_COLS), ("days.csv", days, DAY_COLS)]:
        if df is not None:
            _order(df, cols).to_csv(out / fname, index=False)
        elif (out / fname).exists():
            (out / fname).unlink()
    return out


def read_run(run_dir):
    """{'dir', 'meta', 'det', 'meals', 'days'}; meals/days are None when not available."""
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "run.json").read_text())

    def load(name):
        if not meta["available"].get(name.split(".")[0], name == "detections.csv"):
            return None
        df = pd.read_csv(run_dir / name)
        for c in TIME_COLS:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c])
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.date
        return df

    return {"dir": run_dir, "meta": meta, "det": load("detections.csv"),
            "meals": load("meals.csv"), "days": load("days.csv")}


def discover_runs(repo=REPO):
    """Run folders (those containing run.json) under methods/*/results/, sorted."""
    return sorted(p.parent for p in Path(repo).glob("methods/*/results/**/run.json"))


def cohort_days(cfg):
    """days.csv rows for every screened participant-day, from the common QC and cohort code.

    qc_status comes from build_cohort_flow.process (rules 1-3) plus the min_valid_days rule;
    days before the first retained minute (24-h sensor warm-up) are 'sensor_warmup'. Scoring
    windows come from common.evaluation.data.build_cohort, the Route A split from
    common.evaluation.tuning.route_a_split.
    """
    from common.evaluation import data as D, tuning as T
    import build_cohort_flow as B
    import cgmacros as C

    cohort = D.build_cohort(cfg)
    split = T.route_a_split(cohort, cfg)
    cd = cohort.days.assign(route_a_split=split)
    rows = []
    for subject in C.list_subjects():
        _, qc, _ = B.process(subject)
        g = B.load_1min(subject)
        in_cohort = subject in set(cohort.participants.subject)
        screened = pd.date_range(g.index[0].normalize(), g.index[-1].normalize(), freq="D")
        qc = qc.set_index(pd.to_datetime(qc.day))
        for day in screened:
            r = dict(participant=subject, date=day.date(), route_a_split=None,
                     window_start=pd.NaT, window_end=pd.NaT, scored=False)
            if day not in qc.index:
                r["qc_status"] = "sensor_warmup"
            else:
                q = qc.loc[day]
                if q.gap_status != "gap_ok":
                    r["qc_status"] = q.gap_status
                elif not q.valid:
                    r["qc_status"] = "no_breakfast_lunch"
                elif not in_cohort:
                    r["qc_status"] = "participant_excluded"
                else:
                    c = cd.loc[f"{subject}_{day.date()}"]
                    r.update(qc_status="valid", route_a_split=c.route_a_split,
                             window_start=c.window_start, window_end=c.window_end,
                             scored=bool(c.scored))
            rows.append(r)
    days = pd.DataFrame(rows)
    days.loc[~days.scored, ["window_start", "window_end"]] = pd.NaT
    return days[DAY_COLS]


def participant_summary(run, participants=None):
    """Per participant and route: TP, FP, FN, sensitivity, FP per day (and scored days).

    TP/FN come from meals.csv, FP from detections.csv, the FP/day denominator from days.csv
    restricted to the route's evaluated_days. Without meals/days, FN, sensitivity and
    FP/day are NaN (TP is then counted from detections).
    """
    meta, det, meals, days = run["meta"], run["det"], run["meals"], run["days"]
    if participants is None:
        participants = sorted(det.participant.unique())
    rows = []
    for route, rmeta in meta["routes"].items():
        ev = rmeta.get("evaluated_days", "all")
        dsel = None
        if days is not None:
            dsel = days[days.scored]
            if ev != "all":
                dsel = dsel[dsel[ev["column"]].isin(ev["values"])]
        for p in participants:
            d = det[(det.participant == p) & (det.route == route)]
            fp = int((d.status == "FP").sum())
            if meals is not None:
                m = meals[(meals.participant == p) & (meals.route == route)]
                tp, fn = int((m.outcome == "TP").sum()), int((m.outcome == "FN").sum())
            else:
                tp, fn = int((d.status == "TP").sum()), np.nan
            n_days = int((dsel.participant == p).sum()) if dsel is not None else np.nan
            sens = tp / (tp + fn) if meals is not None and tp + fn else np.nan
            rows.append(dict(participant=p, route=route, TP=tp, FP=fp, FN=fn, sensitivity=sens,
                             scored_days=n_days,
                             FP_per_day=fp / n_days if n_days and n_days == n_days else np.nan))
    return pd.DataFrame(rows)
