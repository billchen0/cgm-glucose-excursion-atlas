"""Export the saved TMA detections to the standard result format (common/docs/result_format.md).

Reads results/bl_maskDS/detections.csv (written by export_detections.py) and nothing else;
TMA code and results are not changed. One run per template version (persTMA, pop_mixed,
pop_grouped). Detections only: TMA's outputs have no scored-meal list, so meals.csv and
days.csv are "not available" and no FN is reconstructed.
Checked per subject against results/population_variants/per_subject.csv (C05-15).

Usage: python methods/pellizzari2025_tma/export_standard.py
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.export import result_format as RF  # noqa: E402

SRC = HERE / "results" / "bl_maskDS" / "detections.csv"
REF = HERE / "results" / "population_variants" / "per_subject.csv"
OUT = HERE / "results" / "standard"
DATE = "2026-09-22"            # commit 70125ee (detections.csv)
ROUTE = "own_split"
VERSIONS = {
    "persTMA": "Personal template and threshold (subject's own training meals)",
    "pop_mixed": "Population template and threshold, leave-one-subject-out, all other subjects",
    "pop_grouped": "Population template and threshold, leave-one-subject-out, same glycaemic group",
}
NOTE = ("Not directly comparable with runs on the common/ cohort. TMA uses its own protocol: "
        "all 45 participants with no cohort-flow QC (persTMA 44), a per-participant chronological "
        "60:40 split of meals (test period only), breakfast + lunch ground truth with logged "
        "dinner/snacks masked, a fixed daily window 04:43-17:31 combined with the 22:00-07:00 "
        "exclusion, TP window [-15, +120] min (C05-15) and a 120-min lockout after each TP. "
        "Detection time is the estimated meal onset (cross-correlation peak minus half the "
        "template). Only TP and FP are available: no FN, sensitivity or FP/day.")


def main():
    src = pd.read_csv(SRC)
    ref = pd.read_csv(REF)
    ref = ref[ref.evaluation == "C05-15"]
    ok = True
    for ver, desc in VERSIONS.items():
        s = src[src.version == ver]
        det = pd.DataFrame({
            "participant": s.subject, "detection_time": s.onset_time, "route": ROUTE,
            "split": "test", "status": s.status, "status_original": s.status,
            "matched_meal_time": s.meal_time, "delay_min": s.delay_min,
            "excursion_start": s.onset_time, "peak_time": s.peak_time,
            "group": s.group, "meal_type": s.meal_type,
            "meal_type_inferred": s.meal_type_inferred,
            "tp_window_start": s.win_start, "tp_window_end": s.win_end})
        meta = dict(
            method="pellizzari2025_tma", run=f"bl_maskDS_{ver}",
            title=f"TMA · {ver} · bl_maskDS · C05-15",
            description=f"Pellizzari 2025 Template Matching Algorithm. {desc}.",
            date=DATE, source="methods/pellizzari2025_tma/results/bl_maskDS",
            routes={ROUTE: dict(label="TMA's own split: chronological 60:40 per participant, "
                                      "test period", kind="tuning", evaluated_days="all")},
            adjacent_rule="tp_lockout", adjacent_rule_uses_labels=True,
            matching_rule=dict(name="C05-15", tp_before_min=15, tp_after_min=120,
                               description="[-15, +120] min around the logged start"),
            scoring_window="07:00-17:31 (fixed window 04:43-17:31 and 22:00-07:00 excluded), "
                           "test period; logged dinner/snacks masked",
            parameters_file="methods/pellizzari2025_tma/results/bl/templates_thresholds.json",
            available=dict(detections=True, meals=False, days=False),
            comparable=False, comparability_note=NOTE)
        out = RF.write_run(OUT / meta["run"], meta, det)

        got = RF.participant_summary(RF.read_run(out)).set_index("participant")[["TP", "FP"]]
        exp = ref[ref.variant == ver].set_index("subject")[["TP", "FP"]]
        exp = exp[(exp.TP + exp.FP) > 0]
        match = got.sort_index().equals(exp.sort_index().astype(int))
        ok &= match
        print(f"{out.relative_to(HERE.parents[1])}: {len(det)} detections, "
              f"TP={got.TP.sum()} FP={got.FP.sum()}  per-subject vs population_variants: "
              f"{'OK' if match else 'MISMATCH'}")
    print("ALL MATCH" if ok else "!!! MISMATCH")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
