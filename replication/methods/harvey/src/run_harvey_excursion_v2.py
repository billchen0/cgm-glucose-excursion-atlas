"""Harvey (GRID) with the shared excursion definition (2026-10-01).

Runs tp_lockout, meal_window_max_peak, refractory and the new excursion_end rule (our matching
rule, Route A and B) with ``[features] segmentation = "excursion"``. Detection metrics of the
three earlier rules must equal methods/harvey/results/peak_rules/ (checked; the run stops if not).
Earlier outputs are read, never written.

Usage: python methods/harvey/src/run_harvey_excursion_v2.py
Outputs: methods/harvey/results/excursion_v2/ (see its README.md).
"""
import copy
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_harvey  # noqa: E402
import run_harvey_peak_rules as PR  # noqa: E402
from common.evaluation import load_config  # noqa: E402
from common.evaluation import metrics as M  # noqa: E402
from common.evaluation.data import build_cohort  # noqa: E402

OUT = run_harvey.HARVEY / "results" / "excursion_v2"
PEAK = run_harvey.HARVEY / "results" / "peak_rules"
REF = run_harvey.OUT
RULES = ["tp_lockout", "meal_window_max_peak", "refractory", "excursion_end"]
GROUPS = PR.GROUPS
END_TYPES = ["returned", "trough", "trough_interrupted", "censored", "no_rise"]
DET_COLS = ["TP", "FP", "FN", "sensitivity", "precision", "F2", "FP_per_day", "FP_per_hour",
            "delay_median", "delay_mean"]


def regression(allsum):
    """Detection metrics of the earlier rules must equal the peak_rules/ run."""
    old = pd.read_csv(PEAK / "comparison.csv")
    cols = [c for c in old.columns if any(c.startswith(k) for k in DET_COLS)]
    key = ["adjacent_rule", "route", "stratum"]
    new = allsum[allsum.adjacent_rule.isin(RULES[:3])][key + cols].round(4)
    old = old[old.adjacent_rule.isin(RULES[:3])][key + cols]
    m = new.merge(old, on=key, suffixes=("_new", "_old"), validate="one_to_one")
    assert len(m) == len(old) == len(new), (len(m), len(old), len(new))
    bad = [(r[key].tolist(), c) for _, r in m.iterrows() for c in cols
           if not (pd.isna(r[f"{c}_new"]) and pd.isna(r[f"{c}_old"]))
           and not np.isclose(r[f"{c}_new"], r[f"{c}_old"], rtol=0, atol=1e-9)]
    if bad:
        raise SystemExit(f"STOP: detection metrics differ from peak_rules/: {bad[:10]}")
    return len(m), len(cols)


def provisional_agreement(cfg):
    """Provisional recovery agreement per rule: earlier files, and recomputed for excursion_end."""
    out = {"tp_lockout": pd.read_csv(REF / "recovery_agreement.csv").query("rule == 'ours'"),
           "meal_window_max_peak": pd.read_csv(PEAK / "meal_window_max_peak" / "recovery_agreement.csv"),
           "refractory": pd.read_csv(PEAK / "refractory" / "recovery_agreement.csv")}
    cohort = build_cohort(cfg)
    det = pd.read_csv(OUT / "excursion_end" / "detections.csv",
                      parse_dates=["detection_time", "matched_meal_start"])
    fprov = {**cfg["features"], "segmentation": "provisional"}
    agr = []
    for route, d in det.groupby("route"):
        pairs = M.feature_pairs(d, cohort, fprov)
        agr.append(M.agreement_table(pairs, dict(adjacent_rule="excursion_end", route=route, rule="ours")))
    out["excursion_end"] = pd.concat(agr, ignore_index=True)
    out["excursion_end"].round(4).to_csv(OUT / "excursion_end" / "recovery_agreement_provisional.csv",
                                         index=False)
    return out


def end_types(feats):
    rows = []
    for (rule, route), f in feats.groupby(["adjacent_rule", "route"], sort=False):
        f = f[f.featurised]
        for anchor in ["det", "ref"]:
            for g in ["overall"] + GROUPS:
                x = f if g == "overall" else f[f.group == g]
                vc = x[f"end_type_{anchor}"].value_counts()
                rows.append(dict(adjacent_rule=rule, route=route, anchor=anchor, group=g, n=len(x),
                                 **{f"{t}_pct": round(100 * vc.get(t, 0) / len(x), 1) for t in END_TYPES}))
    return pd.DataFrame(rows)


def no_rise_exclusions(feats):
    """Pairs left out of the recovery-time ICC (overall stratum)."""
    rows = []
    for (rule, route), f in feats.groupby(["adjacent_rule", "route"], sort=False):
        f = f[f.featurised]
        nd, nr = f.end_type_det == "no_rise", f.end_type_ref == "no_rise"
        rows.append(dict(adjacent_rule=rule, route=route, pairs=len(f), no_rise_det=int(nd.sum()),
                         no_rise_ref=int(nr.sum()), excluded_either=int((nd | nr).sum()),
                         used=int((~(nd | nr)).sum())))
    return pd.DataFrame(rows)


def recovery_by_end_type(feats):
    rows = []
    for (rule, route), f in feats.groupby(["adjacent_rule", "route"], sort=False):
        f = f[f.featurised]
        for anchor in ["det", "ref"]:
            for g in ["overall"] + GROUPS:
                x = f if g == "overall" else f[f.group == g]
                for t in END_TYPES:
                    y = x.loc[x[f"end_type_{anchor}"] == t, f"recovery_time_min_{anchor}"]
                    q = y.quantile([0.25, 0.5, 0.75]) if len(y) else pd.Series([np.nan] * 3, [0.25, 0.5, 0.75])
                    rows.append(dict(adjacent_rule=rule, route=route, anchor=anchor, group=g,
                                     end_type=t, n=len(y), median=q[0.5], q1=q[0.25], q3=q[0.75]))
    return pd.DataFrame(rows)


def merge_by_group(det):
    rows = []
    for route, d in det.groupby("route"):
        for g in ["overall"] + GROUPS:
            x = d if g == "overall" else d[d.group == g]
            anchors = x[x.detection_time == x.event_anchor]
            rows.append(dict(route=route, group=g, raw_detections=len(x),
                             merged_pct=round(100 * x.status.str.startswith("removed").sum() / len(x), 1),
                             events=len(anchors),
                             **{f"events_{t}_pct": round(100 * (anchors.event_end_type == t).mean(), 1)
                                for t in END_TYPES}))
    return pd.DataFrame(rows)


def main():
    base = load_config(run_harvey.HARVEY_CONFIG)
    OUT.mkdir(parents=True, exist_ok=True)
    for rule in RULES:
        cfg = copy.deepcopy(base)
        cfg["scoring"]["adjacent_rule"] = rule
        cfg["features"]["segmentation"] = "excursion"
        run_harvey.run(cfg, out=OUT / rule, rules=["ours"], tag_extra={"adjacent_rule": rule},
                       reference_fixed=False)

    order = {r: i for i, r in enumerate(RULES)}
    allsum = pd.concat([pd.read_csv(OUT / r / "summary.csv") for r in RULES], ignore_index=True)
    allsum = allsum.sort_values(["route", "stratum", "adjacent_rule"],
                                key=lambda c: c.map(order) if c.name == "adjacent_rule" else c,
                                kind="stable")
    n_rows, n_cols = regression(allsum)
    print(f"regression ok: {n_rows} rows x {n_cols} detection columns equal peak_rules/")
    cols = ["adjacent_rule", "route", "rule", "stratum", "participants", "days"] + \
        [c for c in allsum.columns if any(c.startswith(k) for k in PR.KEYS)] + ["lockout_ignored"]
    allsum[cols].round(4).to_csv(OUT / "comparison.csv", index=False)

    dets = {r: pd.read_csv(OUT / r / "detections.csv") for r in RULES}
    counts = pd.DataFrame([row for r in RULES for row in PR.detection_counts(dets[r], r)])
    counts = counts.sort_values(["route", "adjacent_rule"],
                                key=lambda c: c.map(order) if c.name == "adjacent_rule" else c)
    counts.to_csv(OUT / "detection_counts.csv", index=False)

    feats = pd.concat([pd.read_csv(OUT / r / "recovery_features.csv") for r in RULES], ignore_index=True)
    et = end_types(feats)
    et.to_csv(OUT / "end_type_by_group.csv", index=False)
    exc = no_rise_exclusions(feats)
    exc.to_csv(OUT / "recovery_icc_no_rise_excluded.csv", index=False)
    rt = recovery_by_end_type(feats)
    rt.round(1).to_csv(OUT / "recovery_time_by_end_type.csv", index=False)
    mbg = merge_by_group(dets["excursion_end"])
    mbg.to_csv(OUT / "merge_by_group.csv", index=False)
    provisional_agreement(base)
    write_comparison_md()
    write_readme()


def load_provisional():
    """Provisional recovery agreement per rule, read from the saved files."""
    return {"tp_lockout": pd.read_csv(REF / "recovery_agreement.csv").query("rule == 'ours'"),
            "meal_window_max_peak": pd.read_csv(PEAK / "meal_window_max_peak" / "recovery_agreement.csv"),
            "refractory": pd.read_csv(PEAK / "refractory" / "recovery_agreement.csv"),
            "excursion_end": pd.read_csv(OUT / "excursion_end" / "recovery_agreement_provisional.csv")}


def load_outputs():
    """All saved outputs the documentation is built from (no pipeline run)."""
    o = dict(allsum=pd.read_csv(OUT / "comparison.csv"),
             counts=pd.read_csv(OUT / "detection_counts.csv"),
             et=pd.read_csv(OUT / "end_type_by_group.csv"),
             exc=pd.read_csv(OUT / "recovery_icc_no_rise_excluded.csv"),
             rt=pd.read_csv(OUT / "recovery_time_by_end_type.csv"),
             mbg=pd.read_csv(OUT / "merge_by_group.csv"),
             prov=load_provisional(),
             new={r: pd.read_csv(OUT / r / "recovery_agreement.csv") for r in RULES})
    o["by"] = {(r.route, r.adjacent_rule, r.stratum): r for _, r in o["allsum"].iterrows()}
    return o


def write_comparison_md():
    """comparison.md (tables a-h) from the saved outputs, plain ASCII."""
    o = load_outputs()
    order = {r: i for i, r in enumerate(RULES)}
    allsum, counts, et, exc, rt, mbg, prov, new, by = (o[k] for k in
        ["allsum", "counts", "et", "exc", "rt", "mbg", "prov", "new", "by"])
    fmt = PR.fmt
    L = ["## a) Overall detection", "",
         "| Route | Rule | TP | FP | FN | Sens % | Prec % | F2 | FP/day | Delay median | Delay mean |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    ka = ["TP", "FP", "FN", "sensitivity", "precision", "F2", "FP_per_day", "delay_median", "delay_mean"]
    for route in ["A", "B"]:
        for rule in RULES:
            L.append(f"| {route} | {rule} | " + " | ".join(fmt(by[(route, rule, 'overall')], k) for k in ka) + " |")
    L += ["", "## b) By glycaemic group", "",
          "| Route | Rule | " + " | ".join(f"Sens % {g}" for g in GROUPS) + " | Sens range (pp) | "
          + " | ".join(f"Prec % {g}" for g in GROUPS) + " | " + " | ".join(f"FP/day {g}" for g in GROUPS) + " |",
          "|---|---|" + "---|" * 10]
    for route in ["A", "B"]:
        for rule in RULES:
            rs = [by[(route, rule, g)] for g in GROUPS]
            rng = 100 * (max(x.sensitivity for x in rs) - min(x.sensitivity for x in rs))
            L.append(f"| {route} | {rule} | " + " | ".join(fmt(x, "sensitivity") for x in rs)
                     + f" | {rng:.1f} | " + " | ".join(fmt(x, "precision") for x in rs) + " | "
                     + " | ".join(fmt(x, "FP_per_day") for x in rs) + " |")
    L += ["", "## c) By meal", "",
          "| Route | Rule | Sens % breakfast | Delay median breakfast | Sens % lunch | Delay median lunch |",
          "|---|---|---|---|---|---|"]
    for route in ["A", "B"]:
        for rule in RULES:
            b_, l_ = by[(route, rule, "breakfast")], by[(route, rule, "lunch")]
            L.append(f"| {route} | {rule} | {fmt(b_, 'sensitivity')} | {fmt(b_, 'delay_median')} | "
                     f"{fmt(l_, 'sensitivity')} | {fmt(l_, 'delay_median')} |")
    L += ["", "## d) Recovery-feature agreement, new excursion definition vs provisional (TP pairs, overall)", "",
          "Recovery time (new) leaves out pairs where either anchor is no_rise; see the exclusion table below.", "",
          "| Route | Rule | Feature | n new | ICC new | Bias new | 95 % LoA new | n provisional | ICC provisional | Bias provisional | 95 % LoA provisional |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for route in ["A", "B"]:
        for f in PR.FEATURES:
            for rule in RULES:
                sel = lambda a: a[(a.route == route) & (a.stratum == "overall") & (a.feature == f)].iloc[0]
                x, p = sel(new[rule]), sel(prov[rule])
                assert f == "recovery_time_min" or int(x.n) == int(p.n), (rule, route, f)
                L.append(f"| {route} | {rule} | {f} | {int(x.n)} | {x.ICC_A1:.2f} | {x.BA_bias:.1f} | "
                         f"{x.BA_loa_low:.1f} to {x.BA_loa_high:.1f} | {int(p.n)} | {p.ICC_A1:.2f} | "
                         f"{p.BA_bias:.1f} | {p.BA_loa_low:.1f} to {p.BA_loa_high:.1f} |")
    L += ["", "Pairs left out of the new recovery-time ICC (no_rise at either anchor):", ""]
    L += PR.md_table(exc[["route", "adjacent_rule", "pairs", "no_rise_det", "no_rise_ref", "excluded_either",
                          "used"]].sort_values(["route", "adjacent_rule"], kind="stable",
                                               key=lambda c: c.map(order) if c.name == "adjacent_rule" else c),
                     ["Route", "Rule", "TP pairs", "no_rise det", "no_rise ref", "Excluded (either)", "Used"])
    L += ["", "## e) End type by group (TP pairs; det = detector anchor, ref = logged meal start)", ""]
    L += PR.md_table(et[["route", "adjacent_rule", "anchor", "group", "n"] + [f"{t}_pct" for t in END_TYPES]]
                     .sort_values(["route", "adjacent_rule", "anchor"], kind="stable",
                                  key=lambda c: c.map(order) if c.name == "adjacent_rule" else c),
                     ["Route", "Rule", "Anchor", "Group", "n", "% returned", "% trough",
                      "% trough_interrupted", "% censored", "% no_rise"])
    L += ["", "## f) Recovery time (min) by group and end type, excursion_end (median [IQR], n)", ""]
    x = rt[rt.adjacent_rule == "excursion_end"]
    hdr = ["Route", "Anchor", "Group"] + END_TYPES
    rows = []
    for (route, anchor, g), y in x.groupby(["route", "anchor", "group"], sort=False):
        cell = lambda r: "" if r.n == 0 else f"{r['median']:.0f} [{r.q1:.0f}, {r.q3:.0f}], {int(r.n)}"
        rows.append([route, anchor, g] + [cell(y[y.end_type == t].iloc[0]) for t in END_TYPES])
    L += PR.md_table(pd.DataFrame(rows), hdr)
    L += ["", "## g) excursion_end: merging by group", ""]
    L += PR.md_table(mbg[["route", "group", "raw_detections", "merged_pct", "events"]],
                     ["Route", "Group", "Raw detections", "% merged", "Events"])
    L += ["", "## h) Detection counts and locked parameters", ""]
    L += PR.md_table(counts[["route", "adjacent_rule", "raw_detections", "removed_by_rule",
                             "removed_in_scoring_window", "ignored_by_tp_lockout", "kept_scored_TP_FP"]],
                     ["Route", "Rule", "Raw", "Removed by rule", "Removed inside scoring window",
                      "Ignored by TP lockout", "Kept and scored (TP + FP)"])
    L += [""]
    prow = []
    for rule in RULES:
        for route in ["A", "B"]:
            prow += PR.params_rows(OUT / rule / "params" / f"chosen_params_route{route}_ours.json", rule, route)
    L += PR.md_table(pd.DataFrame(prow)[["rule", "route", "set", "tau_F", "G_min", "Gp_min_3", "Gp_min_2",
                                         "forced_edges"]],
                     ["Rule", "Route", "Set", "tau_F", "G_min", "G'_min,3", "G'_min,2", "Forced edges"])
    PR.write_ascii(OUT / "comparison.md", "\n".join(L) + "\n")



# ---------------------------------------------------------------- README (plain ASCII)
PNAME = {"tau_F": "tau_F", "G_min": "G_min", "Gp_min_3": "G'_min,3", "Gp_min_2": "G'_min,2"}
PFMT = {"tau_F": "{:.0f}", "G_min": "{:.0f}", "Gp_min_3": "{:.1f}", "Gp_min_2": "{:.1f}"}
FEAT = {"recovery_time_min": "recovery time", "peak_height": "peak height", "iauc": "iAUC",
        "peak_time_min": "peak time"}
RULE_INFO = [
    ("tp_lockout", "Ignore unmatched detections within 120 min after a TP (Hochsmann 2026).",
     "yes", "reference only"),
    ("excursion_end", "Merge detections until the shared excursion end (below).", "no", "candidate main"),
    ("refractory", "Drop detections <= 120 min after the previous kept one.", "no", "sensitivity"),
    ("meal_window_max_peak", "Keep the highest-peak detection per Lim 2026 meal window.", "no",
     "sensitivity"),
]
ORDER = ["excursion_end", "tp_lockout", "refractory", "meal_window_max_peak"]


def _ci(r, k, f):
    if pd.isna(r[k]):
        return ""
    s = f.format(r[k])
    if f"{k}_lo" in r and pd.notna(r[f"{k}_lo"]):
        s += f" [{f.format(r[f'{k}_lo'])}, {f.format(r[f'{k}_hi'])}]"
    return s


def _pct(r, k):
    return _ci(r.copy().pipe(lambda x: x.where(~x.index.str.startswith(k), x * 100)), k, "{:.1f}")


def _tbl(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return out + ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]


def _route_tables(o, route, split):
    """Section d layout for one route."""
    by, new, prov, et, rt, mbg = (o[k] for k in ["by", "new", "prov", "et", "rt", "mbg"])
    A = o["allsum"]
    days = int(A[(A.route == route) & (A.stratum == "overall")].days.iloc[0])
    cap = f"Route {route}, {split}, 42 participants, {days} scored days."
    L = ["#### Detection", "", f"{cap} 95 % participant-bootstrap CI in brackets.", ""]
    L += _tbl(["Rule", "Sens %", "Prec %", "F2", "FP/day", "Delay median (min)"],
              [[r, _pct(by[(route, r, "overall")], "sensitivity"), _pct(by[(route, r, "overall")], "precision"),
                _ci(by[(route, r, "overall")], "F2", "{:.3f}"), _ci(by[(route, r, "overall")], "FP_per_day", "{:.2f}"),
                _ci(by[(route, r, "overall")], "delay_median", "{:.0f}")] for r in ORDER])
    for k, name, unit, f in [("sensitivity", "Sensitivity (%)", "pp", None), ("precision", "Precision (%)", "pp", None),
                             ("FP_per_day", "FP/day", "per day", "{:.2f}")]:
        rows = []
        for r in ORDER:
            xs = [by[(route, r, g)] for g in GROUPS]
            vals = [x[k] * (100 if f is None else 1) for x in xs]
            cells = [_pct(x, k) if f is None else _ci(x, k, f) for x in xs]
            rng = max(vals) - min(vals)
            rows.append([r] + cells + [f"{rng:.1f}" if f is None else f"{rng:.2f}"])
        L += ["", f"#### {name} by group", "",
              f"{cap} Healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min ({unit}).", ""]
        L += _tbl(["Rule", "Healthy", "Prediabetes", "T2D", "Range"], rows)
    sel = lambda a, f, st="overall": a[(a.route == route) & (a.stratum == st) & (a.feature == f)].iloc[0]
    L += ["", "#### Recovery agreement, ICC(A,1) (new definition)", "",
          f"{cap} n = TP pairs; recovery time leaves out pairs with no_rise at either anchor.", ""]
    L += _tbl(["Rule", "n pairs", "n (recovery time)", "Recovery time", "Peak height", "iAUC", "Peak time"],
              [[r, int(sel(new[r], "peak_height").n), int(sel(new[r], "recovery_time_min").n)]
               + [f"{sel(new[r], f).ICC_A1:.2f}" for f in ["recovery_time_min", "peak_height", "iauc", "peak_time_min"]]
               for r in ORDER])
    L += ["", "#### Recovery time: agreement, new vs provisional", "",
          f"{cap} n = TP pairs used (new). Bias = detector minus reference (min).", ""]
    rows = []
    for r in ORDER:
        x, p = sel(new[r], "recovery_time_min"), sel(prov[r], "recovery_time_min")
        rows.append([r, int(x.n), f"{x.ICC_A1:.2f}", f"{p.ICC_A1:.2f}", f"{x.BA_bias:.0f}",
                     f"{x.BA_loa_low:.0f} to {x.BA_loa_high:.0f}"])
    L += _tbl(["Rule", "n", "ICC new", "ICC provisional", "Bias new (min)", "95 % LoA new (min)"], rows)
    L += ["", "#### Recovery time by stratum, excursion_end (new definition)", "",
          f"{cap} n = TP pairs used. Bias = detector minus reference (min).", ""]
    a = new["excursion_end"]
    L += _tbl(["Stratum", "n", "ICC", "Bias (min)", "95 % LoA (min)"],
              [[st, int(x.n), f"{x.ICC_A1:.2f}", f"{x.BA_bias:.0f}", f"{x.BA_loa_low:.0f} to {x.BA_loa_high:.0f}"]
               for st in ["overall"] + GROUPS + ["breakfast", "lunch"]
               for x in [sel(a, "recovery_time_min", st)]])
    bias = {st: sel(a, "recovery_time_min", st).BA_bias for st in GROUPS + ["breakfast", "lunch"]}
    if min(bias["prediabetes"], bias["T2D"]) > bias["healthy"] and bias["lunch"] > bias["breakfast"]:
        L += ["", "The detector over-estimates recovery time more in prediabetes, T2D and lunch."]
    else:
        L += ["", "Bias by stratum does not follow the prediabetes / T2D / lunch pattern on this route."]
    for anchor, label in [("det", "detector anchor"), ("ref", "reference anchor (logged meal start)")]:
        x = et[(et.route == route) & (et.adjacent_rule == "excursion_end") & (et.anchor == anchor)]
        L += ["", f"#### End type by group, excursion_end, {label}", "",
              f"{cap} n = TP pairs. Values are % of n.", ""]
        L += _tbl(["Group", "n", "Returned", "Trough", "Trough interrupted", "Censored", "No rise"],
                  [[r.group, int(r.n)] + [f"{r[f'{t}_pct']:.1f}" for t in END_TYPES] for r in x.itertuples()
                   for r in [x.loc[r.Index]]])
    for anchor, label in [("det", "detector anchor"), ("ref", "reference anchor")]:
        x = rt[(rt.route == route) & (rt.adjacent_rule == "excursion_end") & (rt.anchor == anchor)]
        rows = []
        for g in ["overall"] + GROUPS:
            y = x[x.group == g].set_index("end_type")
            rows.append([g] + ["" if y.loc[t].n == 0 else
                               f"{y.loc[t, 'median']:.0f} [{y.loc[t].q1:.0f}, {y.loc[t].q3:.0f}] ({int(y.loc[t].n)})"
                               for t in END_TYPES])
        L += ["", f"#### Recovery time (min) by end type, excursion_end, {label}", "",
              f"{cap} Median [IQR] (n = TP pairs).", ""]
        L += _tbl(["Group", "Returned", "Trough", "Trough interrupted", "Censored", "No rise"], rows)
    x = mbg[mbg.route == route]
    L += ["", "#### Merging by group, excursion_end", "",
          f"{cap} Raw = all detections at the locked parameters, all day.", ""]
    L += _tbl(["Group", "Raw detections", "% merged", "Events"],
              [[r.group, int(r.raw_detections), f"{r.merged_pct:.1f}", int(r.events)] for r in x.itertuples()])
    return L


def _params(rule, route):
    return json.load(open(OUT / rule / "params" / f"chosen_params_route{route}_ours.json"))


def write_readme():
    """excursion_v2/README.md from the saved outputs, plain ASCII."""
    o = load_outputs()
    E = load_config(run_harvey.HARVEY_CONFIG)["excursion"]
    by, et, new, prov = o["by"], o["et"], o["new"], o["prov"]
    b = by[("B", "excursion_end", "overall")]
    rt_icc = lambda d, r: d[r][(d[r].route == "B") & (d[r].stratum == "overall")
                               & (d[r].feature == "recovery_time_min")].ICC_A1.iloc[0]
    cens = lambda anchor: ", ".join(
        f"{g} {et[(et.route == 'B') & (et.adjacent_rule == 'excursion_end') & (et.anchor == anchor) & (et.group == g)].censored_pct.iloc[0]:.1f}"
        for g in GROUPS)
    L = ["# Harvey (GRID): shared excursion definition (excursion_v2)", "",
         "## Summary", "",
         "- Harvey GRID on CGMacros (Dexcom, 42 participants), test data, our matching window (-30 to +120 min).",
         "- One shared excursion definition drives the merge rule excursion_end and the recovery features.",
         "- Candidate main rule: excursion_end. It needs no meal log.",
         f"- Route B, excursion_end: Sens {_pct(b, 'sensitivity')} %, Prec {_pct(b, 'precision')} %, "
         f"F2 {_ci(b, 'F2', '{:.3f}')}, FP/day {_ci(b, 'FP_per_day', '{:.2f}')}.",
         f"- Recovery-time ICC, Route B, excursion_end: {rt_icc(new, 'excursion_end'):.2f} new vs "
         f"{rt_icc(prov, 'excursion_end'):.2f} provisional.",
         f"- % censored at 180 min, Route B, excursion_end: reference anchors {cens('ref')}; detector anchors {cens('det')}.",
         "- The excursion definition is frozen as of 2026-10-01. Later changes go to sensitivity analyses only.",
         "", "## Rules", "", "Route A and B, our matching rule. Applied to detections before scoring.", ""]
    L += _tbl(["Rule", "What it does", "Needs meal log?", "Role"], RULE_INFO)
    L += ["", "## Excursion definition", "",
          "Code: `common/evaluation/excursion.py`. Input: an anchor a and the QC'd 1-min glucose.",
          "The anchor is a detection (detector) or the logged meal start (reference).", "",
          f"- Baseline b = min glucose over the valid minutes in [a - {E['lookback_min']} min, a].",
          "- Running peak P(t) = max glucose in (a, t]. If glucose later exceeds P, P updates.",
          f"- Rise gate: an end counts only once P(t) - b >= {E['abs_tol_mg_dl']} mg/dL.",
          f"- Fall requirement: any end also needs P(t) - glucose(t) >= {E['trough_drop']:.2f} * (P(t) - b).",
          "- The excursion ends at the earliest of:",
          f"  1. Return: glucose(t) <= b + max({E['abs_tol_mg_dl']} mg/dL, {E['rel_tol']:.2f} * (P(t) - b)), after the time of P(t).",
          f"  2. Trough: a local minimum m after the peak, confirmed when glucose rises to >= m + {E['trough_rise_mg_dl']} mg/dL "
          f"within {E['trough_confirm_min']} min. The end is the time of m. A dip under {100 * E['trough_drop']:.0f} % of the rise is not an end, so a double peak stays one excursion.",
          f"  3. Censor: a + {E['max_event_min']} min.",
          "- A QC gap never counts as a return or a trough. Missing minutes in the trough confirmation mean no confirmation.",
          "- End types: returned, trough, trough_interrupted, censored, no_rise.",
          "  - trough_interrupted: a trough followed by a new start. Detector: a raw detection in (t_m, t_m + 30]. "
          "Reference: any logged food entry (any type) in [t_m - 30, t_m + 30].",
          f"  - no_rise: glucose never rose {E['abs_tol_mg_dl']} mg/dL above b within {E['max_event_min']} min.",
          "  - censored: the excursion rose but did not end by a + 180.",
          "- Features: peak = max in (a, end]. Recovery time = end minus peak time. iAUC = area above b from a to the end. "
          "Peak time is measured from a. Completeness check unchanged: no missing minute in [a - 30, a + 180].",
          "- Sources: trough end follows Lim 2026 (PPGR end at the wavelet minimum after the peak) and Fernandes 2022 "
          "(MAGE, peak to nadir). The 50 % drop that keeps double peaks together follows Archavli 2024. "
          "The 10 mg/dL rise matches the Lim 2026 minimum PPGR rise.", "",
          "**Worked example.** Baseline 90 mg/dL, peak 150 mg/dL, so the rise is 60.",
          "The return tolerance is max(10, 0.20 * 60) = 12, so the return threshold is 90 + 12 = 102 mg/dL.",
          "The fall requirement is 0.50 * 60 = 30, so glucose must be <= 150 - 30 = 120 mg/dL.",
          "A return therefore happens at the first minute after the peak with glucose <= 102.",
          "A trough can end it earlier only at a local minimum <= 120 that is followed by a 10 mg/dL rise within 30 min.", "",
          "Parameters (`[excursion]` in `common/configs/cgmacros_eval.toml`), fixed and not tuned:", ""]
    L += _tbl(["Name", "Value", "Meaning"], [
        ["lookback_min", E["lookback_min"], "Baseline window before the anchor (min)"],
        ["abs_tol_mg_dl", E["abs_tol_mg_dl"], "Minimum return tolerance and rise gate (mg/dL)"],
        ["rel_tol", f"{E['rel_tol']:.2f}", "Return tolerance as a fraction of the rise"],
        ["trough_drop", f"{E['trough_drop']:.2f}", "Minimum fall from the peak, as a fraction of the rise"],
        ["trough_rise_mg_dl", E["trough_rise_mg_dl"], "Rise that confirms a trough (mg/dL)"],
        ["trough_confirm_min", E["trough_confirm_min"], "Time allowed for that rise (min)"],
        ["max_event_min", E["max_event_min"], "Censor time after the anchor (min)"]])
    L += ["", "## Main results, Route B", ""]
    L += _route_tables(o, "B", "test data (5 held-out folds pooled)")
    L += ["", "## Locked parameters, Route B (all-participant set)", "",
          "Route B, tuned on all 42 participants; candidate lock for AI-READI; no held-out score.", ""]
    rows = []
    for r in ORDER:
        rec = _params(r, "B")["all_participants"]
        rows.append([r] + [PFMT[k].format(rec["params"][k]) for k in PNAME] +
                    [", ".join(PNAME[e] for e in rec["grid_edges_forced"]) or "none"])
    L += _tbl(["Rule", "tau_F", "G_min", "G'_min,3", "G'_min,2", "Forced grid edges"], rows)
    L += ["", "Forced grid edges are parameters that every tied grid point shares. G'_min,2 = 0.8 sits on the lower "
          "grid edge for every rule. With G'_min,2 = 0.8, G'_min,3 has no effect and its value comes from the grid order."]
    a = lambda rule, f, st="overall": new[rule][(new[rule].route == "B") & (new[rule].stratum == st)
                                                 & (new[rule].feature == f)].iloc[0]
    tp = by[("B", "tp_lockout", "overall")]
    L += ["", "## Reading notes", "",
          f"- Route B: excursion_end Sens {100 * b.sensitivity:.1f} % vs tp_lockout {100 * tp.sensitivity:.1f} %; "
          f"FP/day {b.FP_per_day:.2f} vs {tp.FP_per_day:.2f}.",
          f"- Recovery-time ICC (new) is {min(rt_icc(new, r) for r in ORDER):.2f} to {max(rt_icc(new, r) for r in ORDER):.2f} "
          f"across rules (Route B). Provisional: {min(rt_icc(prov, r) for r in ORDER):.2f} to {max(rt_icc(prov, r) for r in ORDER):.2f}.",
          f"- excursion_end recovery-time bias: breakfast {a('excursion_end', 'recovery_time_min', 'breakfast').BA_bias:.0f} min, "
          f"lunch {a('excursion_end', 'recovery_time_min', 'lunch').BA_bias:.0f} min (Route B).",
          f"- excursion_end peak height: ICC {a('excursion_end', 'peak_height').ICC_A1:.2f}, bias "
          f"{a('excursion_end', 'peak_height').BA_bias:+.1f} mg/dL (Route B).",
          "- Detector anchors were never no_rise. T2D has the most censored excursions at both anchors (Route B)."]
    # ---- appendix
    L += ["", "## Appendix", "", "### Route A (per-participant split)", ""]
    L += _route_tables(o, "A", "test data (per-participant test days)")
    L += ["", "### Locked parameters, all sets", "",
          "Route B: one set per fold plus the all-participant set. Forced grid edges as above.", ""]
    rows = []
    for r in ORDER:
        for k, rec in _params(r, "B").items():
            rows.append([r, k] + [PFMT[p].format(rec["params"][p]) for p in PNAME] +
                        [", ".join(PNAME[e] for e in rec["grid_edges_forced"]) or "none"])
    L += _tbl(["Rule", "Set", "tau_F", "G_min", "G'_min,3", "G'_min,2", "Forced grid edges"], rows)
    L += ["", "Route A: one set per participant (n = 42). Mean +/- SD, and the number of participants with a forced edge.", ""]
    rows = []
    for r in ORDER:
        rec = _params(r, "A")
        P_ = pd.DataFrame({k: v["params"] for k, v in rec.items()}).T
        fe = pd.Series([e for v in rec.values() for e in v["grid_edges_forced"]]).value_counts()
        rows.append([r] + [f"{P_[p].mean():.2f} +/- {P_[p].std():.2f} ({int(fe.get(p, 0))})" for p in PNAME])
    L += _tbl(["Rule", "tau_F", "G_min", "G'_min,3", "G'_min,2"], rows)
    L += ["", "### Step 0 findings (provisional recovery rule)", "",
          "- Recovery time is measured from the peak to the end.",
          "- The return rule had no tolerance: glucose <= baseline.",
          "- iAUC runs from the anchor to the end, above baseline.",
          "- Peak time is measured from the anchor.",
          "- The baseline was the mean of [a - 30, a). The peak was the max over the full 180 min.",
          "", "### Two fixes made after seeing results (2026-10-01)", "",
          "Neither adds a parameter. Details: `common/docs/deviations.md` (X1, X6) and `methods/harvey/docs/deviations.md`.", "",
          "1. Rise gate. The first specification had no rise requirement. 62 % of reference excursions (Route B) "
          "ended within 5 min of the meal start, before the rise. The gate reuses abs_tol.",
          "2. Fall requirement. With the gate alone, a rise just over 10 mg/dL and a 1 mg/dL dip counted as a return. "
          "6.6 % of reference excursions that rose still ended within 15 min (Route B). After the fix: 2.4 %. It reuses trough_drop.",
          "", "### Files", ""]
    L += _tbl(["File", "Content"], [
        ["`comparison.csv`, `comparison.md`", "All four rules, Route A and B, all strata, 95 % CI (tables a to h)"],
        ["`detection_counts.csv`", "Raw, removed by the rule, ignored by the TP lockout, kept and scored"],
        ["`end_type_by_group.csv`", "End type % by rule, route, anchor and group (TP pairs)"],
        ["`recovery_time_by_end_type.csv`", "Recovery time median and IQR by rule, route, anchor, group, end type"],
        ["`recovery_icc_no_rise_excluded.csv`", "Pairs left out of the recovery-time ICC"],
        ["`merge_by_group.csv`", "excursion_end merging by group"],
        ["`<rule>/summary*.csv`, `params/`, `recovery_agreement.csv`, `plots/`", "Per-rule outputs (new definition)"],
        ["`excursion_end/recovery_agreement_provisional.csv`", "Provisional agreement for excursion_end detections"],
        ["`<rule>/detections.csv`, `meals.csv`, `recovery_features.csv`", "Row-level, not committed"]])
    L += ["", "### Run", "",
          "From `replication/`:", "",
          "```",
          "python methods/harvey/src/run_harvey_excursion_v2.py",
          "python methods/harvey/src/run_harvey_excursion_v2.py --docs-only",
          "```", "",
          "The first runs the pipeline (about 3 min, deterministic). It reads `reference_tp_lockout/` and `peak_rules/` "
          "and never writes to them. The second rebuilds `comparison.md` and this README from the saved outputs."]
    PR.write_ascii(OUT / "README.md", "\n".join(L) + "\n")

if __name__ == "__main__":
    if "--docs-only" in sys.argv:          # rebuild comparison.md and README from saved outputs
        write_comparison_md()
        write_readme()
    else:
        main()
