"""Harvey (GRID) with the label-free adjacent-detection rules (our matching rule only).

Re-tunes Route A and Route B with each rule applied before scoring, then compares against
the reference run in methods/harvey/results/reference_tp_lockout/ (120-min TP lockout),
which is read, not rewritten.

Usage: python methods/harvey/src/run_harvey_peak_rules.py
Outputs: methods/harvey/results/peak_rules/ (see its README.md).
"""
import copy
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_harvey  # noqa: E402
from common.evaluation import load_config  # noqa: E402

OUT = run_harvey.HARVEY / "results" / "peak_rules"
REF = run_harvey.OUT
NEW_RULES = ["meal_window_max_peak", "refractory", "baseline_return"]
LABELS = {"tp_lockout": "reference only: 120-min lockout after each TP (Hochsmann 2026; uses meal logs)",
          "meal_window_max_peak": "sensitivity: one detection per Lim 2026 meal window, highest peak",
          "refractory": "sensitivity: 120-min refractory after every kept detection",
          "baseline_return": "candidate main: merge detections until glucose returns near baseline"}
from common.evaluation.report import (FEATURES, GROUPS, KEYS, detection_counts, fmt,  # noqa: E402,F401
                                      md_table, params_rows, write_ascii)


def merge_by_group(det):
    """baseline_return: merging and event flags per route and group (all detections, all day)."""
    rows = []
    for route, d in det.groupby("route"):
        for g in ["overall"] + GROUPS:
            x = d if g == "overall" else d[d.group == g]
            anchors = x[x.detection_time == x.event_anchor]
            merged = x.status.str.startswith("removed").sum()
            rows.append(dict(route=route, group=g, raw_detections=len(x),
                             merged_pct=round(100 * merged / len(x), 1),
                             events=len(anchors),
                             censored_pct=round(100 * anchors.event_censored.mean(), 1),
                             fallback_baseline_pct=round(100 * anchors.event_fallback.mean(), 1)))
    return pd.DataFrame(rows)


def main():
    base = load_config(run_harvey.HARVEY_CONFIG)
    OUT.mkdir(parents=True, exist_ok=True)
    for rule in NEW_RULES:
        cfg = copy.deepcopy(base)
        cfg["scoring"]["adjacent_rule"] = rule
        run_harvey.run(cfg, out=OUT / rule, rules=["ours"], tag_extra={"adjacent_rule": rule},
                       reference_fixed=False)

    # comparison: reference (read from methods/harvey/results/reference_tp_lockout/) vs the new rules
    ref = pd.read_csv(REF / "summary.csv")
    ref = ref[(ref.rule == "ours") & ref.route.isin(["A", "B"])].assign(adjacent_rule="tp_lockout")
    new = [pd.read_csv(OUT / r / "summary.csv") for r in NEW_RULES]
    allsum = pd.concat([ref] + new, ignore_index=True)
    order = {r: i for i, r in enumerate(["tp_lockout"] + NEW_RULES)}
    allsum = allsum.sort_values(["route", "stratum", "adjacent_rule"],
                                key=lambda c: c.map(order) if c.name == "adjacent_rule" else c,
                                kind="stable")
    cols = ["adjacent_rule", "route", "rule", "stratum", "participants", "days"] + \
        [c for c in allsum.columns if any(c.startswith(k) for k in KEYS)] + ["lockout_ignored"]
    allsum[cols].round(4).to_csv(OUT / "comparison.csv", index=False)

    # detection counts at the locked parameters
    rows = []
    ref_det = pd.read_csv(REF / "detections.csv")
    rows += detection_counts(ref_det[(ref_det.rule == "ours") & ref_det.route.isin(["A", "B"])],
                             "tp_lockout")
    for r in NEW_RULES:
        rows += detection_counts(pd.read_csv(OUT / r / "detections.csv"), r)
    counts = pd.DataFrame(rows).sort_values(["route", "adjacent_rule"],
                                            key=lambda c: c.map(order) if c.name == "adjacent_rule" else c)
    counts.to_csv(OUT / "detection_counts.csv", index=False)

    mbg = merge_by_group(pd.read_csv(OUT / "baseline_return" / "detections.csv"))
    mbg.to_csv(OUT / "merge_by_group.csv", index=False)

    write_comparison_md()


def write_comparison_md():
    """comparison.md (tables a-g) from the saved CSV and JSON outputs only."""
    allsum = pd.read_csv(OUT / "comparison.csv")
    counts = pd.read_csv(OUT / "detection_counts.csv")
    mbg = pd.read_csv(OUT / "merge_by_group.csv")
    rules = ["tp_lockout"] + NEW_RULES
    by = {(r.route, r.adjacent_rule, r.stratum): r for _, r in allsum.iterrows()}
    L = ["## a) Overall detection", ""]
    L += ["| Route | Rule | TP | FP | FN | Sens % | Prec % | F2 | FP/day | Delay median | Delay mean |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    ka = ["TP", "FP", "FN", "sensitivity", "precision", "F2", "FP_per_day", "delay_median", "delay_mean"]
    for route in ["A", "B"]:
        for rule in rules:
            r = by[(route, rule, "overall")]
            L.append(f"| {route} | {rule} | " + " | ".join(fmt(r, k) for k in ka) + " |")
    L += ["", "## b) By glycaemic group", ""]
    L += ["| Route | Rule | " + " | ".join(f"Sens % {g}" for g in GROUPS) + " | Sens range (pp) | "
          + " | ".join(f"Prec % {g}" for g in GROUPS) + " | " + " | ".join(f"FP/day {g}" for g in GROUPS) + " |",
          "|---|---|" + "---|" * 10]
    for route in ["A", "B"]:
        for rule in rules:
            rs = [by[(route, rule, g)] for g in GROUPS]
            rng = 100 * (max(x.sensitivity for x in rs) - min(x.sensitivity for x in rs))
            L.append(f"| {route} | {rule} | " + " | ".join(fmt(x, "sensitivity") for x in rs)
                     + f" | {rng:.1f} | " + " | ".join(fmt(x, "precision") for x in rs) + " | "
                     + " | ".join(fmt(x, "FP_per_day") for x in rs) + " |")
    L += ["", "## c) By meal", ""]
    L += ["| Route | Rule | Sens % breakfast | Delay median breakfast | Sens % lunch | Delay median lunch |",
          "|---|---|---|---|---|---|"]
    for route in ["A", "B"]:
        for rule in rules:
            b_, l_ = by[(route, rule, "breakfast")], by[(route, rule, "lunch")]
            L.append(f"| {route} | {rule} | {fmt(b_, 'sensitivity')} | {fmt(b_, 'delay_median')} | "
                     f"{fmt(l_, 'sensitivity')} | {fmt(l_, 'delay_median')} |")
    L += ["", "## d) Recovery-feature agreement (TP pairs, overall; PROVISIONAL segmentation)", ""]
    L += ["| Route | Rule | Feature | n | ICC(A,1) | BA bias | 95 % LoA |", "|---|---|---|---|---|---|---|"]
    agr = {"tp_lockout": pd.read_csv(REF / "recovery_agreement.csv").query("rule == 'ours'")}
    agr |= {r: pd.read_csv(OUT / r / "recovery_agreement.csv") for r in NEW_RULES}
    for route in ["A", "B"]:
        for f in FEATURES:
            for rule in rules:
                a = agr[rule]
                x = a[(a.route == route) & (a.stratum == "overall") & (a.feature == f)].iloc[0]
                L.append(f"| {route} | {rule} | {f} | {int(x.n)} | {x.ICC_A1:.2f} | {x.BA_bias:.1f} | "
                         f"{x.BA_loa_low:.1f} to {x.BA_loa_high:.1f} |")
    L += ["", "## e) Detection counts at the locked parameters", ""]
    L += md_table(counts[["route", "adjacent_rule", "raw_detections", "removed_by_rule",
                          "removed_in_scoring_window", "ignored_by_tp_lockout", "kept_scored_TP_FP"]],
                  ["Route", "Rule", "Raw", "Removed by rule", "Removed inside scoring window",
                   "Ignored by TP lockout", "Kept and scored (TP + FP)"])
    L += ["", "## f) Locked parameters and forced grid edges", ""]
    prow = []
    for rule in rules:
        d = REF / "params" if rule == "tp_lockout" else OUT / rule / "params"
        for route in ["A", "B"]:
            prow += params_rows(d / f"chosen_params_route{route}_ours.json", rule, route)
    L += md_table(pd.DataFrame(prow)[["rule", "route", "set", "tau_F", "G_min", "Gp_min_3", "Gp_min_2",
                                      "forced_edges"]],
                  ["Rule", "Route", "Set", "tau_F", "G_min", "G'_min,3", "G'_min,2", "Forced edges"])
    L += ["", "## g) baseline_return: merging by group", ""]
    L += md_table(mbg, ["Route", "Group", "Raw detections", "% merged", "Events", "% censored at 180 min",
                        "% fallback baseline"])
    write_ascii(OUT / "comparison.md", "\n".join(L) + "\n")


if __name__ == "__main__":
    # --docs-only: rebuild comparison.md from the saved outputs, without re-running the pipeline
    write_comparison_md() if "--docs-only" in sys.argv else main()
