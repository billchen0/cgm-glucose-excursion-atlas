"""Spot check (2026-10-05): median-filtered glucose, dG, Res and the thresholds around each
detection, one participant-day per glycaemic group, main rule (refractory), Route B.

Reads the saved protocol_v1 outputs and recomputes the signals with the fold's locked
parameters. Writes methods/faccioli/results/spot_check.md (plain ASCII).

Usage: python methods/faccioli/src/spot_check.py
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
from methods.faccioli.src import faccioli as F  # noqa: E402

RES = Path(__file__).resolve().parents[1] / "results"
OUT = RES / "protocol_v1"
GROUPS = ["healthy", "prediabetes", "T2D"]


def main():
    cfg = load_config(*detectors.config_paths("faccioli"))
    cohort = build_cohort(cfg)
    det = pd.read_csv(OUT / "refractory" / "detections.csv", parse_dates=["detection_time"])
    p = json.loads((OUT / "refractory" / "params" / "chosen_params_routeB_ours.json").read_text())
    fx = F.fixed_params(cfg)
    kept = det[det.status.isin(["TP", "FP"])]
    L = ["# Faccioli spot check: filtered glucose, dG and Res around each detection", "",
         "Main rule refractory, Route B, our matching rule. One participant-day per group: the first "
         "day with at least one TP and one FP. Each block shows samples -15 to +15 min around a kept "
         "detection (5-min samples). g = QC'd glucose, cgm = causal 3-point median, dG = Kalman "
         "derivative (mg/dL/min), Res = observer residual (mg/dL). flag = Res > Th_Res and "
         "dG > Th_Der. Thresholds and L are the held-out fold's locked set.", ""]
    for g in GROUPS:
        st = kept[kept.group == g].groupby("day_id").status.agg(set)
        day_id = sorted(st[st.map(lambda s: {"TP", "FP"} <= s)].index)[0]
        d = cohort.days.loc[day_id]
        fold = next(k for k, v in p.items() if k.startswith("fold") and d.subject in v["test_participants"])
        prm = p[fold]["params"]
        t, glu = cohort.day_series(day_id, 5)
        sig = F.signals(t, glu, fx, prm["l_bound"])
        L += [f"## {g}: {day_id}, {fold}: Th_Res {prm['th_res']:g} mg/dL, Th_Der {prm['th_der']:g} "
              f"mg/dL/min, L {prm['l_bound']:g} mg/dL/min^2", ""]
        x = det[(det.day_id == day_id) & ~det.status.str.startswith("removed")]
        for _, r in x.iterrows():
            i = int(np.flatnonzero(t == r.detection_time)[0])
            L += [f"Detection {r.detection_time:%H:%M}, status {r.status}"
                  + (f", delay {r.delay_min:.0f} min" if r.status == "TP" else ""), "", "```",
                  " min      g    cgm     dG     Res  Res>Th dG>Th  flag"]
            for j in range(max(i - 3, 0), min(i + 4, len(t))):
                a, b = sig["res"][j] > prm["th_res"], sig["dg"][j] > prm["th_der"]
                L.append(f"{5 * (j - i):+4d} {glu[j]:6.1f} {sig['cgm'][j]:6.1f} {sig['dg'][j]:6.2f} "
                         f"{sig['res'][j]:7.2f}  {int(a):6d} {int(b):5d}  {int(a and b):4d}")
            L += ["```", ""]
    write_ascii(RES / "spot_check.md", "\n".join(L) + "\n")
    print(f"wrote {RES / 'spot_check.md'}")


if __name__ == "__main__":
    main()
