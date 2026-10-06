"""Spot check (2026-10-06): smoothed curve, wavelet maxima and minima, candidate segments and the
chosen PPGR, one participant-day per glycaemic group, main run (10 mg/dL), refractory, Route B.

Writes methods/lim/results/spot_check.md (plain ASCII).

Usage: python methods/lim/src/spot_check.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from common.evaluation import detectors, load_config  # noqa: E402
from common.evaluation.data import build_cohort  # noqa: E402
from common.evaluation.report import write_ascii  # noqa: E402
from methods.lim.src import lim as L  # noqa: E402

RES = Path(__file__).resolve().parents[1] / "results"
OUT = RES / "protocol_v1"
GROUPS = ["healthy", "prediabetes", "T2D"]


def hm(t):
    return f"{t:%H:%M}"


def main():
    cfg = load_config(*detectors.config_paths("lim"))
    cohort = build_cohort(cfg)
    det = pd.read_csv(OUT / "refractory" / "detections.csv", parse_dates=["detection_time"])
    det = det[(det.rule == "ours") & (det.route == "B")]
    fx = {**L.fixed_params(cfg), "min_height": 10.0}
    meals = cohort.meals
    kept = det[det.status.isin(["TP", "FP"])]
    Lines = ["# Lim spot check: wavelet candidates and the chosen PPGR", "",
             "Main run (10 mg/dL), refractory, Route B. One participant-day per group: the first day with at "
             "least one TP and one FP (else the first with a TP). Per window: every candidate segment (wavelet "
             "maximum -> next minimum), its start, peak and height (QC'd glucose), and the chosen PPGR. "
             "Below, the smoothed curve and the wavelet coefficient every 15 min from 06:00 to 16:30, with "
             "local maxima (+) and minima (-) of the coefficient.", ""]
    for g in GROUPS:
        st = kept[kept.group == g].groupby("day_id").status.agg(set)
        ok = sorted(st[st.map(lambda s: {"TP", "FP"} <= s)].index) or sorted(st[st.map(lambda s: "TP" in s)].index)
        day_id = ok[0]
        t, y = cohort.day_series(day_id, 5)
        gs, c = L.coefficients(y, fx)
        cands = L.candidates(t, y, fx)
        chosen = L.choose(cands, fx["min_height"])
        lm = meals[meals.day_id == day_id]
        Lines += [f"## {g}: {day_id}", "",
                  "Logged meals: " + ", ".join(f"{r.meal_type} {hm(r.start)}" for r in lm.itertuples()), ""]
        x = det[det.day_id == day_id]
        Lines += ["Kept detections: " + (", ".join(f"{hm(r.detection_time)} {r.status}"
                                                    + (f" (delay {r.delay_min:.0f} min)" if r.status == "TP" else "")
                                                    for r in x.itertuples()) or "none"), "", "```",
                  "window     max    start  peak   end    height  chosen"]
        for cd in cands:
            ch = any(cd is c2 for c2 in chosen)
            Lines.append(f"{cd['window']:9s} {hm(t[cd['max']])}  {hm(t[cd['start']])}  {hm(t[cd['peak']])}  "
                         f"{hm(t[cd['end']])}  {cd['height']:6.1f}  {'yes' if ch else ''}"
                         + ("" if cd["start_in_window"] else "  (start outside window)"))
        Lines += ["```", "", "```", "time     CGM  smoothed   coef"]
        maxi, mini = set(L._local_max(c)), set(L._local_min(c))
        for k in range(len(t)):
            mins = t[k].hour * 60 + t[k].minute
            if 360 <= mins <= 990 and (k % 3 == 0 or k in maxi or k in mini):
                mark = "+" if k in maxi else ("-" if k in mini else "")
                Lines.append(f"{hm(t[k])}  {y[k]:6.1f}  {gs[k]:7.1f}  {c[k]:6.2f} {mark}")
        Lines += ["```", ""]
    write_ascii(RES / "spot_check.md", "\n".join(Lines) + "\n")
    print(f"wrote {RES / 'spot_check.md'}")


if __name__ == "__main__":
    main()
