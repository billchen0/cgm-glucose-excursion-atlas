"""Same detector scored on its own train period vs the test period.

Question: is the weak test-period performance the algorithm's general ceiling, or
an artefact of late-study drift / a threshold overfitted to the training period?

Setup = the main-line breakfast+lunch pipeline with the per-record dinner/snack
mask on (run_bl_mask.py `mask` config) and the C05-15 scoring rule. Nothing is
re-tuned: template and TH are exactly the ones already built on each subject's
train period (read from results/bl/templates_thresholds.json). The train-period
numbers are therefore IN-SAMPLE for persTMA and optimistic by construction - they
are not a fair comparison, they are a diagnostic.

  persTMA: template curves AND TH come from this subject's own train period ->
           train numbers are in-sample (optimism + any drift).
  popTMA : template and TH come from the other 44 subjects (leave-one-subject-out),
           so this subject's train period is out-of-sample as well -> the
           train-vs-test gap is closer to a pure temporal-drift estimate.

Scoring reuses run_tma.evaluate_test unchanged. To score a period, the subject
dict is passed with split=0 (so no peak is dropped by the built-in test filter)
and the period restriction is expressed through the same `outside` not-evaluated
mask that already carries the daily window and the dinner/snack mask, applied at
each protocol's scored time. The `test` rows here therefore use the same boundary
convention as the `train` rows; results/bl_maskDS/ (peak >= split) is reproduced
to within a couple of events.

Outputs: results/train_vs_test/. Nothing existing is modified.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.data import cgmacros  # noqa: E402
import run_bl as B  # noqa: E402
import run_bl_mask as BM  # noqa: E402
import run_tma as R  # noqa: E402
import tma  # noqa: E402

OUT = HERE / "results" / "train_vs_test"
EVAL = "C05-15"


def period_view(sb, period, cc_len):
    """A copy of sb that makes evaluate_test score one period, plus the extra
    not-evaluated mask for the other period."""
    idx = np.arange(cc_len)
    other = idx >= sb["split"] if period == "train" else idx < sb["split"]
    in_period = sb["meal_idx"] < sb["split"] if period == "train" else sb["meal_idx"] >= sb["split"]
    days = sb["train_days"] if period == "train" else sb["test_days"]
    v = dict(sb, split=0, test_days=days)
    return v, ~in_period, other


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bio = cgmacros.load_bio().set_index("subject")
    subjects = [R.prepare(s) for s in cgmacros.list_subjects()]
    meals = {s["subject"]: B.load_typed_meals(s) for s in subjects}
    win = B.derive_window(meals)
    th_bl = json.load(open(HERE / "results" / "bl" / "templates_thresholds.json"))

    sbs = []
    for s in subjects:
        sb = B.attach_bl(s, meals[s["subject"]], win)
        sb["group"] = bio.loc[s["subject"], "group"]
        sb["ds_raw"] = BM.raw_dinner_snack_times(s["subject"])
        sb["ds_times"] = sb["ds_raw"]
        tr_bl = sb["meal_idx"][sb["meal_idx"] < s["split"]]
        sb["curves_bl"], _ = tma.select_template_curves(
            s["g"], tr_bl, R.N_CURVES, all_meal_idx=s["meal_idx"])
        sb["mask_carve"] = BM.ds_mask(sb, True)
        sbs.append(sb)

    rows = []
    for i, sb in enumerate(sbs):
        others = [o for j, o in enumerate(sbs) if j != i]
        for ver in ["persTMA", "popTMA"]:
            if ver == "persTMA":
                if len(sb["curves_bl"]) < 2:
                    continue
                T, d = tma.average_aligned(sb["curves_bl"], 1.0)
            else:
                T, d = tma.average_aligned([c for o in others for c in o["curves_bl"]], 0.5)
            th = th_bl[sb["subject"]][ver]["TH"]
            cc, sil, bad, _ = B.portion_bl(sb, T, d, False)
            for period in ["train", "test"]:
                v, is_train_arg, other = period_view(sb, period, len(cc))
                not_eval = sb["outside"] | sb["mask_carve"] | other
                r = R.evaluate_test(v, cc, sil, bad, is_train_arg, th, len(T), outside=not_eval)
                rows.append(dict(
                    subject=sb["subject"], group=sb["group"], version=ver, split=period,
                    in_sample=(ver == "persTMA"), evaluation=EVAL, TH=th, M=len(T),
                    scored_hours=BM.scored_hours(dict(sb, split=0), not_eval, True),
                    n_meals_eval=r["n_test_meals_eval"],
                    **{k: val for k, val in r[EVAL].items() if not k.startswith("_")},
                    delays=json.dumps([round(x, 1) for x in r[EVAL]["_delays"]])))
        print(sb["subject"], flush=True)

    per = pd.DataFrame(rows)
    per.to_csv(OUT / "per_subject.csv", index=False)

    summ = []
    for (ver, period), df in per.groupby(["version", "split"]):
        for g, dg in [("all", df)] + list(df.groupby("group")):
            p = R.pooled(dg)
            p["scored_hours"] = dg.scored_hours.sum()
            p["FP_per_10_scored_h"] = 10 * p["FP"] / p["scored_hours"]
            p["n_meals_eval"] = int(dg.n_meals_eval.sum())
            summ.append(dict(version=ver, split=period, group=g,
                             in_sample=bool(dg.in_sample.iloc[0]), evaluation=EVAL, **p))
    summ = pd.DataFrame(summ)
    summ.to_csv(OUT / "summary.csv", index=False)

    cols = ["version", "split", "in_sample", "sensitivity", "precision", "F1", "FP_per_day",
            "FP_per_10_scored_h", "TP", "FP", "FN", "n_meals_eval", "days", "scored_hours"]
    main_tbl = summ[summ.group == "all"][cols].sort_values(["version", "split"])
    main_tbl.to_csv(OUT / "train_vs_test.csv", index=False)
    print("\nEvaluation:", EVAL, "| breakfast+lunch ground truth, daily window + per-record"
          " dinner/snack mask\ntrain rows are IN-SAMPLE for persTMA (template and TH were"
          " chosen on that period)\n")
    print(main_tbl.round(3).to_string(index=False))
    print("\nby glycaemic group:")
    print(summ[summ.group != "all"][["version", "split", "group", "sensitivity", "precision",
                                     "F1", "FP_per_day", "TP", "FP", "n_meals_eval"]]
          .sort_values(["version", "group", "split"]).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
