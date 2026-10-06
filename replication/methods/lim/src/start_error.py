"""Lim start-time error and out-of-window meals (2026-10-06), from the saved protocol outputs.

1. TP start-time error: |PPGR start - logged meal start| for TP detections (Route B, refractory,
   our matching rule), by meal and group, for the 10, 20 and 30 mg/dL runs.
2. Lim-style error: every scored meal logged inside its own window, paired with the PPGR found in
   that window on the same day (if any), regardless of TP status. This is closest to Lim's
   evaluation, which only kept days with in-window meal times.
3. Meals logged outside their window (breakfast outside 06:00-11:45, lunch outside 12:00-16:00):
   share of scored meals, and how many became FN.
Writes methods/lim/results/start_error.md and start_error.csv (plain ASCII).

Usage: python methods/lim/src/start_error.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from common.evaluation import detectors, load_config  # noqa: E402
from common.evaluation.report import md_table, write_ascii  # noqa: E402

RES = Path(__file__).resolve().parents[1] / "results"
RUNS = [("protocol_v1", "10"), ("protocol_v1_h20", "20"), ("protocol_v1_h30", "30")]
GROUPS = ["healthy", "prediabetes", "T2D"]
LIM = {"breakfast": "14 [6, 29]", "lunch": "36 [19, 63]"}          # Lim 2026, CGMacros Dexcom


def mm(s):
    h, m = map(int, s.split(":"))
    return 60 * h + m


def stat(x):
    x = pd.Series(x).dropna()
    if not len(x):
        return "", 0
    return f"{x.median():.0f} [{x.quantile(.25):.0f}, {x.quantile(.75):.0f}]", len(x)


def load(rd):
    d = pd.read_csv(RES / rd / "refractory" / "detections.csv",
                    parse_dates=["detection_time", "matched_meal_start", "excursion_start"])
    m = pd.read_csv(RES / rd / "refractory" / "meals.csv", parse_dates=["start", "detection_time"])
    return d[(d.rule == "ours") & (d.route == "B")], m[(m.rule == "ours") & (m.route == "B")]


def main():
    cfg = load_config(*detectors.config_paths("lim"))
    win = {k: (mm(v[0]), mm(v[1])) for k, v in cfg["methods"]["lim"]["windows"].items()}
    rows, L = [], ["# Lim: start-time error and out-of-window meals", ""]

    # 1 and 2, per run
    for rd, h in RUNS:
        d, m = load(rd)
        tp = d[d.status == "TP"].copy()
        tp["err"] = (tp.detection_time - tp.matched_meal_start).dt.total_seconds().abs() / 60
        # Lim-style: in-window scored meals vs the PPGR of the same window
        m = m[m.status != "not_scored"].copy()
        mmin = m.start.dt.hour * 60 + m.start.dt.minute
        m["in_window"] = [win[t][0] <= x <= win[t][1] for t, x in zip(m.meal_type, mmin)]
        dd = d[~d.status.str.startswith("removed")].copy()
        dmin = dd.detection_time.dt.hour * 60 + dd.detection_time.dt.minute
        dd["window"] = np.select([(dmin >= win[k][0]) & (dmin <= win[k][1]) for k in win], list(win), "")
        ppgr = dd.set_index(["day_id", "window"]).detection_time
        m["ppgr"] = [ppgr.get((di, t), pd.NaT) for di, t in zip(m.day_id, m.meal_type)]
        m["err_lim"] = (m.ppgr - m.start).dt.total_seconds().abs() / 60
        for meal in ["breakfast", "lunch", "all"]:
            for g in ["all"] + GROUPS:
                a = tp if meal == "all" else tp[tp.matched_meal_type == meal]
                b = m[m.in_window] if meal == "all" else m[m.in_window & (m.meal_type == meal)]
                if g != "all":
                    a, b = a[a.group == g], b[b.group == g]
                s1, n1 = stat(a.err)
                s2, n2 = stat(b.err_lim)
                rows.append(dict(min_height=h, meal=meal, group=g, tp_error=s1, tp_n=n1, lim_style_error=s2,
                                 lim_style_n=n2, in_window_meals=len(b),
                                 ppgr_found_pct=round(100 * b.ppgr.notna().mean(), 1) if len(b) else np.nan))
        if h == "10":
            out_w = m[~m.in_window]
            ow = [["all", len(m), len(out_w), f"{100 * len(out_w) / len(m):.1f}",
                   int((out_w.status == "FN").sum()), int((m.status == "FN").sum())]]
            for t in ["breakfast", "lunch"]:
                mt, ot = m[m.meal_type == t], out_w[out_w.meal_type == t]
                ow.append([t, len(mt), len(ot), f"{100 * len(ot) / len(mt):.1f}", int((ot.status == "FN").sum()),
                           int((mt.status == "FN").sum())])
    df = pd.DataFrame(rows)
    df.to_csv(RES / "start_error.csv", index=False)

    L += ["## Meals logged outside their window (10 mg/dL run)", "",
          "Route B, scored breakfast and lunch meals (refractory, our matching rule). Breakfast window "
          "06:00-11:45, lunch 12:00-16:00 (meal start time).", ""]
    L += md_table(pd.DataFrame(ow), ["Meal", "Scored meals", "Outside window", "%", "FN among them", "All FN"])
    L += ["", "## Start-time error, 10 mg/dL (main run)", "",
          "Median [IQR] absolute error (min) between PPGR start and logged meal start. TP: TP detections "
          "(match within -30 to +120 min). Lim-style: every scored meal logged inside its window, paired "
          "with the PPGR of that window on the same day (any status). Lim 2026 on CGMacros (Dexcom): "
          "breakfast 14 [6, 29], lunch 36 [19, 63]; Hall breakfast 10 [4, 19].", ""]
    t = df[df.min_height == "10"]
    L += md_table(t[["meal", "group", "tp_error", "tp_n", "lim_style_error", "lim_style_n", "ppgr_found_pct"]],
                  ["Meal", "Group", "TP error", "TP n", "Lim-style error", "Lim-style n", "% with a PPGR"])
    L += ["", "## Start-time error by threshold (all groups)", "",
          "Same definitions. Lim reports no Sens or FP/day; its sensitivity analysis compared PPGR parameters.", ""]
    t = df[df.group == "all"]
    L += md_table(t[["min_height", "meal", "tp_error", "tp_n", "lim_style_error", "lim_style_n", "ppgr_found_pct"]],
                  ["Min height", "Meal", "TP error", "TP n", "Lim-style error", "Lim-style n", "% with a PPGR"])
    write_ascii(RES / "start_error.md", "\n".join(L) + "\n")
    print(f"wrote {RES / 'start_error.md'}")


if __name__ == "__main__":
    main()
