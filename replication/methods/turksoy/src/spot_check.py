"""Spot check (2026-10-05): CGM, estimated G_s, R_a, p1, p2, p4 and tau around each detection,
one participant-day per glycaemic group, main rule (refractory), Route B.

Reads the saved protocol_v1 outputs and re-runs the UKF on the day. Writes
methods/turksoy/results/spot_check.md (plain ASCII).

Usage: python methods/turksoy/src/spot_check.py
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
from methods.turksoy.src import turksoy as T  # noqa: E402

RES = Path(__file__).resolve().parents[1] / "results"
OUT = RES / "protocol_v1"
GROUPS = ["healthy", "prediabetes", "T2D"]


def main():
    cfg = load_config(*detectors.config_paths("turksoy"))
    cohort = build_cohort(cfg)
    det = pd.read_csv(OUT / "refractory" / "detections.csv", parse_dates=["detection_time"])
    p = json.loads((OUT / "refractory" / "params" / "chosen_params_routeB_ours.json").read_text())
    fx = T.fixed_params(cfg)
    kept = det[det.status.isin(["TP", "FP"])]
    L = ["# Turksoy spot check: UKF states around each detection", "",
         "Main rule refractory, Route B, our matching rule. One participant-day per group: the first "
         "day with at least one TP and one FP. Each block shows minutes -10 to +10 around a kept "
         "detection (1-min samples, every 2 min). cgm = QC'd 1-min glucose; G_s, R_a (mg/dL/min), "
         "p1, p2 (1/min), p4 and tau (min) are UKF estimates. flag = R_a > Threshold_Ra and "
         "cgm > 100 mg/dL. Threshold_Ra is the held-out fold's locked value.", ""]
    for g in GROUPS:
        st = kept[kept.group == g].groupby("day_id").status.agg(set)
        ok = sorted(st[st.map(lambda s: {"TP", "FP"} <= s)].index)
        day_id = ok[0] if ok else sorted(st.index)[0]
        d = cohort.days.loc[day_id]
        fold = next(k for k, v in p.items() if k.startswith("fold") and d.subject in v["test_participants"])
        th = p[fold]["params"]["th_ra"]
        t, glu = cohort.day_series(day_id, 1)
        s = T.ukf(glu, fx)
        L += [f"## {g}: {day_id}, {fold}: Threshold_Ra {th:g} mg/dL/min", ""]
        x = det[(det.day_id == day_id) & ~det.status.str.startswith("removed")]
        for _, r in x.iterrows():
            i = int(np.flatnonzero(t == r.detection_time)[0])
            L += [f"Detection {r.detection_time:%H:%M}, status {r.status}"
                  + (f", delay {r.delay_min:.0f} min" if r.status == "TP" else ""), "", "```",
                  " min    cgm     G_s    R_a      p1      p2     p4    tau  flag"]
            for j in range(max(i - 10, 0), min(i + 11, len(t)), 2):
                flag = s["R_a"][j] > th and glu[j] > fx["glucose_min"]
                L.append(f"{j - i:+4d} {glu[j]:6.1f} {s['G_s'][j]:7.1f} {s['R_a'][j]:6.2f} "
                         f"{s['p1'][j]:7.4f} {s['p2'][j]:7.4f} {s['p4'][j]:6.2f} {s['tau'][j]:6.1f}  {int(flag):4d}")
            L += ["```", ""]
    write_ascii(RES / "spot_check.md", "\n".join(L) + "\n")
    print(f"wrote {RES / 'spot_check.md'}")


if __name__ == "__main__":
    main()
