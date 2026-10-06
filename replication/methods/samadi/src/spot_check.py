"""Spot check (2026-10-05): d1G, d2G, the sign memberships and IGT around each detection,
one participant-day per glycaemic group, main rule (refractory), Route B.

Reads the saved protocol_v1 outputs and recomputes the signals with the fold's locked
parameters. Writes methods/samadi/results/spot_check.md (plain ASCII).

Usage: python methods/samadi/src/spot_check.py
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
from methods.samadi.src import samadi as S  # noqa: E402

RES = Path(__file__).resolve().parents[1] / "results"
OUT = RES / "protocol_v1"
GROUPS = ["healthy", "prediabetes", "T2D"]


def main():
    cfg = load_config(*detectors.config_paths("samadi"))
    cohort = build_cohort(cfg)
    det = pd.read_csv(OUT / "refractory" / "detections.csv", parse_dates=["detection_time"])
    p = json.loads((OUT / "refractory" / "params" / "chosen_params_routeB_ours.json").read_text())
    fx = S.fixed_params(cfg)
    kept = det[det.status.isin(["TP", "FP"])]
    L = ["# Samadi spot check: d1G, d2G, memberships and IGT around each detection", "",
         "Main rule refractory, Route B, our matching rule. One participant-day per group: the first "
         "day with at least one TP and one FP. Each block shows samples -15 to +15 min around a kept "
         "detection (5-min samples). d1G in mg/dL/min, d2G in mg/dL/min^2. N1/Z1/P1: negative, zero, "
         "positive memberships of d1G; N2/Z2/P2: the same for d2G. flag = IGT > Threshold_act. "
         "Thresholds are the held-out fold's locked set.", ""]
    for g in GROUPS:
        st = kept[kept.group == g].groupby("day_id").status.agg(set)
        day_id = sorted(st[st.map(lambda s: {"TP", "FP"} <= s)].index)[0]
        d = cohort.days.loc[day_id]
        fold = next(k for k, v in p.items() if k.startswith("fold") and d.subject in v["test_participants"])
        prm = p[fold]["params"]
        t, glu = cohort.day_series(day_id, 5)
        d1, d2 = S.derivatives(glu, fx["fit_points"], fx["sampling_min"])
        n1, z1, p1 = S.sign_memberships(d1, prm["gamma1"])
        n2, z2, p2 = S.sign_memberships(d2, prm["gamma1"] / fx["d2_scale_min"])
        v = S.igt(d1, d2, prm["gamma1"], fx["d2_scale_min"])
        L += [f"## {g}: {day_id}, {fold}: gamma1 {prm['gamma1']:g}, Threshold_act {prm['th_act']:g}", ""]
        x = det[(det.day_id == day_id) & ~det.status.str.startswith("removed")]
        for _, r in x.iterrows():
            i = int(np.flatnonzero(t == r.detection_time)[0])
            L += [f"Detection {r.detection_time:%H:%M}, status {r.status}"
                  + (f", delay {r.delay_min:.0f} min" if r.status == "TP" else ""), "", "```",
                  " min      g    d1G     d2G    N1   Z1   P1    N2   Z2   P2    IGT  flag"]
            for j in range(max(i - 3, 0), min(i + 4, len(t))):
                L.append(f"{5 * (j - i):+4d} {glu[j]:6.1f} {d1[j]:6.2f} {d2[j]:7.3f}  "
                         f"{n1[j]:4.2f} {z1[j]:4.2f} {p1[j]:4.2f}  {n2[j]:4.2f} {z2[j]:4.2f} {p2[j]:4.2f}  "
                         f"{v[j]:5.2f}  {int(v[j] > prm['th_act']):4d}")
            L += ["```", ""]
    write_ascii(RES / "spot_check.md", "\n".join(L) + "\n")
    print(f"wrote {RES / 'spot_check.md'}")


if __name__ == "__main__":
    main()
