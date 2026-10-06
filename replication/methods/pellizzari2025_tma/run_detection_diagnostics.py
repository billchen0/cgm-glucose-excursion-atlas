"""Where do detections fall relative to logged meals? (diagnostic only)

No detector is re-run or changed: templates are rebuilt by the same
tma.select_template_curves/average_aligned calls and the thresholds are read from
the existing results/ JSONs, exactly as run_bl_mask.py / run_train_vs_test.py do.
Only the bookkeeping is new.

DATA SET - IMPORTANT: this pipeline has no validation split. prepare() makes a
per-subject chronological 60:40 train/test split only, so there are no untouched
validation days. This script therefore uses the TRAIN period and never touches
the test period. Consequence: the thresholds were grid-searched on these very
days, so for persTMA these detections are in-sample. popTMA's template and TH
come from the other 44 subjects (leave-one-subject-out), so for popTMA the
subject's train period is out-of-sample - the closest thing to a validation set
that exists here.

Two ground-truth versions:
* bl       - PRIMARY: breakfast+lunch only, daily window 04:43-17:31, no
             per-record dinner/snack mask (section 6 `bl` rule). The mask is
             deliberately off: it would delete snack-adjacent detections from the
             record and force the "nearest event is a snack" row to zero.
* allmeals - every logged meal incl. snacks, no window (section 1 rule).

Scoring rule for the TP/FP labels: C05-15, i.e. a detection is a TP if it is the
first unused detection in [meal - 15, meal + 120] min; a 120-min lockout follows
each TP; 22:00-07:00 detections are excluded. Labels come from
evaluation.match_events - the same function the reported numbers use. Detections
that are neither (suppressed by that lockout) are kept as a third category,
because the current rule does not charge them as FP.

Relative time = detection time - nearest logged meal start of that version's
ground truth (negative = detection precedes the log). Nearest-of-any-logged-event
(incl. snacks/dinners) is recorded separately for the summary table.

Outputs (results/diagnostics/): detections_train.csv, fp_breakdown.csv,
hist_bl.png, hist_allmeals.png.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.data import cgmacros  # noqa: E402
from common.evaluation import evaluation  # noqa: E402
import run_bl as B  # noqa: E402
import run_tma as R  # noqa: E402
import tma  # noqa: E402

OUT = HERE / "results" / "diagnostics"
WIN_BEFORE, WIN_AFTER, LOCKOUT = 15, 120, 120     # C05-15
XLIM = (-180, 240)
BIN = 5


def detections(sb, T, d, th, not_eval, period_mask):
    """Detection times of the existing detector inside the period, after the
    rule's own filters (silencing, window, night). No detector change."""
    cc = tma.cross_correlation(sb["g"], sb["train_mean"], T, d)
    M = len(T)
    bad = tma.non_evaluable_meals(sb["g"], sb["meal_idx"], M)
    if sb.get("fits_window") is not None:
        bad = bad | ~sb["fits_window"]
    sil = tma.silence_mask(sb["g"], sb["meal_idx"][bad], len(cc))
    pk = tma.detect(cc, th, sil)
    on = np.clip(tma.onset_index(pk, M), 0, len(cc) - 1)
    keep = period_mask[on] & ~not_eval[on]
    times = pd.DatetimeIndex(sb["t"][on[keep]])
    return times[~evaluation.in_night(times)] if len(times) else times, bad


def label(det_times, meal_times):
    """TP / FP / lockout-suppressed, from the same matcher the results use."""
    r = evaluation.match_events(det_times, meal_times, win_before_min=WIN_BEFORE,
                                win_after_min=WIN_AFTER, lockout_min=LOCKOUT,
                                exclude_night=True)
    tp_det = [m + pd.Timedelta(minutes=dl) for m, dl in zip(r["tp_meal_times"], r["delays"])]
    tp_pairs = dict(zip(tp_det, r["tp_meal_times"]))
    fp = set(r["fp_times"])
    out = []
    for t in pd.DatetimeIndex(det_times):
        if t in tp_pairs:
            out.append(("TP", tp_pairs[t]))
        elif t in fp:
            out.append(("FP", None))
        else:
            out.append(("lockout", None))
    return out, tp_det


def nearest(t, times, types=None):
    if len(times) == 0:
        return np.nan, None
    dt = (t - pd.DatetimeIndex(times)).total_seconds() / 60
    j = int(np.argmin(np.abs(dt)))
    return float(dt[j]), (None if types is None else types[j])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bio = cgmacros.load_bio().set_index("subject")
    subjects = [R.prepare(s) for s in cgmacros.list_subjects()]
    meals = {s["subject"]: B.load_typed_meals(s) for s in subjects}
    win = B.derive_window(meals)
    th_bl = json.load(open(HERE / "results" / "bl" / "templates_thresholds.json"))
    th_all = json.load(open(HERE / "results" / "templates_thresholds.json"))

    rows = []
    for version in ["bl", "allmeals"]:
        views = []
        for s in subjects:
            m = meals[s["subject"]]
            if version == "bl":
                sb = B.attach_bl(s, m, win)
                sb["not_eval"] = sb["outside"]                 # window only, mask OFF
                tr = sb["meal_idx"][sb["meal_idx"] < s["split"]]
                sb["curves"], _ = tma.select_template_curves(
                    s["g"], tr, R.N_CURVES, all_meal_idx=s["meal_idx"])
                sb["th"] = th_bl[s["subject"]]
            else:
                sb = dict(s, fits_window=None,
                          meal_types=m["Meal Type"].to_numpy(),
                          not_eval=np.zeros(len(s["t"]), bool))
                sb["curves"], _ = tma.select_template_curves(
                    s["g"], s["meal_idx"][s["meal_idx"] < s["split"]], R.N_CURVES)
                sb["th"] = th_all[s["subject"]]
            sb["group"] = bio.loc[s["subject"], "group"]
            sb["all_times"] = pd.DatetimeIndex(m.Timestamp)
            sb["all_types"] = list(m["Meal Type"])
            views.append(sb)

        for i, sb in enumerate(views):
            others = [o for j, o in enumerate(views) if j != i]
            period = np.arange(len(sb["t"])) < sb["split"]          # TRAIN period only
            for method in ["persTMA", "popTMA"]:
                if method == "persTMA":
                    if len(sb["curves"]) < 2 or "persTMA" not in sb["th"]:
                        continue
                    T, d = tma.average_aligned(sb["curves"], 1.0)
                else:
                    T, d = tma.average_aligned([c for o in others for c in o["curves"]], 0.5)
                th = sb["th"][method]["TH"]
                det, bad = detections(sb, T, d, th, sb["not_eval"], period)
                gt_mask = (sb["meal_idx"] < sb["split"]) & ~bad
                gt_times = pd.DatetimeIndex(sb["meal_times"][gt_mask])
                gt_types = list(np.asarray(sb["meal_types"])[gt_mask])
                lab, tp_det = label(det, gt_times)
                for t, (kind, matched_meal) in zip(pd.DatetimeIndex(det), lab):
                    dt_gt, type_gt = nearest(t, gt_times, gt_types)
                    dt_any, type_any = nearest(t, sb["all_times"], sb["all_types"])
                    prev_tp = [x for x in tp_det if x <= t]
                    rows.append(dict(
                        version=version, method=method, subject=sb["subject"], group=sb["group"],
                        detection_time=t, label=kind,
                        rel_min_nearest_gt=dt_gt, nearest_gt_type=type_gt,
                        rel_min_nearest_any=dt_any, nearest_any_type=type_any,
                        min_since_prev_tp=(np.nan if not prev_tp else
                                           (t - max(prev_tp)).total_seconds() / 60),
                        matched_meal=matched_meal))
            print(version, sb["subject"], flush=True)

    det = pd.DataFrame(rows)
    det.to_csv(OUT / "detections_train.csv", index=False)

    # ---------------- FP breakdown
    brk = []
    for (version, method), df in det.groupby(["version", "method"]):
        fp = df[df.label == "FP"]
        lock = df[df.label == "lockout"]
        brk.append({
            "version": version, "method": method,
            "detections_total": len(df), "TP": int((df.label == "TP").sum()),
            "FP": len(fp), "lockout_suppressed": len(lock),
            "FP_-30_to_0min": int(((fp.rel_min_nearest_gt >= -30) & (fp.rel_min_nearest_gt < 0)).sum()),
            "FP_+120_to_+180min": int(((fp.rel_min_nearest_gt > 120) & (fp.rel_min_nearest_gt <= 180)).sum()),
            "FP_within_120min_after_a_TP": int((fp.min_since_prev_tp <= 120).sum()),
            "lockout_within_120min_after_a_TP": int((lock.min_since_prev_tp <= 120).sum()),
            "FP_nearest_any_is_snack": int((fp.nearest_any_type == "snack").sum()),
            "FP_>180min_from_any_logged": int((fp.rel_min_nearest_any.abs() > 180).sum()),
        })
    brk = pd.DataFrame(brk)
    for c in ["FP_-30_to_0min", "FP_+120_to_+180min", "FP_within_120min_after_a_TP",
              "FP_nearest_any_is_snack", "FP_>180min_from_any_logged"]:
        brk[c + "_pct"] = (100 * brk[c] / brk.FP).round(1)
    brk.to_csv(OUT / "fp_breakdown.csv", index=False)

    # ---------------- plots
    colors = {"TP": "#2c7fb8", "FP": "#d95f0e", "lockout": "#cccccc"}
    bins = np.arange(XLIM[0], XLIM[1] + BIN, BIN)
    for version, dv in det.groupby("version"):
        methods = sorted(dv.method.unique())
        fig, axes = plt.subplots(len(methods), 1, figsize=(10, 3.1 * len(methods)), sharex=True)
        for ax, method in zip(np.atleast_1d(axes), methods):
            dm = dv[dv.method == method]
            raw = {k: dm[dm.label == k].rel_min_nearest_gt for k in colors}
            series = [v[(v >= XLIM[0]) & (v <= XLIM[1])] for v in raw.values()]
            labels = [f"{k} (n={len(v)}" + (f", {len(v) - len(s)} outside axis)" if len(v) > len(s) else ")")
                      for (k, v), s in zip(raw.items(), series)]
            ax.hist(series, bins=bins, stacked=True, color=list(colors.values()), label=labels)
            for x, ls in [(0, "-"), (120, "--")]:
                ax.axvline(x, color="k", ls=ls, lw=1)
            ax.set_title(f"{method} — {version} ground truth, train period, C05-15 labels")
            ax.set_ylabel("detections")
            ax.legend(fontsize=8)
        np.atleast_1d(axes)[-1].set_xlabel(
            "detection time - nearest logged meal start (min); 0 and +120 = current TP window")
        fig.tight_layout()
        fig.savefig(OUT / f"hist_{version}.png", dpi=150)
        plt.close(fig)

    print(brk.to_string(index=False))
    for version, dv in det.groupby("version"):
        for method, dm in dv.groupby("method"):
            q = dm[dm.label == "TP"].rel_min_nearest_gt.quantile([.25, .5, .75]).round(1).tolist()
            qf = dm[dm.label == "FP"].rel_min_nearest_gt.quantile([.25, .5, .75]).round(1).tolist()
            print(version, method, "TP rel-min IQR", q, "| FP rel-min IQR", qf)


if __name__ == "__main__":
    main()
