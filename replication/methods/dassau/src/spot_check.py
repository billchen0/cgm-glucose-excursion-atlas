"""Spot check (2026-10-05): the four Dassau indicators around each detection, one
participant-day per glycaemic group, both detectors, main rule (refractory), Route B.

Reads the saved protocol_v1 outputs and re-runs the indicators with the fold's locked
parameters. Writes methods/dassau/results/spot_check.md (plain ASCII).

Usage: python methods/dassau/src/spot_check.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from common.evaluation import detectors, load_config  # noqa: E402
from common.evaluation.data import build_cohort  # noqa: E402
from common.evaluation.report import write_ascii  # noqa: E402
from methods.dassau.src import dassau as D  # noqa: E402

RES = Path(__file__).resolve().parents[1] / "results"
NAMES = ["dassau_2of3", "dassau_3of4"]
GROUPS = ["healthy", "prediabetes", "T2D"]


def pick_days(det):
    """Per group, the first day (sorted) with at least one TP and one FP under 3of4."""
    d = det[det.status.isin(["TP", "FP"])]
    out = {}
    for g in GROUPS:
        st = d[d.group == g].groupby("day_id").status.agg(set)
        ok = sorted(st[st.map(lambda s: {"TP", "FP"} <= s)].index)
        out[g] = ok[0]
    return out


def main():
    cfg = load_config(*detectors.config_paths(NAMES[0]))
    cohort = build_cohort(cfg)
    dets = {n: pd.read_csv(RES / n / "protocol_v1" / "refractory" / "detections.csv",
                           parse_dates=["detection_time"]) for n in NAMES}
    days = pick_days(dets["dassau_3of4"])
    L = ["# Dassau spot check: indicators around each detection", "",
         "Main rule refractory, Route B, our matching rule. One participant-day per group: the first "
         "day with at least one TP and one FP under 3-of-4. Each block shows minutes -2 to +6 around a "
         "detection at t(i). Columns: raw glucose g, Kalman glucose gK, BD_raw, BD_Kalman, Kalman ROC "
         "dgK and acceleration ddgK, then the indicators BD, BDK, KF, ACC (1 = true) and votes. "
         "Thresholds are the held-out fold's locked set.", ""]
    for g, day_id in days.items():
        d = cohort.days.loc[day_id]
        t, glu = cohort.day_series(day_id, 1)
        L += [f"## {g}: {day_id}", ""]
        for name in NAMES:
            variant = name.split("_")[1]
            p = json.loads((RES / name / "protocol_v1" / "refractory" / "params" /
                            "chosen_params_routeB_ours.json").read_text())
            fold = next(k for k, v in p.items() if k.startswith("fold") and d.subject in v["test_participants"])
            params = {**detectors.fixed_params(name, cfg), **p[fold]["params"]}
            sig = D.signals(glu, params)
            ind = D.indicators(sig, params)
            x = dets[name]
            x = x[(x.day_id == day_id) & ~x.status.str.startswith("removed")]
            L += [f"### {name}, {fold}: " + ", ".join(f"{k} {v:g}" for k, v in p[fold]["params"].items()), ""]
            if not len(x):
                L += ["No kept detection on this day.", ""]
            for _, r in x.iterrows():
                i = int((r.detection_time - t[0]) / pd.Timedelta(minutes=1))
                L += [f"Detection {r.detection_time:%H:%M}, status {r.status}"
                      + (f", delay {r.delay_min:.0f} min" if r.status == "TP" else ""), "", "```",
                      " min      g     gK  BD_raw   BD_K    dgK    ddgK  BD BDK KF ACC votes"]
                for j in range(max(i - 2, 0), min(i + 7, len(t))):
                    v = [int(ind[k][j]) for k in ["BD", "BDK", "KF", "ACC"]]
                    nv = v[0] + v[1] + v[3] + (v[2] if variant == "3of4" else 0)
                    L.append(f"{j - i:+4d} {glu[j]:6.1f} {sig['gk'][j]:6.1f} {sig['bd'][j]:7.2f} "
                             f"{sig['bdk'][j]:6.2f} {sig['dgk'][j]:6.2f} {sig['ddgk'][j]:7.3f}  "
                             f"{int(v[0]):2d} {int(v[1]):3d} {int(v[2]):2d} {int(v[3]):3d} {int(nv):5d}")
                L += ["```", ""]
    write_ascii(RES / "spot_check.md", "\n".join(L) + "\n")
    print(f"wrote {RES / 'spot_check.md'}")


if __name__ == "__main__":
    main()
