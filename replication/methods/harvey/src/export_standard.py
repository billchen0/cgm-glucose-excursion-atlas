"""Export the saved Harvey runs to the standard result format (common/docs/result_format.md).

Reads only. No detector is run and no existing file is changed. Four runs, as saved:
  tp_lockout x ours, tp_lockout x review    results/reference_tp_lockout/  (routes A, B, Harvey2014_fixed)
  meal_window_max_peak x ours               results/peak_rules/meal_window_max_peak/  (routes A, B)
  refractory x ours                         results/peak_rules/refractory/  (routes A, B)
Output: results/standard/<run>/. Each run is checked against the saved summary.csv.

Usage: python methods/harvey/src/export_standard.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from common.evaluation import REPO, load_config  # noqa: E402
from common.export import result_format as RF  # noqa: E402

HARVEY = REPO / "methods" / "harvey"
RES = HARVEY / "results"
OUT = RES / "standard"
PUBLISHED_PARAMS = "methods/harvey/configs/harvey2014_published_params.json"
DATE = "2026-09-29"            # commits 213c0d9 (reference) and 1c7c448 (peak rules); hashes: docs/prespecification_log.md

STATUS = {"TP": "TP", "FP": "FP", "not_scored": "not_scored", "lockout": "ignored_by_tp_lockout",
          "removed_in_window": "removed_by_rule", "removed_outside_window": "removed_by_rule"}
ROUTES = {
    "A": dict(label="Route A: per-participant tuning on validation days, scored on test days",
              kind="tuning", evaluated_days={"column": "route_a_split", "values": ["test"]}),
    "B": dict(label="Route B: one global parameter set, 5-fold participant cross-validation",
              kind="tuning", evaluated_days="all"),
    "Harvey2014_fixed": dict(label="Harvey 2014 published parameters (untuned)",
                             kind="parameter_source", evaluated_days="all",
                             parameters_file=PUBLISHED_PARAMS),
}
RULE_WINDOWS = {"ours": "[-30, +120] min around the logged start",
                "review": "[0, +120] min after the logged start (Hochsmann 2026)"}
SCORING_WINDOW = ("07:00 to lunch start + 180 min (capped at 22:00) on QC-valid days; "
                  "night 22:00-07:00 not scored")
RUNS = [
    dict(run="tp_lockout_ours", folder="reference_tp_lockout", adjacent_rule="tp_lockout", rule="ours",
         desc="Reference run: 120-min lockout after each TP, applied at scoring (uses meal labels)."),
    dict(run="tp_lockout_review", folder="reference_tp_lockout", adjacent_rule="tp_lockout",
         rule="review",
         desc="Reference run with the review's TP window: 120-min lockout after each TP, "
              "applied at scoring (uses meal labels)."),
    dict(run="meal_window_max_peak_ours", folder="peak_rules/meal_window_max_peak",
         adjacent_rule="meal_window_max_peak", rule="ours",
         desc="Main label-free rule: one detection per Lim 2026 meal window, highest peak, "
              "applied before scoring."),
    dict(run="refractory_ours", folder="peak_rules/refractory", adjacent_rule="refractory", rule="ours",
         desc="Label-free sensitivity rule: 120-min refractory after every kept detection, "
              "applied before scoring."),
]


def split_of(tab, splits):
    """validation / test for Route A, cv-fold<k> for Route B, all for the fixed parameters."""
    sp = splits.set_index("day_id")
    ra = tab.day_id.map(sp.route_a)
    rb = "cv-fold" + tab.day_id.map(sp.route_b_fold).astype("Int64").astype(str)
    return np.select([tab.route == "A", tab.route == "B"], [ra, rb], "all")


def export(spec, cfg, days):
    src = RES / spec["folder"]
    det = pd.read_csv(src / "detections.csv")
    meals = pd.read_csv(src / "meals.csv")
    splits = pd.read_csv(src / "splits.csv")
    det = det[det.rule == spec["rule"]].copy()
    meals = meals[meals.rule == spec["rule"]].copy()
    det["adjacent_rule"] = spec["adjacent_rule"]          # missing in reference_tp_lockout
    meals["adjacent_rule"] = spec["adjacent_rule"]

    # Route A split in days.csv must be the one the run used
    v = days.dropna(subset=["route_a_split"])
    chk = v.set_index(v.participant + "_" + v.date.astype(str))["route_a_split"]
    assert chk.sort_index().equals(splits.set_index("day_id").route_a.sort_index().rename("route_a_split")), \
        "Route A split differs from the saved splits.csv"

    d = pd.DataFrame({
        "participant": det.subject, "detection_time": det.detection_time, "route": det.route,
        "split": split_of(det, splits), "status": det.status.map(STATUS),
        "status_original": det.status, "matched_meal_time": det.matched_meal_start,
        "delay_min": det.delay_min, "group": det.group, "day_id": det.day_id,
        "matched_meal_type": det.matched_meal_type,
        "fp_near_snack_or_dinner": det.fp_near_snack_or_dinner})
    assert d.status.notna().all(), f"unmapped status {set(det.status) - set(STATUS)}"
    m = pd.DataFrame({
        "participant": meals.subject, "meal_time": meals.start, "meal_type": meals.meal_type,
        "carbs": meals.carbs, "scored": meals.status != "not_scored", "outcome": meals.status,
        "route": meals.route, "split": split_of(meals, splits),
        "detection_time": meals.detection_time, "delay_min": meals.delay_min,
        "meal_id": meals.meal_id, "group": meals.group, "day_id": meals.day_id})

    routes = {r: ROUTES[r] | ({} if r == "Harvey2014_fixed" else {
        "parameters_file": f"methods/harvey/results/{spec['folder']}/params/"
                           f"chosen_params_route{r}_{spec['rule']}.json"})
        for r in sorted(det.route.unique())}
    rc = cfg["scoring"]["rules"][spec["rule"]]
    meta = dict(
        method="harvey", run=spec["run"],
        title=f"Harvey GRID · {spec['adjacent_rule']} · {spec['rule']} rule",
        description=spec["desc"], date=DATE, source=f"methods/harvey/results/{spec['folder']}",
        routes=routes, adjacent_rule=spec["adjacent_rule"],
        adjacent_rule_uses_labels=spec["adjacent_rule"] == "tp_lockout",
        matching_rule=dict(name=spec["rule"], tp_before_min=rc["tp_before_min"],
                           tp_after_min=rc["tp_after_min"], description=RULE_WINDOWS[spec["rule"]]),
        scoring_window=SCORING_WINDOW,
        parameters_file="methods/harvey/configs/harvey.toml",
        available=dict(detections=True, meals=True, days=True),
        comparable=True, comparability_note="")
    out = RF.write_run(OUT / spec["run"], meta, d, m, days)
    return out, check(out, spec, src)


def check(out, spec, src):
    """Pooled per-participant counts must equal the saved summary.csv (overall stratum)."""
    run = RF.read_run(out)
    ps = RF.participant_summary(run)
    ref = pd.read_csv(src / "summary.csv")
    ref = ref[(ref.rule == spec["rule"]) & (ref.stratum == "overall")].set_index("route")
    lines, ok = [], True
    for route, g in ps.groupby("route"):
        got = dict(TP=int(g.TP.sum()), FP=int(g.FP.sum()), FN=int(g.FN.sum()),
                   days=int(g.scored_days.sum()))
        r = ref.loc[route]
        exp = dict(TP=int(r.TP), FP=int(r.FP), FN=int(r.FN), days=int(r.days))
        match = got == exp
        ok &= match
        lines.append(f"  route {route:17s} {got}  {'OK' if match else f'MISMATCH saved {exp}'}")
    return ok, lines


def main():
    cfg = load_config(HARVEY / "configs" / "harvey.toml")
    days = RF.cohort_days(cfg)
    all_ok = True
    for spec in RUNS:
        out, (ok, lines) = export(spec, cfg, days)
        all_ok &= ok
        print(out.relative_to(REPO))
        print("\n".join(lines))
    print("ALL MATCH" if all_ok else "!!! MISMATCH")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
