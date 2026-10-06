"""Write docs/results_summary.md from the saved protocol_v1 outputs (plain ASCII).

Tables: main results with 95 % CIs (Route B, refractory, our matching rule); tp_lockout with the
review matching rule vs Hochsmann 2026 Table 2; grid boundary hits and the main deviations.
The findings and the one-line deviations are written here by hand.

Usage (from the repository root): python common/make_results_summary.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.evaluation import REPO, detectors  # noqa: E402
from common.evaluation import protocol as PROT  # noqa: E402
from common.evaluation.report import GROUPS, fmt, md_table, write_ascii  # noqa: E402

ORDER = ["samadi", "faccioli", "harvey", "dassau_2of3", "dassau_3of4", "lim", "popp", "turksoy"]
HOCHSMANN = ["dassau_2of3", "dassau_3of4", "faccioli", "harvey", "popp", "samadi", "turksoy"]
DEVIATIONS = {   # one line each; full lists in the deviations files
    "harvey": "Native 5-min Dexcom; rising-edge events; grid as Hochsmann.",
    "dassau_2of3": "Eq. 5 as written (Threshold_ROC and Threshold_Acceleration only, unlike Table 1); Kalman settings are defaults.",
    "dassau_3of4": "Eq. 6 as written; same Kalman defaults; detection at t(i), available 4 min later.",
    "samadi": "Simplified rule as in the review; membership functions are defaults (Samadi 2017 not available).",
    "faccioli": "Observer bound L tuned on the grid, added after the first result (night gain rule gave Sens about 20 %).",
    "turksoy": "Original model has no insulin input; trimming bounds, 120-min warm-up and sigma-point clipping are defaults.",
    "popp": "Dalla Man 2007 model from BioModels; anchoring of the no-meal simulation is a default.",
    "lim": "Appendices A-C missing: smoothing, wavelet scale and tie-break are defaults; breakfast and lunch windows only.",
}
FINDINGS = [
    "The five best methods by F2 lie within 0.05 of each other: Samadi 0.786, Faccioli 0.758, Harvey 0.749, Dassau 2-of-3 0.740, Dassau 3-of-4 0.736. Lim follows at 0.713, Popp 0.649, Turksoy 0.581.",
    "Sensitivity and precision trade off. Samadi has the highest Sens (87.4 %) but the lowest Prec (55.9 %) and the most FP/day (1.37). Turksoy and Lim have the highest Prec (about 89 %) at Sens 53.5 % and 67.9 %.",
    "Lim is the most even across groups (Sens range 1.2 pp; it is window-limited, at most 2 detections per day). Popp is the least even: T2D Sens 44.5 % vs 76.8 % in healthy (range 32.2 pp).",
    "Recovery-time ICC(A,1) between detector and logged-meal anchors ranges from 0.61 (Popp) to 0.72 (Harvey).",
    "In all seven tuned methods at least one selected parameter sits on a grid bound (table above), mostly the permissive one (Faccioli's Th_Der is on the strict bound), so a better operating point may lie outside the published grids. Faccioli's observer bound L was added to the grid after the first result.",
    "Turksoy is limited by a weak R_a response: only 59 % of meals push the estimated R_a above 1.5 mg/dL/min, the lowest threshold, within 120 min.",
]


def run_dirs():
    out = {}
    for name in ORDER:
        cfg = PROT.protocol_config(name)
        out[name] = (cfg, PROT.protocol_dir(name, cfg))
    return out


def rel(p):
    return str(Path(p).relative_to(REPO))


def main():
    runs = run_dirs()
    L = ["# Results summary", "",
         "All methods under the standard protocol on CGMacros: 42 participants, 332 scored days, "
         "breakfast and lunch as ground truth. Route B (5 participant folds, test data pooled). "
         "95 % participant-bootstrap CIs in brackets. Built by `common/make_results_summary.py` from "
         "the saved outputs; the per-method READMEs have the details.", ""]

    # 1. main table
    rows = []
    for name, (cfg, d) in runs.items():
        s = pd.read_csv(d / "refractory" / "summary.csv")
        s = s[(s.rule == "ours") & (s.route == "B")].set_index("stratum")
        o = s.loc["overall"]
        a = pd.read_csv(d / "refractory" / "recovery_agreement.csv")
        icc = a[(a.rule == "ours") & (a.route == "B") & (a.stratum == "overall")
                & (a.feature == "recovery_time_min")].ICC_A1.iloc[0]
        sens = [s.loc[g, "sensitivity"] for g in GROUPS]
        title = cfg["methods"][name]["about"]["title"]
        rows.append([f"[{title}](../{rel(d)}/README.md)", fmt(o, "sensitivity"), fmt(o, "precision"),
                     fmt(o, "F2"), fmt(o, "FP_per_day"), fmt(o, "delay_median"),
                     f"{100 * (max(sens) - min(sens)):.1f}", f"{icc:.2f}"])
    L += ["## Main results", "",
          "Main adjacent rule (refractory), our matching rule (-30 to +120 min). Sorted by F2. Sens range = "
          "max minus min across healthy, prediabetes and T2D. Recovery-time ICC = ICC(A,1), detector vs "
          "logged-meal anchor. Lim is window-limited (at most 2 detections per day), so its FP/day is not "
          "comparable with the all-day detectors.", ""]
    L += md_table(pd.DataFrame(rows), ["Method", "Sens %", "Prec %", "F2", "FP/day", "Delay median (min)",
                                       "Sens range (pp)", "Recovery-time ICC"])

    # 2. vs Hochsmann
    rows = []
    for name in HOCHSMANN:
        cfg, d = runs[name]
        about = cfg["methods"][name]["about"]
        h = about["hochsmann2026_table2"]
        s = pd.read_csv(d / "tp_lockout" / "summary.csv")
        o = s[(s.rule == "review") & (s.route == "B") & (s.stratum == "overall")].iloc[0]
        sens = float(fmt(o, "sensitivity").split()[0])
        fpd = float(fmt(o, "FP_per_day").split()[0])
        dl = float(fmt(o, "delay_mean").split()[0])
        rows.append([about["title"], f"{sens:.1f}", f"{h['sensitivity_pct']:.1f}", f"{sens - h['sensitivity_pct']:+.1f}",
                     f"{fpd:.2f}", f"{h['fp_per_day']:.2f}", f"{dl:.1f}", f"{h['delay_mean_min']:.1f}"])
    L += ["", "## Comparison with Hochsmann 2026 Table 2 (not like-for-like)", "",
          "tp_lockout with the review matching rule (0 to +120 min), Route B, test data, vs Hochsmann 2026 "
          "Table 2 (16 healthy young adults, Libre 2, three meals a day, afternoon detections suppressed, "
          "per-participant or global tuning). Cohort, sensor, scored meals, scoring window and tuning all "
          "differ. Delay is the mean, as in Table 2. Difference = ours minus Hochsmann (pp).", ""]
    L += md_table(pd.DataFrame(rows), ["Method", "Sens % ours", "Sens % Hochsmann", "Difference (pp)",
                                       "FP/day ours", "FP/day Hochsmann", "Delay ours", "Delay Hochsmann"])

    # 3. boundary hits and deviations
    rows = []
    for name, (cfg, d) in runs.items():
        about = cfg["methods"][name]["about"]
        labels = about.get("param_labels", {})
        ax = detectors.get(name).grid_axes(cfg)
        p = json.loads((d / "refractory" / "params" / "chosen_params_routeB_ours.json").read_text())
        hits = []
        for k, a in ax.items():
            if len(a) == 1:
                continue
            lo = sum(abs(v["params"][k] - a[0]) < 1e-9 for v in p.values())
            hi = sum(abs(v["params"][k] - a[-1]) < 1e-9 for v in p.values())
            lab = labels.get(k, k).split(" (")[0]
            if lo:
                hits.append(f"{lab} low {lo}/{len(p)}")
            if hi:
                hits.append(f"{lab} high {hi}/{len(p)}")
        fixed = all(len(a) == 1 for a in ax.values())
        hit = "fixed, not tuned" if fixed else (("yes: " + ", ".join(hits)) if hits else "no")
        dev = about["deviations"]
        rows.append([about["title"], hit, DEVIATIONS[name], f"[deviations](../{dev})"])
    L += ["", "## Grid boundary hits and main deviations", "",
          "Boundary hits: Route B sets (5 folds and all_participants, refractory) whose value lies on the "
          "lower or upper grid bound.", ""]
    L += md_table(pd.DataFrame(rows), ["Method", "Boundary hits", "Main deviations", "File"])

    L += ["", "## Findings", ""] + [f"- {f}" for f in FINDINGS]
    L += ["", "Excluded: Pellizzari 2025 TMA (needs training; common/docs/deviations.md Z6)."]
    write_ascii(REPO / "docs" / "results_summary.md", "\n".join(L) + "\n")
    print("wrote docs/results_summary.md")


if __name__ == "__main__":
    main()
