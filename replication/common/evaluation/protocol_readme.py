"""Standard method README for a protocol run (plain ASCII), built from the saved outputs only.

Layout: summary; method, sampling and parameters; grid with source and boundary hits; detection
(main rule first); by group; by meal; recovery agreement (recovery time first); locked
all_participants parameters; comparison with Hochsmann 2026 Table 2; deviations; files; run.
"""
import json

import numpy as np
import pandas as pd

from . import detectors
from . import protocol as PROT
from .report import GROUPS, fmt, md_table, write_ascii

FEATURE_LABELS = {"recovery_time_min": "Recovery time", "peak_height": "Peak height",
                  "iauc": "iAUC", "peak_time_min": "Peak time"}
FEATURES = list(FEATURE_LABELS)


def _num(v):
    return f"{v:g}" if isinstance(v, float) else str(v)


def load(cfg, out):
    """Saved outputs: summaries, agreement and params per (adjacent rule, matching rule)."""
    route = cfg["protocol"]["routes"][0]
    runs = []
    for rule, mrules in PROT.rule_plan(cfg):
        summ = pd.read_csv(out / rule / "summary.csv")
        agr = pd.read_csv(out / rule / "recovery_agreement.csv")
        for mr in mrules:
            s = summ[(summ.rule == mr) & (summ.route == route)].set_index("stratum")
            a = agr[(agr.rule == mr) & (agr.route == route)]
            p = json.loads((out / rule / "params" / f"chosen_params_route{route}_{mr}.json").read_text())
            role = PROT.rule_role(rule, cfg)
            runs.append(dict(rule=rule, mr=mr, role=role, s=s, a=a, p=p,
                             label=f"{rule}, {mr} ({role})"))
    return route, runs


def caption(route, s):
    o = s.loc["overall"]
    test = ("test data (5 held-out folds pooled)" if route == "B"
            else "test data (per-participant test days)")
    return f"Route {route}, {test}, {int(o.participants)} participants, {int(o.days)} scored days."


def group_line(s):
    return "Groups: " + ", ".join(f"{g} {int(s.loc[g].participants)}" for g in GROUPS) + " participants."


def write(name, cfg, out):
    about = cfg["methods"][name].get("about", {})
    mcfg = cfg["methods"][name]
    title = about.get("title", name)
    meta = json.loads((out / "protocol.json").read_text())
    route, runs = load(cfg, out)
    main = runs[0]
    s0, a0 = main["s"], main["a"]
    rd = cfg["protocol"]["results_dir"]
    mrc = cfg["scoring"]["rules"][cfg["protocol"]["matching_rule"]]
    match_txt = f"-{mrc['tp_before_min']} to +{mrc['tp_after_min']} min"
    cap = caption(route, s0)
    ci = " 95 % participant-bootstrap CI in brackets."
    axes = detectors.get(name).grid_axes(cfg)
    labels = about.get("param_labels", {})

    def short(k):
        return labels.get(k, k).split(" (")[0]

    def icc(a, f, stratum="overall"):
        x = a[(a.stratum == stratum) & (a.feature == f)]
        return x.iloc[0] if len(x) else None

    L = [f"# {title}: standard protocol ({rd})", ""]

    # ------------------------------------------------ summary
    o = s0.loc["overall"]
    rt = icc(a0, "recovery_time_min")
    lk = [r for r in runs if r["rule"] == "tp_lockout" and r["mr"] == cfg["protocol"]["matching_rule"]]
    allp = main["p"]["all_participants"]
    L += ["## Summary", "",
          f"- {title} on CGMacros (Dexcom, {int(o.participants)} participants). "
          f"Standard protocol ({rd}), run on {meta['date']}.",
          f"- Main adjacent rule: {main['rule']}. Route {route} only. "
          f"Matching window {match_txt} around the logged meal start. "
          "Why refractory: common/docs/deviations.md Z1.",
          f"- Main result, Route {route}: Sens {fmt(o, 'sensitivity')} %, Prec {fmt(o, 'precision')} %, "
          f"F2 {fmt(o, 'F2')}, FP/day {fmt(o, 'FP_per_day')}, delay median {fmt(o, 'delay_median')} min.",
          f"- Recovery-time ICC(A,1), main rule: {rt.ICC_A1:.2f} (n = {int(rt.n)} TP pairs; "
          f"{meta['segmentation']} segmentation)."]
    if lk:
        x = lk[0]["s"].loc["overall"]
        L.append(f"- tp_lockout (comparison only, uses meal labels): Sens {fmt(x, 'sensitivity')} %, "
                 f"Prec {fmt(x, 'precision')} %, FP/day {fmt(x, 'FP_per_day')}.")
    fixed_axes = {k for k, v in axes.items() if len(v) == 1}            # not tuned: no edge to report
    forced = [short(e) for e in allp["grid_edges_forced"] if e not in fixed_axes]
    L.append("- Locked all_participants set, main rule: "
             + ", ".join(f"{short(k)} {_num(v)}" for k, v in allp["params"].items())
             + (f". Forced grid edges: {', '.join(forced)}." if forced else ". No forced grid edge."))
    L.append("")

    # ------------------------------------------------ method
    L += ["## Method, sampling and parameters", ""]
    if about.get("paper"):
        L.append(f"- Source: {about['paper']}")
    if about.get("implementation"):
        L.append(f"- Implementation: {about['implementation']}")
    L += [f"- {line}" for line in about.get("description", [])]
    if mcfg["sampling_min"] == 5:
        L.append("- Sampling: 5-min CGM input (native Dexcom readings for 5 min; "
                 "see common/docs/deviations.md E1).")
    else:
        L.append(f"- Sampling: {mcfg['sampling_min']}-min CGM input (QC'd 1-min series, plan 2.2; "
                 "Dexcom readings linearly interpolated to 1 min).")
    fixed = detectors.fixed_params(name, cfg)
    if fixed:
        L.append("- Fixed settings (not tuned): " + ", ".join(f"{k} = {_num(v)}" for k, v in fixed.items()) + ".")
    L.append("- Tuned parameters: " + ", ".join(labels.get(k, k) for k in axes) + ".")
    L.append(f"- Tuning: F2 (beta = {cfg['tuning']['beta']}). Ties: higher F2, then lower FP/day, "
             "then shorter mean delay, then grid order.")
    L.append(f"- Route {route}: 5 participant folds stratified by group. Each fold is tuned on the other "
             "4 and scored on its held-out participants. An all_participants set is also tuned once on everyone.")
    L.append("")

    # ------------------------------------------------ grid
    n_grid = 1
    for v in axes.values():
        n_grid *= len(v)
    L += ["## Grid", "",
          f"Source: {about.get('grid_source', 'method config')}. {n_grid:,} grid points. "
          f"Edge hits count the {len(main['p'])} Route {route} sets (5 folds and all_participants) "
          "on the lower or upper grid bound.", ""]
    grid_rules = [r for r in runs if r["mr"] == cfg["protocol"]["matching_rule"]]
    hdr = ["Parameter", "Values", "n"] + [f"Edge hits, {r['rule']} ({r['role']})" for r in grid_rules]
    rows = []
    for k, ax in axes.items():
        step = ax[1] - ax[0] if len(ax) > 1 else 0
        if len(ax) == 1:                                                 # fixed value
            vals = _num(float(ax[0]))
        elif len(ax) > 2 and not np.allclose(np.diff(ax), step):        # explicit, uneven values
            vals = ", ".join(_num(float(v)) for v in ax)
        else:
            vals = f"{_num(float(ax[0]))} to {_num(float(ax[-1]))}, step {_num(round(float(step), 6))}"
        cells = [labels.get(k, k), vals, str(len(ax))]
        for r in grid_rules:
            vals = [v["params"][k] for v in r["p"].values()]
            lo = sum(abs(v - ax[0]) < 1e-9 for v in vals)
            hi = sum(abs(v - ax[-1]) < 1e-9 for v in vals)
            cells.append("fixed (not tuned)" if len(ax) == 1 else f"low {lo}/{len(vals)}, high {hi}/{len(vals)}")
        rows.append(cells)
    L += md_table(pd.DataFrame(rows), hdr)
    L += ["", "A parameter on a grid bound may mean the best value lies outside the grid. "
          "Forced edges (shared by every tied grid point) are listed with the locked parameters.", ""]

    # ------------------------------------------------ detection
    L += ["## Detection", "", cap + ci, ""]
    rows = []
    for r in runs:
        x = r["s"].loc["overall"]
        rows.append([r["label"]] + [fmt(x, k) for k in
                                    ["sensitivity", "precision", "F2", "FP_per_day", "delay_median"]])
    L += md_table(pd.DataFrame(rows), ["Rule", "Sens %", "Prec %", "F2", "FP/day", "Delay median (min)"])
    L += ["", "Rules:", ""]
    for rule, _ in PROT.rule_plan(cfg):
        L.append(f"- {rule} ({PROT.rule_role(rule, cfg)}): {PROT.RULE_TEXT.get(rule, rule)}")
    L += ["- Matching rules: ours = " + match_txt + "; review = 0 to +120 min (Hochsmann 2026).", ""]

    # ------------------------------------------------ by group
    L += ["## By group", ""]
    for k, lab, unit in [("sensitivity", "Sensitivity (%)", "pp"), ("precision", "Precision (%)", "pp"),
                         ("FP_per_day", "FP/day", "per day")]:
        L += [f"#### {lab} by group", "", f"{cap} {group_line(s0)} Range = max minus min ({unit}).", ""]
        rows = []
        for r in runs:
            xs = [r["s"].loc[g] for g in GROUPS]
            vals = [x[k] for x in xs]
            rng = max(vals) - min(vals)
            rng = f"{100 * rng:.1f}" if k != "FP_per_day" else f"{rng:.2f}"
            rows.append([r["label"]] + [fmt(x, k) for x in xs] + [rng])
        L += md_table(pd.DataFrame(rows), ["Rule", "Healthy", "Prediabetes", "T2D", "Range"])
        L.append("")

    # ------------------------------------------------ by meal
    L += ["## By meal", "", cap + " FP cannot be assigned to a meal, so only Sens and delay.", ""]
    rows = []
    for r in runs:
        b, l_ = r["s"].loc["breakfast"], r["s"].loc["lunch"]
        rows.append([r["label"], fmt(b, "sensitivity"), fmt(b, "delay_median"),
                     fmt(l_, "sensitivity"), fmt(l_, "delay_median")])
    L += md_table(pd.DataFrame(rows), ["Rule", "Sens % breakfast", "Delay median breakfast",
                                       "Sens % lunch", "Delay median lunch"])
    L.append("")

    # ------------------------------------------------ recovery
    L += ["## Recovery agreement", "",
          f"Segmentation: {meta['segmentation']} (frozen definition, common/docs/deviations.md section X). "
          "Detector anchor = detection time; reference anchor = logged meal start.", "",
          "#### ICC(A,1) by feature", "",
          f"{cap} n = TP pairs with complete data; recovery time leaves out pairs with no_rise at either anchor.", ""]
    rows = []
    for r in runs:
        a = r["a"]
        x = {f: icc(a, f) for f in FEATURES}
        rows.append([r["label"], int(x["peak_height"].n), int(x["recovery_time_min"].n)]
                    + [f"{x[f].ICC_A1:.2f}" for f in FEATURES])
    L += md_table(pd.DataFrame(rows), ["Rule", "n pairs", "n (recovery time)"] + [FEATURE_LABELS[f] for f in FEATURES])
    L += ["", f"#### Recovery time by stratum, {main['rule']} (main)", "",
          f"{cap} n = TP pairs used. Bias = detector minus reference (min).", ""]
    rows = []
    for st in ["overall", *GROUPS, "breakfast", "lunch"]:
        x = icc(a0, "recovery_time_min", st)
        if x is None or not x.n:
            continue
        rows.append([st, int(x.n), f"{x.ICC_A1:.2f}", f"{x.BA_bias:.0f}",
                     f"{x.BA_loa_low:.0f} to {x.BA_loa_high:.0f}"])
    L += md_table(pd.DataFrame(rows), ["Stratum", "n", "ICC", "Bias (min)", "95 % LoA (min)"])
    L.append("")

    # ------------------------------------------------ locked params
    L += ["## Locked parameters (all_participants)", "",
          f"Route {route}, tuned once on all {int(o.participants)} participants. "
          "Candidate lock for AI-READI. No held-out score.", ""]
    rows = []
    for r in runs:
        p = r["p"]["all_participants"]
        rows.append([r["label"]] + [_num(p["params"][k]) for k in axes]
                    + [", ".join(short(e) for e in p["grid_edges_forced"] if e not in fixed_axes) or "none"])
    L += md_table(pd.DataFrame(rows), ["Rule"] + [short(k) for k in axes] + ["Forced grid edges"])
    L += ["", f"Fold sets: `<rule>/params/chosen_params_route{route}_<matching rule>.json`.", ""]
    t1 = about.get("hochsmann2026_table1")
    if t1:
        L += ["Hochsmann 2026 Table 1 (tuned per participant, mean +/- SD; their cohort): "
              + ", ".join(f"{short(k) if k in axes else k} {v}" for k, v in t1.items()) + ".", ""]

    # ------------------------------------------------ Hochsmann
    L += ["## Comparison with Hochsmann 2026 Table 2 (not like-for-like)", ""]
    h = about.get("hochsmann2026_table2")
    if h:
        L += [f"Hochsmann 2026 cohort: {h['cohort']}. Ours: CGMacros, Route {route}, test data. "
              "Delay is the mean, as in Table 2.", ""]
        rows = [["Hochsmann 2026 Table 2", "tp_lockout, review", f"{h['sensitivity_pct']:.1f}",
                 f"{h['fp_per_day']:.2f}", f"{h['delay_mean_min']:.1f}"]]
        for r in sorted(runs, key=lambda r: (r["rule"] != "tp_lockout", r["mr"] != "review")):
            x = r["s"].loc["overall"]
            rows.append([f"CGMacros, Route {route}", r["label"], fmt(x, "sensitivity"), fmt(x, "FP_per_day"),
                         fmt(x, "delay_mean")])
        L += md_table(pd.DataFrame(rows), ["Data", "Rule", "Sens %", "FP/day", "Delay mean (min)"])
        L += ["", "The closest row is tp_lockout with the review matching rule. Differences remain: "
              "cohort, sensor, meals scored (breakfast and lunch here), scoring window "
              "(07:00 to lunch + 180 min here) and tuning (per participant in the review; one global set "
              f"in Route {route}).", ""]
    else:
        L += ["Not reported for this method in Hochsmann 2026 Table 2.", ""]
    orig = about.get("original")
    if orig:
        L += [f"Original paper ({orig.get('note', 'its own cohort and evaluation')}): "
              + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in orig.items() if k != "note") + ".", ""]

    # ------------------------------------------------ deviations, files, run
    L += ["## Deviations", ""]
    if about.get("deviations"):
        L.append(f"- Method: `{about['deviations']}`.")
    L += ["- Framework: `common/docs/deviations.md` (protocol decisions: section Z).", "",
          "## Files", ""]
    L += md_table(pd.DataFrame([
        ["`comparison.csv`", "All rules and matching rules, all strata, 95 % CI"],
        ["`detection_counts.csv`", "Raw detections, removed by the rule, ignored by the TP lockout, kept and scored"],
        ["`<rule>/summary.csv`, `recovery_agreement.csv`, `params/`, `plots/`", "Per-rule outputs"],
        ["`<rule>/detections.csv`, `meals.csv`, `recovery_features.csv`", "Row-level, not committed"],
        ["`standard/<run>/`", "Standard-format export for the dashboard, not committed"],
        ["`protocol.json`", "Protocol settings of this run"],
    ]), ["File", "Content"])
    L += ["", "## Run", "", "From `replication/`:", "", "```",
          f"python common/run_protocol.py {name}",
          f"python common/run_protocol.py {name} --docs-only", "```", "",
          "The first runs the full protocol and also rewrites `results/method_comparison.md`. "
          "The second rebuilds this README and the comparison from the saved outputs."]
    write_ascii(out / "README.md", "\n".join(L) + "\n")
