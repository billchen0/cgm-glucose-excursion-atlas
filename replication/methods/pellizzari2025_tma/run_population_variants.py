"""persTMA vs population-mixed vs population-grouped, on the main-line setup.

The breakfast+lunch pipeline only ever implemented the MIXED population variant:
run_bl_mask.py pools the template curves of `others` (every other subject, no
group filter) and reads TH from results/bl, where run_bl.tune() tuned it on that
same all-44 donor set. The grouped variant existed only in run_grouped.py, which
runs on the older all-meal pipeline (no dinner/snack mask, templates from all
meal types), so it was not comparable. This script adds grouped to the main-line
setup and puts the three variants side by side.

Setup (identical for every row): breakfast+lunch ground truth, daily window
04:43-17:31, per-record dinner/snack mask with the breakfast/lunch carve-out
(run_bl_mask `mask` config), scored with C05-15.

Variants, all leave-one-subject-out - the held-out subject's own meal log is
never used for the population rows:
* persTMA  - template from the subject's own breakfast/lunch training meals,
             TH tuned on the subject's own training period (reference ceiling)
* pop_mixed- template + TH from the other 44 subjects (the variant already
             reported; TH read from results/bl, so this row reproduces
             results/bl_maskDS)
* pop_grouped - template + TH from the other subjects of the SAME glycaemic
             group (HbA1c cut-offs from Das 2025 via cgmacros.load_bio:
             < 5.7 healthy, 5.7-6.4 prediabetes, > 6.4 T2D -> 15/16/14)
Two hybrids are also written to the CSV to separate the template effect from the
threshold effect: mixT_grpTH (mixed template, group-tuned TH) and grpT_mixTH.

TH for every re-tuned row uses run_bl.tune() with silence_ds=False, the same
recipe that produced the mixed TH, so the rows differ only in the donor set.
Scoring reuses run_tma.evaluate_test unchanged. Outputs go to
results/population_variants/; nothing existing is modified.
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

OUT = HERE / "results" / "population_variants"
EVAL = "C05-15"
GROUPS = ["healthy", "prediabetes", "T2D"]


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
    by_group = {g: [s for s in sbs if s["group"] == g] for g in GROUPS}
    print({g: len(v) for g, v in by_group.items()})

    rows, meta = [], []
    for i, sb in enumerate(sbs):
        others = [o for j, o in enumerate(sbs) if j != i]
        same = [o for o in by_group[sb["group"]] if o is not sb]
        pool_mixed = [c for o in others for c in o["curves_bl"]]
        pool_group = [c for o in same for c in o["curves_bl"]]
        T_mix, d_mix = tma.average_aligned(pool_mixed, 0.5)
        T_grp, d_grp = tma.average_aligned(pool_group, 0.5)

        plans = [("pop_mixed", T_mix, d_mix, th_bl[sb["subject"]]["popTMA"]["TH"], len(pool_mixed), len(others)),
                 ("pop_grouped", T_grp, d_grp, None, len(pool_group), len(same)),
                 ("mixT_grpTH", T_mix, d_mix, None, len(pool_mixed), len(same)),
                 ("grpT_mixTH", T_grp, d_grp, None, len(pool_group), len(others))]
        if len(sb["curves_bl"]) >= 2:
            T_p, d_p = tma.average_aligned(sb["curves_bl"], 1.0)
            plans.insert(0, ("persTMA", T_p, d_p, th_bl[sb["subject"]]["persTMA"]["TH"],
                             len(sb["curves_bl"]), 0))

        for name, T, d, th, n_curves, n_donors in plans:
            if th is None:                       # same recipe as the mixed TH
                donors = others if name == "grpT_mixTH" else same
                th = B.tune(donors, T, d, False)
            cc, sil, bad, is_tr = B.portion_bl(sb, T, d, False)
            not_eval = sb["outside"] | sb["mask_carve"]
            r = R.evaluate_test(sb, cc, sil, bad, is_tr, th, len(T), outside=not_eval)
            rows.append(dict(
                subject=sb["subject"], group=sb["group"], variant=name, evaluation=EVAL,
                TH=th, M=len(T), n_template_curves=n_curves, n_donors=n_donors,
                scored_hours=BM.scored_hours(sb, not_eval, True),
                n_meals_eval=r["n_test_meals_eval"],
                **{k: v for k, v in r[EVAL].items() if not k.startswith("_")},
                delays=json.dumps([round(x, 1) for x in r[EVAL]["_delays"]])))
            meta.append(dict(subject=sb["subject"], group=sb["group"], variant=name,
                             M=len(T), delay=int(d), TH=float(th), n_curves=n_curves,
                             n_donors=n_donors))
        print(sb["subject"], flush=True)

    per = pd.DataFrame(rows)
    per.to_csv(OUT / "per_subject.csv", index=False)
    pd.DataFrame(meta).to_csv(OUT / "templates_thresholds.csv", index=False)

    summ = []
    for var, df in per.groupby("variant"):
        for g, dg in [("all", df)] + list(df.groupby("group")):
            p = R.pooled(dg)
            p["scored_hours"] = dg.scored_hours.sum()
            p["FP_per_10_scored_h"] = 10 * p["FP"] / p["scored_hours"]
            p["TH_median"] = dg.TH.median()
            p["M_median"] = dg.M.median()
            p["n_subjects"] = dg.subject.nunique()
            p["n_meals_eval"] = int(dg.n_meals_eval.sum())
            summ.append(dict(variant=var, evaluation=EVAL, group=g, **p))
    summ = pd.DataFrame(summ)
    summ.to_csv(OUT / "summary.csv", index=False)

    order = ["persTMA", "pop_mixed", "pop_grouped", "mixT_grpTH", "grpT_mixTH"]
    cols = ["variant", "sensitivity", "precision", "F1", "FP_per_day", "TP", "FP", "FN",
            "n_subjects", "n_meals_eval", "TH_median", "M_median"]
    main_tbl = (summ[summ.group == "all"].set_index("variant").loc[order].reset_index())[cols]
    main_tbl.to_csv(OUT / "population_variants.csv", index=False)
    print(f"\nbreakfast+lunch truth, window + dinner/snack mask, {EVAL}, test period\n")
    print(main_tbl.round(3).to_string(index=False))
    print("\nby glycaemic group:")
    g = summ[summ.group != "all"]
    print(g[g.variant.isin(order[:3])][["variant", "group", "sensitivity", "precision", "F1",
                                        "FP_per_day", "TP", "FP", "n_subjects", "n_meals_eval"]]
          .sort_values(["group", "variant"]).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
