"""Run TMA (Pellizzari 2025) on all CGMacros subjects.

Two versions, both evaluated on the same per-subject test set (last 40 % of meals):
* persTMA - personalized template (5 training meals of the subject) + personalized
            TH (grid search on the subject's own training set). Upper-bound reference.
* popTMA  - population template + population TH, leave-one-subject-out: for
            held-out subject s the template averages the template curves of the
            other 44 subjects and TH is tuned on the union of their training sets.
            No meal log of s is used, so this is the version deployable to AI-READI.

Three evaluations of the same detections:
* C05     - Hochsmann 2026 protocol: detection = estimated meal onset, TP window
            (0, 120] min after logged start, 120-min lockout, 22:00-07:00 excluded
* C05-15  - as C05 but window [-15, 120] min (onset estimates may precede the log)
* native  - Pellizzari's own counting (evaluatePerformances.m): cc peak within
            [-15, +120] min of the meal, no lockout, no night exclusion
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.data import cgmacros  # noqa: E402
from common.evaluation import evaluation  # noqa: E402
import tma  # noqa: E402

OUT = HERE / "results"
TRAIN_FRAC = 0.6
N_CURVES = 5
N_GRID = 200


def prepare(subject):
    d = cgmacros.load_subject(subject)
    t, g_raw = d["time"], d["glucose"]
    g = tma.interpolate_short_gaps(g_raw)
    mt = pd.DatetimeIndex(d["meals"]["Timestamp"])
    mt = mt[(mt >= t[0]) & (mt <= t[-1])]
    midx = np.searchsorted(t.values, mt.values)          # first sample >= meal
    k = math.ceil(TRAIN_FRAC * len(midx))
    split = int((midx[k - 1] + midx[k]) // 2)
    return {
        "subject": subject, "t": t, "g": g, "meal_times": mt, "meal_idx": midx,
        "split": split, "train_mean": float(np.nanmean(g[:split])),
        "n_meal_rows_raw": d["n_meal_rows_raw"], "n_meals": len(midx),
        "test_days": float(np.sum(~np.isnan(g_raw[split:])) * 5 / 1440),
        "train_days": float(np.sum(~np.isnan(g_raw[:split])) * 5 / 1440),
    }


def portion(s, template, delay):
    """cc, evaluable meal masks and silence mask of subject s for a template."""
    M = len(template)
    cc = tma.cross_correlation(s["g"], s["train_mean"], template, delay)
    bad = tma.non_evaluable_meals(s["g"], s["meal_idx"], M)
    sil = tma.silence_mask(s["g"], s["meal_idx"][bad], len(cc))
    is_train = s["meal_idx"] < s["split"]
    return cc, sil, bad, is_train


def evaluate_test(s, cc, sil, bad, is_train, th, M, outside=None):
    """outside: optional bool mask over samples (tma.outside_window_mask); events
    whose scored time falls outside the scoring window are not evaluated. The
    scored time is the cc peak for `native` and the onset estimate for C05."""
    n, split = len(cc), s["split"]
    pk = tma.detect(cc, th, sil)
    pk = pk[pk >= split]
    pk_native = pk if outside is None else pk[~outside[pk]]
    on_idx = np.clip(tma.onset_index(pk, M), 0, n - 1)
    if outside is not None:
        on_idx = on_idx[~outside[on_idx]]
    test_mask = (~is_train) & (~bad)
    midx = s["meal_idx"][test_mask]
    mtimes = s["meal_times"][test_mask]
    days = s["test_days"]
    out = {}

    tp, fp, fn, pairs = tma.evaluate_native(pk_native, midx, n)
    on_err = [(s["t"][max(p - M // 2, 0)] - s["t"][m]).total_seconds() / 60 for m, p in pairs]
    peak_delay = [(s["t"][p] - s["t"][m]).total_seconds() / 60 for m, p in pairs]
    out["native"] = evaluation.summarize(tp, fp, fn, days, on_err)
    out["native"]["cc_peak_minus_meal_median_min"] = float(np.median(peak_delay)) if pairs else np.nan

    onsets = s["t"][on_idx]
    for name, before in [("C05", 0), ("C05-15", 15)]:
        r = evaluation.match_events(onsets, mtimes, win_before_min=before)
        out[name] = evaluation.summarize(r["tp"], r["fp"], r["fn"], days, r["delays"])
        out[name]["_delays"] = r["delays"]
        out[name]["_fp_times"] = r["fp_times"]
        out[name]["_tp_meal_times"] = r["tp_meal_times"]
    out["native"]["_delays"] = on_err
    tp_pk = {p for _, p in pairs}
    out["native"]["_fp_times"] = list(s["t"][[p for p in pk_native if p not in tp_pk]])
    idx2time = dict(zip(midx, mtimes))
    out["native"]["_tp_meal_times"] = [idx2time[m] for m, _ in pairs]
    out["n_test_meals_eval"] = int(test_mask.sum())
    out["n_test_meals_nonevaluable"] = int(((~is_train) & bad).sum())
    return out


def main():
    OUT.mkdir(exist_ok=True)
    subjects = [prepare(s) for s in cgmacros.list_subjects()]
    bio = cgmacros.load_bio().set_index("subject")
    print(f"{len(subjects)} subjects")

    # ---- personalized template curves from each subject's training meals
    for s in subjects:
        tr = s["meal_idx"][s["meal_idx"] < s["split"]]
        s["curves"], s["curve_rule"] = tma.select_template_curves(s["g"], tr, N_CURVES)

    rows, templates = [], {}
    for i, s in enumerate(subjects):
        rec = {"subject": s["subject"], "group": bio.loc[s["subject"], "group"],
               "n_meal_rows_raw": s["n_meal_rows_raw"], "n_meals_merged": s["n_meals"],
               "train_days": s["train_days"], "test_days": s["test_days"]}

        # ---- persTMA
        res = {}
        if len(s["curves"]) >= 2:
            T, dly = tma.average_aligned(s["curves"], 1.0)
            cc, sil, bad, is_tr = portion(s, T, dly)
            tr_meals = s["meal_idx"][is_tr & ~bad]
            th, f1_tr = tma.grid_search_threshold([(cc, tr_meals, sil, 0, s["split"])], N_GRID)
            res["persTMA"] = evaluate_test(s, cc, sil, bad, is_tr, th, len(T))
            templates.setdefault(s["subject"], {})["persTMA"] = {
                "template": T.round(2).tolist(), "delay": int(dly), "M": len(T),
                "TH": float(th), "train_F1": f1_tr, "n_curves": len(s["curves"]),
                "curve_rule": s["curve_rule"]}

        # ---- popTMA, leave-one-subject-out
        others = [o for j, o in enumerate(subjects) if j != i]
        pool = [c for o in others for c in o["curves"]]
        Tp, dp = tma.average_aligned(pool, 0.5)
        items = []
        for o in others:
            cc_o, sil_o, bad_o, tr_o = portion(o, Tp, dp)
            items.append((cc_o, o["meal_idx"][tr_o & ~bad_o], sil_o, 0, o["split"]))
        thp, f1p = tma.grid_search_threshold(items, N_GRID)
        cc, sil, bad, is_tr = portion(s, Tp, dp)
        res["popTMA"] = evaluate_test(s, cc, sil, bad, is_tr, thp, len(Tp))
        templates.setdefault(s["subject"], {})["popTMA"] = {
            "template": Tp.round(2).tolist(), "delay": int(dp), "M": len(Tp),
            "TH": float(thp), "train_F1_pooled": f1p, "n_curves_pooled": len(pool)}

        for ver, r in res.items():
            for ev in ["C05", "C05-15", "native"]:
                row = dict(rec, version=ver, evaluation=ev,
                           n_test_meals_eval=r["n_test_meals_eval"],
                           n_test_meals_nonevaluable=r["n_test_meals_nonevaluable"],
                           TH=templates[s["subject"]][ver]["TH"],
                           M=templates[s["subject"]][ver]["M"])
                row.update({k: v for k, v in r[ev].items() if not k.startswith("_")})
                row["delays"] = json.dumps([round(x, 1) for x in r[ev]["_delays"]])
                rows.append(row)
        print(f"{s['subject']}: pers TH={templates[s['subject']].get('persTMA', {}).get('TH', np.nan):.0f} "
              f"pop TH={thp:.0f} M_pop={len(Tp)}", flush=True)

    per = pd.DataFrame(rows)
    per.to_csv(OUT / "per_subject.csv", index=False)
    with open(OUT / "templates_thresholds.json", "w") as f:
        json.dump(templates, f, indent=1)
    summary = summarize_all(per)
    summary.to_csv(OUT / "summary.csv", index=False)
    print(summary.to_string())


def pooled(df):
    delays = [x for s in df["delays"] for x in json.loads(s)]
    r = evaluation.summarize(int(df.TP.sum()), int(df.FP.sum()), int(df.FN.sum()),
                             float(df.days.sum()), delays)
    q = lambda c: df[c].quantile([.25, .5, .75]).round(3).tolist()
    r.update({"n_subjects": len(df),
              "sens_subject_median_iqr": q("sensitivity"),
              "prec_subject_median_iqr": q("precision"),
              "F1_subject_median_iqr": q("F1"),
              "FPday_subject_median_iqr": q("FP_per_day")})
    return r


def summarize_all(per):
    out = []
    for (ver, ev), df in per.groupby(["version", "evaluation"]):
        out.append(dict(version=ver, evaluation=ev, group="all", **pooled(df)))
        for grp, dg in df.groupby("group"):
            out.append(dict(version=ver, evaluation=ev, group=grp, **pooled(dg)))
    return pd.DataFrame(out)


if __name__ == "__main__":
    main()
