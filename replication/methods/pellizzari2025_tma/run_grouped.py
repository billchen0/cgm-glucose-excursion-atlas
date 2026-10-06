"""popTMA stratified by glycaemic group (healthy / prediabetes / T2D).

Tests the hypothesis from the first run: popTMA fails on healthy subjects because
the mixed population template is dominated by the large, slow T2D/prediabetes
responses.

Variants (all leave-one-subject-out; the held-out subject's meal log is never used):
* mixed    - the first run's popTMA: template + TH from the other 44 subjects
* grouped  - template + TH from the other subjects of the SAME group
* sizematch- control for pool size: template + TH from k random other subjects of
             ANY group, k = size of the grouped donor pool; R random draws
* cross    - template from group A donors, TH tuned on the subject's own group
             donors (with that template): only the template shape changes
* mixT_grpTH - mixed template (other 44), TH tuned on own-group donors only:
             only the threshold is stratified
* halfsplit- stability: within a group, template + TH from a random half of the
             subjects, evaluated on the other half; R random splits

Group labels: HbA1c from bio.csv with the CGMacros paper's cut-offs
(< 5.7 healthy, 5.7-6.4 prediabetes, > 6.4 T2D; Das 2025) -> 15 / 16 / 14.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.data import cgmacros  # noqa: E402
import run_tma as R  # noqa: E402
import tma  # noqa: E402

SELECTION = sys.argv[1] if len(sys.argv) > 1 else "rise"   # "rise" | "chrono"
QUICK = SELECTION != "rise"      # chrono run: skip sizematch / halfsplit
OUT = HERE / "results" / ("grouped" if SELECTION == "rise" else f"grouped_{SELECTION}")
N_SIZEMATCH = 20
N_BOOT = 2000
GROUPS = ["healthy", "prediabetes", "T2D"]


def fold(s, template_donors, th_donors):
    """Population template from template_donors' curves, TH tuned on the pooled
    training sets of th_donors, evaluated on s's test set."""
    pool = [c for o in template_donors for c in o["curves"]]
    T, d = tma.average_aligned(pool, 0.5)
    items = []
    for o in th_donors:
        cc_o, sil_o, bad_o, tr_o = R.portion(o, T, d)
        items.append((cc_o, o["meal_idx"][tr_o & ~bad_o], sil_o, 0, o["split"]))
    th, _ = tma.grid_search_threshold(items, R.N_GRID)
    cc, sil, bad, is_tr = R.portion(s, T, d)
    res = R.evaluate_test(s, cc, sil, bad, is_tr, th, len(T))
    return res, {"template": T, "delay": int(d), "M": len(T), "TH": float(th),
                 "n_curves": len(pool), "n_donors": len(template_donors)}


def rows_from(s, res, meta, **tags):
    out = []
    for ev in ["C05", "C05-15", "native"]:
        r = dict(subject=s["subject"], group=s["group"], evaluation=ev,
                 TH=meta["TH"], M=meta["M"], n_curves=meta["n_curves"],
                 n_donors=meta["n_donors"], **tags)
        r.update({k: v for k, v in res[ev].items() if not k.startswith("_")})
        r["delays"] = json.dumps([round(x, 1) for x in res[ev]["_delays"]])
        out.append(r)
    return out


def descriptors(T, d):
    """Shape of a template: rise (peak - first sample), time to peak, fall after
    the peak by the end, total length (min)."""
    return {"rise_mgdl": float(T[d] - T[0]), "time_to_peak_min": 5 * d,
            "fall_after_peak_mgdl": float(T[d] - T[-1]), "length_min": 5 * len(T)}


def paired_bootstrap(df_a, df_b, rng):
    """Subject-level paired bootstrap of (b - a) for pooled Sens, FP/day, F1."""
    a = df_a.set_index("subject").sort_index()
    b = df_b.set_index("subject").loc[a.index]
    subs = np.arange(len(a))

    def met(x, idx):
        tp, fp, fn, days = (x[c].to_numpy()[idx].sum() for c in ["TP", "FP", "FN", "days"])
        return np.array([tp / (tp + fn), fp / days, 2 * tp / (2 * tp + fp + fn)])

    diffs = np.array([met(b, i) - met(a, i)
                      for i in (rng.choice(subs, len(subs)) for _ in range(N_BOOT))])
    point = met(b, subs) - met(a, subs)
    lo, hi = np.percentile(diffs, [2.5, 97.5], axis=0)
    return {f"d_{k}": point[j] for j, k in enumerate(["sens", "FPday", "F1"])} | \
           {f"d_{k}_ci": [round(lo[j], 3), round(hi[j], 3)] for j, k in enumerate(["sens", "FPday", "F1"])}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260921)
    bio = cgmacros.load_bio().set_index("subject")
    subjects = [R.prepare(s) for s in cgmacros.list_subjects()]
    for s in subjects:
        s["group"] = bio.loc[s["subject"], "group"]
        tr = s["meal_idx"][s["meal_idx"] < s["split"]]
        s["curves"], _ = tma.select_template_curves(s["g"], tr, R.N_CURVES, SELECTION)
    by_group = {g: [s for s in subjects if s["group"] == g] for g in GROUPS}

    rows, metas = [], []
    for s in subjects:
        others = [o for o in subjects if o is not s]
        same = [o for o in by_group[s["group"]] if o is not s]

        res, meta = fold(s, others, others)
        rows += rows_from(s, res, meta, variant="mixed", draw=0, template_group="all")
        metas.append(dict(subject=s["subject"], group=s["group"], variant="mixed",
                          **{k: meta[k] for k in ["M", "delay", "TH", "n_curves"]},
                          **descriptors(meta["template"], meta["delay"])))

        for src in GROUPS:
            donors = [o for o in by_group[src] if o is not s]
            res, meta = fold(s, donors, same)
            variant = "grouped" if src == s["group"] else "cross"
            rows += rows_from(s, res, meta, variant=variant, draw=0, template_group=src)
            metas.append(dict(subject=s["subject"], group=s["group"], variant=variant,
                              template_group=src,
                              **{k: meta[k] for k in ["M", "delay", "TH", "n_curves"]},
                              **descriptors(meta["template"], meta["delay"]),
                              template=meta["template"].round(2).tolist()))

        res, meta = fold(s, others, same)
        rows += rows_from(s, res, meta, variant="mixT_grpTH", draw=0, template_group="all")

        k = len(same)
        for r in range(0 if QUICK else N_SIZEMATCH):
            donors = [others[i] for i in rng.choice(len(others), k, replace=False)]
            res, meta = fold(s, donors, donors)
            rows += rows_from(s, res, meta, variant="sizematch", draw=r, template_group="random")
        print(s["subject"], s["group"], flush=True)

    # half-split stability
    for g in GROUPS:
        ss = by_group[g]
        for r in range(0 if QUICK else N_SIZEMATCH):
            perm = rng.permutation(len(ss))
            donors = [ss[i] for i in perm[:len(ss) // 2]]
            for i in perm[len(ss) // 2:]:
                res, meta = fold(ss[i], donors, donors)
                rows += rows_from(ss[i], res, meta, variant="halfsplit", draw=r, template_group=g)
                if i == perm[-1]:
                    metas.append(dict(subject=ss[i]["subject"], group=g, variant="halfsplit",
                                      template_group=g, draw=r,
                                      **{k: meta[k] for k in ["M", "delay", "TH", "n_curves"]},
                                      **descriptors(meta["template"], meta["delay"])))

    per = pd.DataFrame(rows)
    per.to_csv(OUT / "per_subject.csv", index=False)
    meta = pd.DataFrame(metas)
    meta.to_json(OUT / "templates.json", orient="records", indent=1)

    # ---------------- sample sizes
    size = []
    for g in GROUPS + ["all"]:
        ss = subjects if g == "all" else by_group[g]
        c05 = per[(per.variant == "mixed") & (per.evaluation == "C05")]
        c05 = c05 if g == "all" else c05[c05.group == g]
        size.append({"group": g, "n_subjects": len(ss),
                     "meals_total": int(sum(s["n_meals"] for s in ss)),
                     "meals_train": int(sum((s["meal_idx"] < s["split"]).sum() for s in ss)),
                     "test_meals_C05": int(c05.TP.sum() + c05.FN.sum()),
                     "test_days": round(float(c05.days.sum()), 1),
                     "template_curves_per_fold": (len(ss) - 1) * R.N_CURVES if g != "all" else 44 * R.N_CURVES})
    pd.DataFrame(size).to_csv(OUT / "sample_sizes.csv", index=False)

    # ---------------- pooled metrics per group
    summ = []
    for (var, tg, ev), df in per[~per.variant.isin(["sizematch", "halfsplit"])].groupby(["variant", "template_group", "evaluation"]):
        for g, dg in df.groupby("group"):
            summ.append(dict(variant=var, template_group=tg, evaluation=ev, group=g, **R.pooled(dg)))
    for (var, ev), df in per[per.variant.isin(["sizematch", "halfsplit"])].groupby(["variant", "evaluation"]):
        for g, dg in df.groupby("group"):
            draws = pd.DataFrame([R.pooled(dd) for _, dd in dg.groupby("draw")])
            rec = dict(variant=var, template_group="random" if var == "sizematch" else g,
                       evaluation=ev, group=g)
            for c in ["sensitivity", "FP_per_day", "delay_mean_min", "precision", "F1"]:
                rec[c] = draws[c].mean()
                rec[c + "_draw_range95"] = draws[c].quantile([.025, .975]).round(3).tolist()
            summ.append(rec)
    summ = pd.DataFrame(summ)
    summ.to_csv(OUT / "summary.csv", index=False)

    # ---------------- paired bootstrap: grouped vs mixed
    boots = []
    for ev in ["C05", "native"]:
        for g in GROUPS:
            a = per[(per.variant == "mixed") & (per.evaluation == ev) & (per.group == g)]
            b = per[(per.variant == "grouped") & (per.evaluation == ev) & (per.group == g)]
            boots.append(dict(evaluation=ev, group=g, **paired_bootstrap(a, b, rng)))
    pd.DataFrame(boots).to_csv(OUT / "bootstrap_grouped_minus_mixed.csv", index=False)

    # ---------------- fold-to-fold template stability
    stab = []
    for (var, g), dm in meta[meta.variant.isin(["mixed", "grouped", "halfsplit"])].groupby(["variant", "group"]):
        stab.append({"variant": var, "group": g, "folds": len(dm),
                     "TH_median": dm.TH.median(), "TH_cv": dm.TH.std() / dm.TH.mean(),
                     "M_range": [int(dm.M.min()), int(dm.M.max())],
                     "rise_range": [round(dm.rise_mgdl.min(), 1), round(dm.rise_mgdl.max(), 1)],
                     "time_to_peak_range": [int(dm.time_to_peak_min.min()), int(dm.time_to_peak_min.max())],
                     "length_range": [int(dm.length_min.min()), int(dm.length_min.max())]})
    pd.DataFrame(stab).to_csv(OUT / "template_stability.csv", index=False)

    show = summ[summ.evaluation == "C05"]
    print(show[["variant", "template_group", "group", "sensitivity", "FP_per_day", "delay_mean_min", "precision", "F1"]].round(3).to_string())
    if not QUICK:
        print(summ[summ.variant.isin(["sizematch", "halfsplit"]) & (summ.evaluation == "C05")][
            ["variant", "group", "sensitivity_draw_range95", "FP_per_day_draw_range95", "F1_draw_range95"]].to_string())
    print(pd.DataFrame(boots).to_string())
    print(pd.DataFrame(stab).to_string())
    print(pd.DataFrame(size).to_string())


if __name__ == "__main__":
    main()
