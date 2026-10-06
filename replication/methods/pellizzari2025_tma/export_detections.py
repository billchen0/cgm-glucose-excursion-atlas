"""Export per-detection records for the dashboard glucose-curve overlay.

Additive only: this reuses the exact same machinery as run_bl_mask.py and
run_population_variants.py (main-line config = per-record dinner/snack `mask`,
evaluation `C05-15`) and writes ONE new file, `results/bl_maskDS/detections.csv`.
It does not modify or re-run any existing output; the aggregate CSVs in
results/bl_maskDS/ and results/population_variants/ are left exactly as they are.

Three template variants, all leave-one-subject-out (the held-out subject's own
meal log is never used for the population rows), matching the variants verified
in results/population_variants/:
  persTMA      subject's own template + own tuned TH (reference ceiling)
  pop_mixed    template + TH from all 44 other subjects (== results/bl_maskDS)
  pop_grouped  template + TH from the other subjects of the SAME glycaemic group
               (donor pool + tuning identical to run_population_variants.py)

Each row is a single breakfast/lunch detection with absolute timestamps, so the
dashboard can draw a translucent band per detection, filtered by subject/day:

  subject, group, version            persTMA | pop_mixed | pop_grouped
  status                             TP | FP
  meal_type                          breakfast | lunch
  meal_type_inferred                 True for FP (no logged meal; daypart guess)
  onset_time, peak_time              estimated meal-start band [onset, cc peak]
  meal_time                          logged meal start (TP only)
  win_start, win_end                 C05-15 scoring window [meal-15, meal+120] (TP only)
  delay_min                          onset - logged meal, minutes (TP only)
  date                               calendar day of onset (for the day filter)

The detection model (see run_tma.py / tma.py): a detection is a cross-correlation
peak; the estimated meal onset is peak - M//2 samples (5 min each). C05-15 counts
a detection as TP if its onset falls in [meal-15, meal+120] min of a logged
breakfast/lunch, else FP (120-min lockout, 22:00-07:00 excluded).
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
import run_bl_mask as MK  # noqa: E402
import tma  # noqa: E402

EVAL = "C05-15"          # main-line scoring window [-15, +120] min
WIN_BEFORE_MIN = 15      # matches C05-15
WIN_AFTER_MIN = 120
SAMPLE_MIN = 5           # CGMacros grid
GROUPS = ["healthy", "prediabetes", "T2D"]
OUT = HERE / "results" / "bl_maskDS" / "detections.csv"


def main():
    bio = cgmacros.load_bio().set_index("subject")
    subjects = [R.prepare(s) for s in cgmacros.list_subjects()]
    meals = {s["subject"]: B.load_typed_meals(s) for s in subjects}
    win = B.derive_window(meals)
    prev_th = json.load(open(HERE / "results" / "bl" / "templates_thresholds.json"))

    # Same subject setup as run_bl_mask.main (config "mask": carve-out on).
    sbs = []
    for s in subjects:
        sb = B.attach_bl(s, meals[s["subject"]], win)
        sb["group"] = bio.loc[s["subject"], "group"]
        sb["ds_raw"] = MK.raw_dinner_snack_times(s["subject"])
        tr_bl = sb["meal_idx"][sb["meal_idx"] < s["split"]]
        sb["curves_bl"], _ = tma.select_template_curves(
            s["g"], tr_bl, R.N_CURVES, all_meal_idx=s["meal_idx"])
        sb["mask_carve"] = MK.ds_mask(sb, True)
        sbs.append(sb)
    by_group = {g: [s for s in sbs if s["group"] == g] for g in GROUPS}

    rows = []
    for i, sb in enumerate(sbs):
        others = [o for j, o in enumerate(sbs) if j != i]
        same = [o for o in by_group[sb["group"]] if o is not sb]   # leave-one-out
        typ = dict(zip(sb["meal_times"], sb["meal_types"]))

        # Build the per-subject template plans, exactly as run_population_variants:
        # (version, template, delay, TH or None-to-tune, donors-to-tune-on).
        T_mix, d_mix = tma.average_aligned([c for o in others for c in o["curves_bl"]], 0.5)
        T_grp, d_grp = tma.average_aligned([c for o in same for c in o["curves_bl"]], 0.5)
        plans = [
            ("pop_mixed", T_mix, d_mix, prev_th[sb["subject"]]["popTMA"]["TH"], None),
            ("pop_grouped", T_grp, d_grp, None, same),  # tuned on same-group donors
        ]
        if len(sb["curves_bl"]) >= 2:
            T_p, d_p = tma.average_aligned(sb["curves_bl"], 1.0)
            plans.insert(0, ("persTMA", T_p, d_p, prev_th[sb["subject"]]["persTMA"]["TH"], None))

        for ver, T, d, th, tune_donors in plans:
            if th is None:                       # same recipe as the mixed TH
                th = B.tune(tune_donors, T, d, False)
            cc, sil, bad, is_tr = B.portion_bl(sb, T, d, False)
            not_eval = sb["outside"] | sb["mask_carve"]
            r = R.evaluate_test(sb, cc, sil, bad, is_tr, th, len(T), outside=not_eval)
            ev = r[EVAL]
            # estimated meal-start band width = onset..cc peak = M//2 samples
            span = pd.Timedelta(minutes=(len(T) // 2) * SAMPLE_MIN)

            # True positives: onset = logged meal + delay (delays align with meals)
            for meal_t, delay in zip(ev["_tp_meal_times"], ev["_delays"]):
                meal_t = pd.Timestamp(meal_t)
                onset = meal_t + pd.Timedelta(minutes=delay)
                rows.append(dict(
                    subject=sb["subject"], group=sb["group"], version=ver,
                    status="TP", meal_type=typ.get(meal_t, ""),
                    meal_type_inferred=False,
                    onset_time=onset, peak_time=onset + span, meal_time=meal_t,
                    win_start=meal_t - pd.Timedelta(minutes=WIN_BEFORE_MIN),
                    win_end=meal_t + pd.Timedelta(minutes=WIN_AFTER_MIN),
                    delay_min=round(float(delay), 1),
                ))

            # False positives: only the onset time is known (no logged meal).
            # Infer a daypart for consistent breakfast/lunch coloring; flagged.
            for onset in ev["_fp_times"]:
                onset = pd.Timestamp(onset)
                rows.append(dict(
                    subject=sb["subject"], group=sb["group"], version=ver,
                    status="FP",
                    meal_type="breakfast" if onset.hour < 11 else "lunch",
                    meal_type_inferred=True,
                    onset_time=onset, peak_time=onset + span, meal_time=pd.NaT,
                    win_start=pd.NaT, win_end=pd.NaT, delay_min=np.nan,
                ))

    df = pd.DataFrame(rows).sort_values(["subject", "version", "onset_time"])
    df["date"] = pd.to_datetime(df["onset_time"]).dt.date
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    print(f"wrote {OUT}  ({len(df)} detections)\n")
    got = df.groupby(["version", "status"]).size().unstack(fill_value=0)
    print(got.to_string())

    # Cross-check TP/FP against the already-published aggregate numbers:
    # persTMA / pop_mixed -> results/population_variants/summary.csv (== bl_maskDS),
    # pop_grouped -> the verified grouped row.
    ref = pd.read_csv(HERE / "results" / "population_variants" / "summary.csv")
    ref = ref[(ref.evaluation == EVAL) & (ref.group == "all")].set_index("variant")
    print("\ncross-check vs results/population_variants/summary.csv (all, C05-15):")
    ok = True
    for ver in ["persTMA", "pop_mixed", "pop_grouped"]:
        tp, fp = int(got.loc[ver, "TP"]), int(got.loc[ver, "FP"])
        rtp, rfp = int(ref.loc[ver, "TP"]), int(ref.loc[ver, "FP"])
        match = (tp == rtp) and (fp == rfp)
        ok &= match
        print(f"  {ver:12s} exported TP={tp:3d} FP={fp:3d} | "
              f"published TP={rtp:3d} FP={rfp:3d}  {'OK' if match else 'MISMATCH'}")
    print("ALL MATCH" if ok else "!!! MISMATCH - do not use")


if __name__ == "__main__":
    main()
