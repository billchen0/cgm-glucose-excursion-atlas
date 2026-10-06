"""Standard evaluation protocol shared by all method replications.

* ``run_method``: tune (Route A per participant and/or Route B 5-fold CV) and evaluate one detector
  for one adjacent-detection rule and the given matching rules; writes the per-rule file set.
  Also used by the earlier Harvey runners (their outputs are unchanged).
* ``run_protocol``: the standard run, driven by ``[protocol]`` in common/configs/cgmacros_eval.toml
  (decisions: common/docs/deviations.md section Z). For each rule in ``adjacent_rules`` (first =
  main) it runs ``run_method`` on the configured routes with ``matching_rule`` (plus
  ``extra_matching_rules``) and ``[features] segmentation`` set to the protocol value. Then it
  writes comparison.csv, detection_counts.csv, protocol.json, the standard-format export
  (``standard/``, read by the dashboard), the method README and results/method_comparison.md.

A new method supplies only its detector module (registered in ``detectors.py``) and its
config (``methods/<name>/configs/*.toml``: ``[methods.<name>]`` with ``sampling_min``,
``grid`` and ``about``).
"""
import copy
import json
from datetime import date

import numpy as np
import pandas as pd

from . import CONFIG as CONFIG_PATH, REPO, load_config
from . import detectors
from . import metrics as M
from . import postprocess as P
from . import report as R
from . import scoring as S
from . import tuning as T
from .data import build_cohort
import cgmacros as C  # noqa: E402  (on sys.path via the package __init__)


# ---------------------------------------------------------------- one rule, one method
def evaluate(cohort, cfg, rule, det_mod, fixed, assign, method):
    """Run the detector with locked params on the assigned days. assign: day_id -> params."""
    ms = S.scored_meals(cohort, cfg, rule)
    drows, mrows, evrows, xrows = [], [], [], []
    for day_id, params in assign.items():
        d = cohort.days.loc[day_id]
        t, g = cohort.day_series(day_id, cfg["methods"][method]["sampling_min"])
        det = det_mod.detect(t, g, {**fixed, **params})
        if hasattr(det_mod, "detection_extras"):  # optional per-detection columns (e.g. excursion_start)
            xrows.append(det_mod.detection_extras(t, g, {**fixed, **params}).assign(day_id=day_id))
        if not P.uses_tp_lockout(cfg):          # label-free adjacent rule, before scoring
            pk = (P.forward_peak(cohort.series_1min[d.subject], det, P.peak_horizon(cfg))
                  if P.needs_peaks(cfg) and len(det) else np.full(len(det), np.nan))
            cl = P.close_minutes(cohort.series_1min[d.subject], det, d.date, cfg)
            keep = P.keep_mask(np.asarray((det - d.date) / S.MIN), pk, cfg, close_min=cl)
            if P.needs_close(cfg) and len(det):    # event bookkeeping for baseline_return
                ev = P.event_info(cohort.series_1min[d.subject], det, cfg, raw_detections=det)
                anchor = None
                for x, k in zip(det, keep):
                    anchor = x if k else anchor
                    e = ev.loc[anchor]
                    row = dict(day_id=day_id, detection_time=x, event_anchor=anchor,
                               event_baseline=e.baseline, event_close=e.close,
                               event_censored=e.censored, event_fallback=e.fallback)
                    if "end_type" in ev:
                        row["event_end_type"] = e.end_type
                    evrows.append(row)
            for x in det[~keep]:
                inside = d.window_start <= x <= d.window_end
                drows.append(dict(subject=d.subject, day_id=day_id, group=d.group, detection_time=x,
                                  matched_meal_id=None, matched_meal_type=None,
                                  matched_meal_start=pd.NaT, delay_min=np.nan,
                                  status="removed_in_window" if inside else "removed_outside_window"))
            det = det[keep]
        dr, mr = S.score_day(det, d, ms[ms.day_id == day_id], cfg, rule)
        drows += dr
        mrows.append(mr)
    days = cohort.days.loc[list(assign)].reset_index()
    det = pd.DataFrame(drows)
    if evrows:
        det = det.merge(pd.DataFrame(evrows), on=["day_id", "detection_time"], how="left",
                        validate="one_to_one")
    if xrows:
        det = det.merge(pd.concat(xrows, ignore_index=True), on=["day_id", "detection_time"],
                        how="left", validate="one_to_one")
    return det, pd.concat(mrows, ignore_index=True), days


def check_counts(det, meals, counts, day_index, assign_idx):
    """Full scoring must reproduce the grid counts used for tuning."""
    tot = sum(counts[gi, day_index.get_loc(d), :3] for d, gi in assign_idx.items())
    got = [(det.status == "TP").sum(), (det.status == "FP").sum(), (meals.status == "FN").sum()]
    assert np.allclose(tot, got), (tot, got)


def other_meals(cohort):
    """Logged snack/dinner starts (merged log) for the FP diagnostic (deviations E5)."""
    out = {}
    for s in cohort.participants.subject:
        m = C.load_subject(s)["meals"]
        out[s] = pd.DatetimeIndex(m.loc[~m["Meal Type"].isin(["breakfast", "lunch"]), "Timestamp"])
    return out


def flag_near_other(det, others):
    near = []
    for _, r in det.iterrows():
        o = others[r.subject]
        dt = (r.detection_time - o).total_seconds() / 60
        near.append(bool(r.status == "FP" and ((dt >= -60) & (dt <= 120)).any()))
    det["fp_near_snack_or_dinner"] = near
    return det


def params_record(grid, gi, tied, axes, stats):
    p = grid[gi]
    return dict(params=p, grid_edges=T.grid_edges(p, axes),
                grid_edges_forced=T.forced_edges(grid, tied, axes), **stats)


def run_method(cfg, method, out, rules=("ours",), tag_extra=None, fixed=None, fixed_refs=None,
               title=None, routes=("A", "B"), plot_note="PROVISIONAL segmentation"):
    """Tune (Route A and/or B) and evaluate one detector for the given matching rules.

    method: detector name (registry and ``[methods.<method>]``); fixed: detector settings that are
    not tuned; fixed_refs: {name: params} evaluated untuned on all days (e.g. published values);
    title: plot title prefix; routes: tuning routes to run (Route B always includes the
    all-participant set); plot_note: Bland-Altman title note. Writes the per-rule file set to ``out``.
    """
    tag_extra = tag_extra or {}
    fixed = fixed or {}
    fixed_refs = fixed_refs or {}
    title_prefix = title or method
    det_mod = detectors.get(method)
    mcfg = cfg["methods"][method]
    beta = cfg["tuning"]["beta"]
    for sub in ["params", "plots"]:
        (out / sub).mkdir(parents=True, exist_ok=True)

    cohort = build_cohort(cfg)
    days, parts = cohort.days, cohort.participants
    scored = days.scored.to_numpy()
    grid, gdet = T.grid_detections(cohort, cfg, det_mod, mcfg["sampling_min"])
    gdet, _ = T.apply_adjacent(cohort, cfg, gdet, mcfg["sampling_min"])
    axes = det_mod.grid_axes(cfg)
    split = T.route_a_split(cohort, cfg)
    folds = T.route_b_folds(cohort, cfg)
    others = other_meals(cohort)

    sp = days[["subject", "group", "date"]].copy()
    sp["route_a"] = split
    sp["route_b_fold"] = sp.subject.map(folds)
    sp.to_csv(out / "splits.csv")

    summaries, dets, meals_all, pairs_all, agree = [], [], [], [], []
    for rule in rules:
        counts = T.grid_day_counts(cohort, cfg, rule, gdet)
        runs = {}

        # Route A: per participant, tune on validation days, test on the rest
        if "A" in routes:
            rec, assign_idx = {}, {}
            for s in parts.subject:
                vmask = ((days.subject == s) & (split == "validation")).to_numpy()
                gi, tied, st = T.select(counts, vmask, scored, beta)
                rec[s] = params_record(grid, gi, tied, axes, st)
                for d in days.index[(days.subject == s) & (split == "test")]:
                    assign_idx[d] = gi
            runs["A"] = (rec, assign_idx)

        # Route B: participant-level 5-fold CV, one global set per fold
        if "B" in routes:
            rec, assign_idx = {}, {}
            for k in sorted(folds.unique()):
                train = ~days.subject.map(folds).eq(k).to_numpy()
                gi, tied, st = T.select(counts, train, scored, beta)
                held = sorted(folds.index[folds == k])
                rec[f"fold_{k}"] = params_record(grid, gi, tied, axes, st) | {"test_participants": held}
                for d in days.index[days.subject.isin(held)]:
                    assign_idx[d] = gi
            gi, tied, st = T.select(counts, np.ones(len(days), bool), scored, beta)
            rec["all_participants"] = params_record(grid, gi, tied, axes, st) | {
                "note": "tuned on all 42 participants; candidate lock for AI-READI; no held-out score"}
            runs["B"] = (rec, assign_idx)

        # untuned reference parameter sets (e.g. published values), all days
        for name, p in fixed_refs.items():
            gref = grid.index(p)
            runs[name] = (None, {d: gref for d in days.index})

        for route, (rec, assign_idx) in runs.items():
            assign = {d: grid[gi] for d, gi in assign_idx.items()}
            det, meals, edays = evaluate(cohort, cfg, rule, det_mod, fixed, assign, method)
            check_counts(det, meals, counts, days.index, assign_idx)
            det = flag_near_other(det, others)
            tag = dict(**tag_extra, route=route, rule=rule)
            summaries.append(M.summary_table(det, meals, edays, cfg, tag))
            dets.append(det.assign(**tag))
            meals_all.append(meals.assign(**tag))
            pairs = M.feature_pairs(det, cohort, cfg["features"], cfg.get("excursion"))
            pairs_all.append(pairs.assign(**tag))
            agree.append(M.agreement_table(pairs, tag))
            if route not in fixed_refs:
                title = f"{title_prefix}, Route {route}, {rule} rule"
                if tag_extra:
                    title += ", " + ", ".join(map(str, tag_extra.values()))
                M.bland_altman_plot(pairs, title, out / "plots" / f"bland_altman_route{route}_{rule}.png",
                                    note=plot_note)
                with open(out / "params" / f"chosen_params_route{route}_{rule}.json", "w") as f:
                    json.dump(rec, f, indent=1, default=float)

    summary = pd.concat(summaries, ignore_index=True)
    summary.round(4).to_csv(out / "summary.csv", index=False)
    for route in routes:
        summary[summary.route == route].round(4).to_csv(out / f"summary_route{route}.csv", index=False)
    det = pd.concat(dets, ignore_index=True)
    cols = [*tag_extra, "route", "rule", "subject", "group", "day_id", "detection_time", "status",
            "matched_meal_id", "matched_meal_type", "matched_meal_start", "delay_min",
            "fp_near_snack_or_dinner"]
    cols += [c for c in det.columns if c.startswith("event_")]
    cols += [c for c in ["excursion_start", "peak_time", "excursion_end"] if c in det.columns]
    det[cols].to_csv(out / "detections.csv", index=False)
    pd.concat(meals_all, ignore_index=True)[
        [*tag_extra, "route", "rule", "subject", "group", "day_id", "meal_id", "meal_type", "start", "carbs",
         "status", "detection_time", "delay_min"]].to_csv(out / "meals.csv", index=False)
    pd.concat(pairs_all, ignore_index=True).round(3).to_csv(out / "recovery_features.csv", index=False)
    pd.concat(agree, ignore_index=True).round(4).to_csv(out / "recovery_agreement.csv", index=False)

    # sample sizes
    rows = []
    for rule in rules:
        ms = S.scored_meals(cohort, cfg, rule)
        for g in ["overall"] + M.GROUPS:
            sel = (lambda x: x) if g == "overall" else (lambda x, g=g: x[x.group == g])
            rows.append(dict(rule=rule, stratum=g, participants=len(sel(parts)), days=len(sel(days)),
                             scored_days=int(sel(days).scored.sum()),
                             meals=len(sel(ms)), meals_scored=int(sel(ms).scored.sum()),
                             routeA_validation_days=int((split.loc[sel(days).index] == "validation").sum()),
                             routeA_test_days=int((split.loc[sel(days).index] == "test").sum())))
    pd.DataFrame(rows).to_csv(out / "sample_sizes.csv", index=False)
    print(summary[["route", "rule", "stratum", "TP", "FP", "FN", "sensitivity", "precision", "F2",
                   "FP_per_day", "delay_median"]].round(3).to_string())
    return summary


# ---------------------------------------------------------------- standard protocol
RULE_ROLE = {"refractory": "main", "tp_lockout": "comparison only"}
RULE_TEXT = {
    "refractory": "120-min refractory after every kept detection, applied before scoring. Label-free.",
    "tp_lockout": "120-min lockout after each TP, applied at scoring (Hochsmann 2026). Uses meal labels.",
    "meal_window_max_peak": "One detection per Lim 2026 meal window, highest peak. Label-free.",
    "baseline_return": "Merge detections until glucose returns near baseline. Label-free.",
    "excursion_end": "Merge detections until the shared excursion end. Label-free.",
}
TO_STANDARD = {"TP": "TP", "FP": "FP", "not_scored": "not_scored", "lockout": "ignored_by_tp_lockout",
               "removed_in_window": "removed_by_rule", "removed_outside_window": "removed_by_rule"}
SCORING_WINDOW = ("07:00 to lunch start + 180 min (capped at 22:00) on QC-valid days; "
                  "night 22:00-07:00 not scored")
ROUTE_META = {
    "A": dict(label="Route A: per-participant tuning on validation days, scored on test days",
              kind="tuning", evaluated_days={"column": "route_a_split", "values": ["test"]}),
    "B": dict(label="Route B: one global parameter set, 5-fold participant cross-validation",
              kind="tuning", evaluated_days="all"),
}


def protocol_config(name):
    """Shared config + method configs, with the protocol segmentation applied."""
    cfg = load_config(*detectors.config_paths(name))
    cfg["features"]["segmentation"] = cfg["protocol"]["segmentation"]
    return cfg


def protocol_dir(name, cfg):
    """methods/<folder>/results/<results_dir>/, or .../results/<name>/<results_dir>/ when the
    folder holds several detectors."""
    res = REPO / "methods" / detectors.folder(name) / "results"
    if detectors.folder(name) != name:
        res = res / name
    return res / cfg["protocol"]["results_dir"]


def rule_plan(cfg):
    """[(adjacent rule, [matching rules])], main rule first."""
    pc = cfg["protocol"]
    extra = pc.get("extra_matching_rules", {})
    return [(r, [pc["matching_rule"], *extra.get(r, [])]) for r in pc["adjacent_rules"]]


def rule_role(rule, cfg):
    return "main" if rule == cfg["protocol"]["adjacent_rules"][0] else RULE_ROLE.get(rule, "comparison only")


def run_protocol(name, out=None, cfg=None, compare=True):
    """Standard protocol run of one registered detector. Returns the output folder.

    cfg: a modified protocol config for a variant run (default ``protocol_config(name)``);
    compare: also rewrite results/method_comparison.md (off for variant runs)."""
    cfg = cfg or protocol_config(name)
    out = out or protocol_dir(name, cfg)
    out.mkdir(parents=True, exist_ok=True)
    about = cfg["methods"][name].get("about", {})
    title = about.get("title", name)
    routes = tuple(cfg["protocol"]["routes"])
    seg = cfg["protocol"]["segmentation"]
    for rule, mrules in rule_plan(cfg):
        rcfg = copy.deepcopy(cfg)
        rcfg["scoring"]["adjacent_rule"] = rule
        run_method(rcfg, name, out / rule, rules=mrules, tag_extra={"adjacent_rule": rule},
                   fixed=detectors.fixed_params(name, cfg), title=title, routes=routes,
                   plot_note=f"{seg} segmentation")
    summarise(cfg, out)
    meta = dict(method=name, title=title, date=date.today().isoformat(),
                results_dir=cfg["protocol"]["results_dir"], main_rule=cfg["protocol"]["adjacent_rules"][0],
                adjacent_rules=cfg["protocol"]["adjacent_rules"], routes=list(routes),
                matching_rule=cfg["protocol"]["matching_rule"],
                extra_matching_rules=cfg["protocol"].get("extra_matching_rules", {}),
                segmentation=seg, **({"comparison_note": about["comparison_note"]}
                                     if about.get("comparison_note") else {}),
                configs=[str(p.relative_to(REPO)) for p in [CONFIG_PATH, *detectors.config_paths(name)]])
    (out / "protocol.json").write_text(json.dumps(meta, indent=1) + "\n")
    export_standard(name, cfg, out)
    finish(name, cfg, out, compare)
    return out


def finish(name, cfg, out, compare=True):
    """Documentation steps (also run by --docs-only): method README and the method comparison."""
    from . import method_comparison, protocol_readme
    protocol_readme.write(name, cfg, out)
    if compare:
        method_comparison.write(cfg)


def summarise(cfg, out):
    """comparison.csv (all rules, matching rules, strata) and detection_counts.csv."""
    order = {r: i for i, (r, _) in enumerate(rule_plan(cfg))}
    allsum = pd.concat([pd.read_csv(out / r / "summary.csv") for r in order], ignore_index=True)
    allsum = allsum.sort_values(["route", "rule", "adjacent_rule"],
                                key=lambda c: c.map(order) if c.name == "adjacent_rule" else c,
                                kind="stable")
    cols = ["adjacent_rule", "route", "rule", "stratum", "participants", "days"] + \
        [c for c in allsum.columns if any(c.startswith(k) for k in R.KEYS)] + ["lockout_ignored"]
    allsum[cols].round(4).to_csv(out / "comparison.csv", index=False)
    rows = []
    for rule, mrules in rule_plan(cfg):
        det = pd.read_csv(out / rule / "detections.csv")
        for mr in mrules:
            rows += [dict(r, rule=mr) for r in R.detection_counts(det[det.rule == mr], rule)]
    counts = pd.DataFrame(rows).drop(columns="kept_06_to_07_not_scored")
    counts.insert(2, "rule", counts.pop("rule"))
    counts.to_csv(out / "detection_counts.csv", index=False)


def _split_of(tab, splits):
    sp = splits.set_index("day_id")
    ra = tab.day_id.map(sp.route_a)
    rb = "cv-fold" + tab.day_id.map(sp.route_b_fold).astype("Int64").astype(str)
    return np.select([tab.route == "A", tab.route == "B"], [ra, rb], "all")


def export_standard(name, cfg, out):
    """Standard result format (common/docs/result_format.md), one run per rule and matching rule,
    in ``out/standard/<run>/``. Each run is checked against the saved summary.csv."""
    from common.export import result_format as RF

    days = RF.cohort_days(cfg)
    rd = cfg["protocol"]["results_dir"]
    title = cfg["methods"][name].get("about", {}).get("title", name)
    for rule, mrules in rule_plan(cfg):
        src = out / rule
        det_all = pd.read_csv(src / "detections.csv")
        meals_all = pd.read_csv(src / "meals.csv")
        splits = pd.read_csv(src / "splits.csv")
        summ = pd.read_csv(src / "summary.csv")
        for mr in mrules:
            det = det_all[det_all.rule == mr]
            meals = meals_all[meals_all.rule == mr]
            d = pd.DataFrame({
                "participant": det.subject, "detection_time": det.detection_time, "route": det.route,
                "split": _split_of(det, splits), "status": det.status.map(TO_STANDARD),
                "status_original": det.status, "matched_meal_time": det.matched_meal_start,
                "delay_min": det.delay_min, "group": det.group, "day_id": det.day_id,
                "matched_meal_type": det.matched_meal_type,
                "fp_near_snack_or_dinner": det.fp_near_snack_or_dinner})
            for c in ["excursion_start", "peak_time", "excursion_end"]:   # optional standard columns
                if c in det.columns:
                    d[c] = det[c].to_numpy()
            assert d.status.notna().all(), f"unmapped status {set(det.status) - set(TO_STANDARD)}"
            m = pd.DataFrame({
                "participant": meals.subject, "meal_time": meals.start, "meal_type": meals.meal_type,
                "carbs": meals.carbs, "scored": meals.status != "not_scored", "outcome": meals.status,
                "route": meals.route, "split": _split_of(meals, splits),
                "detection_time": meals.detection_time, "delay_min": meals.delay_min,
                "meal_id": meals.meal_id, "group": meals.group, "day_id": meals.day_id})
            routes = {r: ROUTE_META[r] | {"parameters_file": str((src / "params" / f"chosen_params_route{r}_{mr}.json")
                                                                 .relative_to(REPO))}
                      for r in sorted(det.route.unique())}
            rc = cfg["scoring"]["rules"][mr]
            role = rule_role(rule, cfg)
            run = f"{rd}_{rule}_{mr}" if detectors.folder(name) == name else f"{name}_{rd}_{rule}_{mr}"
            meta = dict(
                method=detectors.folder(name), run=run, title=f"{title} | {rule} ({role}) | {mr} rule | {rd}",
                description=f"Standard protocol {rd}, {role}: {RULE_TEXT.get(rule, rule)}",
                date=json.loads((out / "protocol.json").read_text())["date"],
                source=str(src.relative_to(REPO)), routes=routes, adjacent_rule=rule,
                adjacent_rule_uses_labels=rule == "tp_lockout",
                matching_rule=dict(name=mr, tp_before_min=rc["tp_before_min"], tp_after_min=rc["tp_after_min"]),
                scoring_window=SCORING_WINDOW,
                parameters_file=", ".join(str(p.relative_to(REPO)) for p in detectors.config_paths(name)),
                available=dict(detections=True, meals=True, days=True),
                comparable=True, comparability_note="")
            run_dir = RF.write_run(out / "standard" / run, meta, d, m, days)
            # every participant in the cohort, also those without any detection
            ps = RF.participant_summary(RF.read_run(run_dir), participants=sorted(m.participant.unique()))
            for route, g in ps.groupby("route"):
                r = summ[(summ.rule == mr) & (summ.route == route) & (summ.stratum == "overall")].iloc[0]
                got = (int(g.TP.sum()), int(g.FP.sum()), int(g.FN.sum()), int(g.scored_days.sum()))
                exp = (int(r.TP), int(r.FP), int(r.FN), int(r.days))
                assert got == exp, f"standard export {run} route {route}: {got} != saved {exp}"
            print(f"standard export ok: {run_dir.relative_to(REPO)}")
