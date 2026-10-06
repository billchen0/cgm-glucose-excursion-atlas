"""TMA evaluated on breakfast + lunch only (the study-provided standardized meals).

CGMacros breakfasts (protein shakes) and lunches (Chipotle) are prescribed by the
protocol with known composition; dinners and snacks are self-chosen and
self-logged (Das 2025). This run scores TMA against breakfast+lunch only, to
separate ground-truth noise from algorithm limits. The all-meal outputs in
results/ are untouched; everything here goes to results/bl/.

* CGM is never truncated: filtering and cross-correlation run on the full trace.
* Scoring window: a daily clock window [WIN_START, WIN_END] derived from the logged
  meal times (see derive_window). Events whose scored time (cc peak for native,
  onset estimate for C05) falls outside it are not evaluated.
* Breakfast/lunch whose [-15, +120] min scoring range does not fit inside the
  window are handled like the pipeline's non-evaluable meals (`to_be_silenced`):
  dropped from the ground truth and their window silenced.
* C05's 22:00-07:00 exclusion still applies on top, as in the all-meal run.
* The 60:40 split point is the one from the all-meal run, so the test periods match.

Detector configurations:
* rescore  - the all-meal detector unchanged (template from all training meals,
             TH copied from results/templates_thresholds.json); only the scoring
             changes. Isolates the effect of ground truth + window.
* bl       - MAIN new version: template from breakfast/lunch training meals,
             TH grid-searched against breakfast/lunch ground truth in the window.
* bl_silDS - diagnostic: as `bl`, plus the windows of logged dinners/snacks that
             fall inside the scoring window are silenced too (not evaluated).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.data import cgmacros  # noqa: E402
from common.evaluation import evaluation  # noqa: E402
import run_tma as R  # noqa: E402
import tma  # noqa: E402

OUT = HERE / "results" / "bl"
BL_TYPES = ("breakfast", "lunch")
TP_BEFORE_MIN, TP_AFTER_MIN = 15, 120      # widest TP range of the two protocols
BREAKFAST_Q, LUNCH_Q = 0.01, 0.975
C05_NIGHT = (7 * 60, 22 * 60)


def tod(ts):
    ts = pd.DatetimeIndex(ts)
    return np.asarray(ts.hour * 60 + ts.minute)


def load_typed_meals(s):
    m = cgmacros.load_subject(s["subject"])["meals"]
    m = m[(m.Timestamp >= s["t"][0]) & (m.Timestamp <= s["t"][-1])].reset_index(drop=True)
    return m


def derive_window(meals_by_subject):
    """Start = 1st percentile of breakfast clock time - 15 min (native pre-meal
    tolerance). End = 97.5th percentile of lunch clock time + 120 min (TP window).
    Returns minutes after midnight plus the raw quantiles."""
    allm = pd.concat(meals_by_subject.values())
    b = tod(allm[allm["Meal Type"] == "breakfast"].Timestamp)
    l = tod(allm[allm["Meal Type"] == "lunch"].Timestamp)
    bq, lq = np.quantile(b, BREAKFAST_Q), np.quantile(l, LUNCH_Q)
    return {"start_min": int(np.floor(bq - TP_BEFORE_MIN)), "end_min": int(np.ceil(lq + TP_AFTER_MIN)),
            "breakfast_q01_min": float(bq), "lunch_q975_min": float(lq),
            "lunch_quantiles_h": {str(q): round(float(np.quantile(l, q)) / 60, 2)
                                  for q in [0, .01, .05, .25, .5, .75, .95, .975, .99, 1]},
            "breakfast_quantiles_h": {str(q): round(float(np.quantile(b, q)) / 60, 2)
                                      for q in [0, .01, .05, .5, .95, .99, 1]},
            "n_breakfast": int(len(b)), "n_lunch": int(len(l))}


def hhmm(m):
    return f"{int(m) // 60:02d}:{int(m) % 60:02d}"


def attach_bl(s, meals, win):
    t = s["t"]
    bl = meals[meals["Meal Type"].isin(BL_TYPES)]
    ds = meals[~meals["Meal Type"].isin(BL_TYPES)]
    bl_times = pd.DatetimeIndex(bl.Timestamp)
    m_tod = tod(bl_times)
    fits = (m_tod - TP_BEFORE_MIN >= win["start_min"]) & (m_tod + TP_AFTER_MIN <= win["end_min"])
    sb = dict(s)
    sb.update(meal_idx=np.searchsorted(t.values, bl_times.values), meal_times=bl_times,
              meal_types=bl["Meal Type"].to_numpy(), fits_window=fits,
              ds_idx=np.searchsorted(t.values, pd.DatetimeIndex(ds.Timestamp).values),
              ds_times=pd.DatetimeIndex(ds.Timestamp),
              all_idx=s["meal_idx"],
              outside=tma.outside_window_mask(t, win["start_min"], win["end_min"]))
    return sb


def portion_bl(sb, template, delay, silence_ds):
    M = len(template)
    cc = tma.cross_correlation(sb["g"], sb["train_mean"], template, delay)
    bad = tma.non_evaluable_meals(sb["g"], sb["meal_idx"], M) | ~sb["fits_window"]
    silenced = sb["meal_idx"][bad]
    if silence_ds:
        in_win = ~sb["outside"][np.clip(sb["ds_idx"], 0, len(cc) - 1)]
        silenced = np.r_[silenced, sb["ds_idx"][in_win]]
    sil = tma.silence_mask(sb["g"], silenced, len(cc))
    is_train = sb["meal_idx"] < sb["split"]
    return cc, sil, bad, is_train


def tune(items_src, template, delay, silence_ds):
    items = []
    for o in items_src:
        cc, sil, bad, tr = portion_bl(o, template, delay, silence_ds)
        items.append((cc, o["meal_idx"][tr & ~bad], sil | o["outside"], 0, o["split"]))
    return tma.grid_search_threshold(items, R.N_GRID)[0]


def attribute_fps(sb, fp_times):
    """C05 FPs (onset times, all inside the window) by probable source."""
    out = {"near_logged_dinner_snack": 0, "0_60min_before_logged_BL": 0,
           "120_240min_after_logged_BL": 0, "other": 0}
    for f in pd.DatetimeIndex(fp_times):
        dd = (f - sb["ds_times"]).total_seconds() / 60
        db = (f - sb["meal_times"]).total_seconds() / 60
        if np.any((dd >= -15) & (dd <= 120)):
            out["near_logged_dinner_snack"] += 1
        elif np.any((db >= -60) & (db <= 0)):
            out["0_60min_before_logged_BL"] += 1
        elif np.any((db > 120) & (db <= 240)):
            out["120_240min_after_logged_BL"] += 1
        else:
            out["other"] += 1
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bio = cgmacros.load_bio().set_index("subject")
    subjects = [R.prepare(s) for s in cgmacros.list_subjects()]
    meals = {s["subject"]: load_typed_meals(s) for s in subjects}
    win = derive_window(meals)
    win.update(start=hhmm(win["start_min"]), end=hhmm(win["end_min"]))
    json.dump(win, open(OUT / "window.json", "w"), indent=1)
    print("scoring window", win["start"], "-", win["end"])

    old = json.load(open(HERE / "results" / "templates_thresholds.json"))
    sbs = []
    for s in subjects:
        sb = attach_bl(s, meals[s["subject"]], win)
        sb["group"] = bio.loc[s["subject"], "group"]
        tr_all = s["meal_idx"][s["meal_idx"] < s["split"]]
        sb["curves_all"], _ = tma.select_template_curves(s["g"], tr_all, R.N_CURVES)
        tr_bl = sb["meal_idx"][sb["meal_idx"] < s["split"]]
        sb["curves_bl"], sb["rule_bl"] = tma.select_template_curves(
            s["g"], tr_bl, R.N_CURVES, all_meal_idx=s["meal_idx"])
        sbs.append(sb)

    rows, attrib, tmpl = [], [], {}
    for i, sb in enumerate(sbs):
        others = [o for j, o in enumerate(sbs) if j != i]
        for cfg in ["rescore", "bl", "bl_silDS"]:
            ckey = "curves_all" if cfg == "rescore" else "curves_bl"
            silds = cfg == "bl_silDS"
            for ver in ["persTMA", "popTMA"]:
                if ver == "persTMA":
                    if len(sb[ckey]) < 2:
                        continue
                    T, d = tma.average_aligned(sb[ckey], 1.0)
                    th = old[sb["subject"]]["persTMA"]["TH"] if cfg == "rescore" else tune([sb], T, d, silds)
                else:
                    T, d = tma.average_aligned([c for o in others for c in o[ckey]], 0.5)
                    th = old[sb["subject"]]["popTMA"]["TH"] if cfg == "rescore" else tune(others, T, d, silds)
                cc, sil, bad, is_tr = portion_bl(sb, T, d, silds)
                r = R.evaluate_test(sb, cc, sil, bad, is_tr, th, len(T), outside=sb["outside"])
                test = ~is_tr
                for ev in ["C05", "C05-15", "native"]:
                    row = dict(subject=sb["subject"], group=sb["group"], config=cfg, version=ver,
                               evaluation=ev, TH=th, M=len(T),
                               n_test_BL_logged=int(test.sum()),
                               n_test_BL_eval=int((test & ~bad).sum()),
                               n_test_BL_outside_window=int((test & ~sb["fits_window"]).sum()),
                               n_test_breakfast_eval=int((test & ~bad & (sb["meal_types"] == "breakfast")).sum()),
                               n_test_lunch_eval=int((test & ~bad & (sb["meal_types"] == "lunch")).sum()))
                    row.update({k: v for k, v in r[ev].items() if not k.startswith("_")})
                    # per meal type: TP among scored meals of that type
                    typ = dict(zip(sb["meal_times"], sb["meal_types"]))
                    tp_types = [typ[m] for m in r[ev]["_tp_meal_times"]]
                    scored = sb["meal_times"][test & ~bad]
                    if ev.startswith("C05"):
                        scored = scored[~evaluation.in_night(scored)] if len(scored) else scored
                    sc_types = [typ[m] for m in scored]
                    for mt in BL_TYPES:
                        row[f"TP_{mt}"] = tp_types.count(mt)
                        row[f"n_{mt}_scored"] = sc_types.count(mt)
                    row["delays"] = json.dumps([round(x, 1) for x in r[ev]["_delays"]])
                    rows.append(row)
                if cfg in ("rescore", "bl"):
                    attrib.append(dict(subject=sb["subject"], group=sb["group"], config=cfg, version=ver,
                                       FP=r["C05"]["FP"], **attribute_fps(sb, r["C05"]["_fp_times"])))
                if cfg == "bl":
                    tmpl.setdefault(sb["subject"], {})[ver] = {
                        "template": np.round(T, 2).tolist(), "delay": int(d), "M": len(T), "TH": float(th),
                        **({"n_curves": len(sb["curves_bl"]), "curve_rule": sb["rule_bl"]} if ver == "persTMA" else {})}
        print(sb["subject"], flush=True)

    per = pd.DataFrame(rows)
    per.to_csv(OUT / "per_subject.csv", index=False)
    json.dump(tmpl, open(OUT / "templates_thresholds.json", "w"), indent=1)
    att = pd.DataFrame(attrib)
    att.to_csv(OUT / "fp_attribution_per_subject.csv", index=False)
    att.groupby(["config", "version"])[["FP", "near_logged_dinner_snack", "0_60min_before_logged_BL", "120_240min_after_logged_BL", "other"]] \
        .sum().to_csv(OUT / "fp_attribution.csv")

    # scored hours per day: native = window; C05 = window intersected with 07:00-22:00
    hours = {"native": (win["end_min"] - win["start_min"]) / 60,
             "C05": (min(win["end_min"], C05_NIGHT[1]) - max(win["start_min"], C05_NIGHT[0])) / 60}
    hours["C05-15"] = hours["C05"]
    summ = []
    for (cfg, ver, ev), df in per.groupby(["config", "version", "evaluation"]):
        for g, dg in [("all", df)] + list(df.groupby("group")):
            p = R.pooled(dg)
            p["FP_per_10_scored_h"] = p["FP"] / (p["days"] * hours[ev]) * 10
            summ.append(dict(config=cfg, version=ver, evaluation=ev, group=g, scored_h_per_day=hours[ev], **p))
    summ = pd.DataFrame(summ)
    summ.to_csv(OUT / "summary.csv", index=False)

    # side-by-side with the all-meal run (read from its own outputs, not recomputed)
    allm = pd.read_csv(HERE / "results" / "summary.csv")
    allm_hours = {"native": 24.0, "C05": 15.0, "C05-15": 15.0}
    allm["FP_per_10_scored_h"] = allm.apply(lambda r: r.FP / (r.days * allm_hours[r.evaluation]) * 10, axis=1)
    allm["config"] = "all_meals"
    cols = ["config", "version", "evaluation", "group", "sensitivity", "FP_per_day", "FP_per_10_scored_h",
            "delay_mean_min", "delay_median_min", "precision", "F1", "TP", "FP", "FN", "days"]
    comp = pd.concat([allm[cols], summ[cols]])
    comp = comp[comp.evaluation.isin(["C05", "native"])].sort_values(["version", "evaluation", "group", "config"])
    comp.to_csv(OUT / "comparison_all_vs_bl.csv", index=False)

    # sample sizes (config bl, persTMA, C05 rows = one per subject)
    x = per[(per.config == "bl") & (per.version == "popTMA") & (per.evaluation == "C05")]
    size = []
    for g, dg in [("all", x)] + list(x.groupby("group")):
        size.append({"group": g, "n_subjects": dg.subject.nunique(),
                     "subjects_with_eval_test_meals": int((dg.n_test_BL_eval > 0).sum()),
                     "test_BL_logged": int(dg.n_test_BL_logged.sum()),
                     "test_BL_outside_window": int(dg.n_test_BL_outside_window.sum()),
                     "test_BL_eval": int(dg.n_test_BL_eval.sum()),
                     "test_breakfast_eval": int(dg.n_test_breakfast_eval.sum()),
                     "test_lunch_eval": int(dg.n_test_lunch_eval.sum()),
                     "test_BL_scored_C05": int(dg.TP.sum() + dg.FN.sum()),
                     "test_days": round(float(dg.days.sum()), 1)})
    pd.DataFrame(size).to_csv(OUT / "sample_sizes.csv", index=False)

    print(comp[comp.group == "all"].round(3).to_string())
    print(pd.DataFrame(size).to_string())
    print(att.groupby(["config", "version"])[["FP", "near_logged_dinner_snack", "0_60min_before_logged_BL", "120_240min_after_logged_BL", "other"]].sum().to_string())
    bt = per.groupby(["config", "version", "evaluation"])[["TP_breakfast", "n_breakfast_scored", "TP_lunch", "n_lunch_scored"]].sum()
    bt["sens_breakfast"] = bt.TP_breakfast / bt.n_breakfast_scored
    bt["sens_lunch"] = bt.TP_lunch / bt.n_lunch_scored
    bt.to_csv(OUT / "sensitivity_by_meal_type.csv")
    print(bt.round(3).to_string())
    print("persTMA missing (fewer than 2 template curves):",
          sorted(set(per.subject) - set(per[per.version == "persTMA"].subject.unique()))
          or {c: sorted(set(per.subject) - set(per[(per.version == "persTMA") & (per.config == c)].subject))
              for c in per.config.unique()})


if __name__ == "__main__":
    main()
