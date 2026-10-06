"""Breakfast+lunch evaluation with per-record masking of logged dinners/snacks.

Builds on run_bl.py (results/bl/, not re-run or overwritten). The daily scoring
window 04:43-17:31 is unchanged. In addition, every logged dinner/snack row
(raw rows, before the 30-min merge, so before/after photos are both covered)
masks the span [record - 60 min, record + 120 min]: events whose scored time
(cc peak for native, onset estimate for C05) falls there are not evaluated -
neither TP nor FP. This is the same not-evaluated treatment the pipeline uses
near CGM gaps (tma.silence_mask), with the trigger swapped to "a known dinner/
snack that is excluded from the ground truth". Like the scoring window, it is
applied at each protocol's scored time via evaluate_test(outside=...).

Carve-out: the mask never covers a breakfast/lunch's own scoring range
[meal - 15, meal + 120] min, so no breakfast/lunch loses its TP window and the
ground-truth sample is unchanged. `nocarve` shows what happens without it.

Configurations (outputs in results/bl_maskDS/):
* window      - fixed window only; same detector as results/bl `bl` (template
                from B/L training meals, TH read from results/bl) -> reproduces
                the earlier numbers; baseline for the comparison
* mask        - MAIN: same detector, window + per-record dinner/snack mask.
                Only the scoring changes, so FP sources compare directly.
* mask_nocarve- as mask, without the breakfast/lunch carve-out
* mask_retuned- as mask, with TH re-tuned under the mask (deployment view)
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
import run_tma as R  # noqa: E402
import tma  # noqa: E402

OUT = HERE / "results" / "bl_maskDS"
MASK_BEFORE_MIN, MASK_AFTER_MIN = 60, 120
CONFIGS = ["window", "mask", "mask_nocarve", "mask_retuned"]


def raw_dinner_snack_times(subject):
    d = pd.read_csv(cgmacros.CGMACROS_DIR / subject / f"{subject}.csv")
    d.columns = [c.strip() for c in d.columns]
    m = d[d["Meal Type"].notna()].copy()
    m["mt"] = m["Meal Type"].map(cgmacros._normalize_meal_type)
    return pd.DatetimeIndex(pd.to_datetime(m[~m.mt.isin(B.BL_TYPES)]["Timestamp"])).sort_values()


def record_mask(t, triggers, before_min, after_min):
    """True for samples within [trigger - before, trigger + after] of any trigger
    time; the silence_mask pattern with a time-based trigger."""
    m = np.zeros(len(t), bool)
    for x in triggers:
        lo = np.searchsorted(t.values, (x - pd.Timedelta(minutes=before_min)).to_datetime64())
        hi = np.searchsorted(t.values, (x + pd.Timedelta(minutes=after_min)).to_datetime64(), side="right")
        m[lo:hi] = True
    return m


def ds_mask(sb, carve):
    m = record_mask(sb["t"], sb["ds_raw"], MASK_BEFORE_MIN, MASK_AFTER_MIN)
    if carve:
        m &= ~record_mask(sb["t"], sb["meal_times"], B.TP_BEFORE_MIN, B.TP_AFTER_MIN)
    return m


def scored_hours(sb, not_eval, c05):
    """Hours of the test period that are actually scored."""
    t = sb["t"][sb["split"]:]
    keep = ~not_eval[sb["split"]:]
    if c05:
        h = t.hour
        keep &= (h >= 7) & (h < 22)
    return keep.sum() * 5 / 60


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bio = cgmacros.load_bio().set_index("subject")
    subjects = [R.prepare(s) for s in cgmacros.list_subjects()]
    meals = {s["subject"]: B.load_typed_meals(s) for s in subjects}
    win = B.derive_window(meals)
    prev_win = json.load(open(HERE / "results" / "bl" / "window.json"))
    assert (win["start_min"], win["end_min"]) == (prev_win["start_min"], prev_win["end_min"])
    prev_th = json.load(open(HERE / "results" / "bl" / "templates_thresholds.json"))

    sbs = []
    for s in subjects:
        sb = B.attach_bl(s, meals[s["subject"]], win)
        sb["group"] = bio.loc[s["subject"], "group"]
        sb["ds_raw"] = raw_dinner_snack_times(s["subject"])
        sb["ds_times"] = sb["ds_raw"]              # FP attribution uses raw rows too
        tr_bl = sb["meal_idx"][sb["meal_idx"] < s["split"]]
        sb["curves_bl"], _ = tma.select_template_curves(
            s["g"], tr_bl, R.N_CURVES, all_meal_idx=s["meal_idx"])
        sb["mask_carve"] = ds_mask(sb, True)
        sb["mask_nocarve"] = ds_mask(sb, False)
        sbs.append(sb)

    rows, attrib, lunch_check = [], [], []
    for i, sb in enumerate(sbs):
        others = [o for j, o in enumerate(sbs) if j != i]
        test = ~(sb["meal_idx"] < sb["split"])
        # breakfasts/lunches whose own scoring range touches a dinner/snack mask
        own = [record_mask(sb["t"], [m], B.TP_BEFORE_MIN, B.TP_AFTER_MIN) for m in sb["meal_times"]]
        touched = np.array([bool((o & sb["mask_nocarve"]).any()) for o in own], bool)
        for ver in ["persTMA", "popTMA"]:
            if ver == "persTMA":
                if len(sb["curves_bl"]) < 2:
                    continue
                T, d = tma.average_aligned(sb["curves_bl"], 1.0)
            else:
                T, d = tma.average_aligned([c for o in others for c in o["curves_bl"]], 0.5)
            th_prev = prev_th[sb["subject"]][ver]["TH"]
            for cfg in CONFIGS:
                if cfg == "window":
                    mask, th = np.zeros(len(sb["t"]), bool), th_prev
                elif cfg == "mask_nocarve":
                    mask, th = sb["mask_nocarve"], th_prev
                else:
                    mask, th = sb["mask_carve"], th_prev
                if cfg == "mask_retuned":
                    donors = [sb] if ver == "persTMA" else others
                    items = []
                    for o in donors:
                        cc_o, sil_o, bad_o, tr_o = B.portion_bl(o, T, d, False)
                        items.append((cc_o, o["meal_idx"][tr_o & ~bad_o],
                                      sil_o | o["outside"] | o["mask_carve"], 0, o["split"]))
                    th = tma.grid_search_threshold(items, R.N_GRID)[0]
                cc, sil, bad, is_tr = B.portion_bl(sb, T, d, False)
                not_eval = sb["outside"] | mask
                r = R.evaluate_test(sb, cc, sil, bad, is_tr, th, len(T), outside=not_eval)
                typ = dict(zip(sb["meal_times"], sb["meal_types"]))
                for ev in ["C05", "C05-15", "native"]:
                    row = dict(subject=sb["subject"], group=sb["group"], config=cfg, version=ver,
                               evaluation=ev, TH=th, M=len(T),
                               scored_hours=scored_hours(sb, not_eval, ev.startswith("C05")),
                               n_test_BL_eval=int((test & ~bad).sum()),
                               n_test_lunch_eval=int((test & ~bad & (sb["meal_types"] == "lunch")).sum()),
                               n_test_lunch_touched=int((test & ~bad & touched & (sb["meal_types"] == "lunch")).sum()))
                    row.update({k: v for k, v in r[ev].items() if not k.startswith("_")})
                    tp_types = [typ[m] for m in r[ev]["_tp_meal_times"]]
                    row["TP_breakfast"], row["TP_lunch"] = tp_types.count("breakfast"), tp_types.count("lunch")
                    touched_times = set(sb["meal_times"][test & ~bad & touched])
                    row["TP_lunch_touched"] = sum(1 for m in r[ev]["_tp_meal_times"]
                                                  if m in touched_times and typ[m] == "lunch")
                    row["delays"] = json.dumps([round(x, 1) for x in r[ev]["_delays"]])
                    rows.append(row)
                attrib.append(dict(subject=sb["subject"], group=sb["group"], config=cfg, version=ver,
                                   FP=r["C05"]["FP"], **B.attribute_fps(sb, r["C05"]["_fp_times"])))
        print(sb["subject"], flush=True)

    per = pd.DataFrame(rows)
    per.to_csv(OUT / "per_subject.csv", index=False)
    att = pd.DataFrame(attrib)
    att.to_csv(OUT / "fp_attribution_per_subject.csv", index=False)
    cats = ["FP", "near_logged_dinner_snack", "0_60min_before_logged_BL", "120_240min_after_logged_BL", "other"]
    fa = att.groupby(["version", "config"])[cats].sum()
    for c in cats[1:]:
        fa[c + "_pct"] = (100 * fa[c] / fa.FP).round(1)
    fa.to_csv(OUT / "fp_attribution.csv")

    summ = []
    for (cfg, ver, ev), df in per.groupby(["config", "version", "evaluation"]):
        for g, dg in [("all", df)] + list(df.groupby("group")):
            p = R.pooled(dg)
            p["scored_hours"] = dg.scored_hours.sum()
            p["FP_per_10_scored_h"] = 10 * p["FP"] / p["scored_hours"]
            p["n_lunch_eval"] = int(dg.n_test_lunch_eval.sum())
            p["n_lunch_touched"] = int(dg.n_test_lunch_touched.sum())
            p["TP_lunch"] = int(dg.TP_lunch.sum())
            p["TP_lunch_touched"] = int(dg.TP_lunch_touched.sum())
            summ.append(dict(config=cfg, version=ver, evaluation=ev, group=g, **p))
    summ = pd.DataFrame(summ)
    summ.to_csv(OUT / "summary.csv", index=False)
    json.dump({"window": [prev_win["start"], prev_win["end"]], "mask_before_min": MASK_BEFORE_MIN,
               "mask_after_min": MASK_AFTER_MIN, "carve_out_min": [-B.TP_BEFORE_MIN, B.TP_AFTER_MIN],
               "n_raw_dinner_snack_rows": int(sum(len(s["ds_raw"]) for s in sbs))},
              open(OUT / "settings.json", "w"), indent=1)

    show = summ[(summ.group == "all") & summ.evaluation.isin(["C05", "native"])]
    print(show[["version", "evaluation", "config", "sensitivity", "FP_per_day", "FP_per_10_scored_h", "scored_hours",
                "precision", "F1", "delay_mean_min", "TP", "FP", "FN", "n_lunch_eval", "TP_lunch",
                "n_lunch_touched", "TP_lunch_touched"]].round(3).to_string())
    print(fa.to_string())


if __name__ == "__main__":
    main()
