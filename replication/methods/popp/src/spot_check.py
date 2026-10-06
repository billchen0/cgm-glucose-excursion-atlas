"""Spot check (2026-10-05): G, the no-meal prediction G', Div, m_st and the fit error of each load
around each detection, one participant-day per glycaemic group, main rule (refractory), Route B.

Reads the saved protocol_v1 outputs and recomputes the signals with the fold's locked
parameters. Also writes the m_st delay table. Output: methods/popp/results/spot_check.md (ASCII).

Usage: python methods/popp/src/spot_check.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from common.evaluation import detectors, load_config  # noqa: E402
from common.evaluation.data import build_cohort  # noqa: E402
from common.evaluation.report import md_table, write_ascii  # noqa: E402
from methods.popp.src import popp as P  # noqa: E402

RES = Path(__file__).resolve().parents[1] / "results"
OUT = RES / "protocol_v1"
GROUPS = ["healthy", "prediabetes", "T2D"]


def fit_errors(y, i, fx, tau):
    """G'(i), Div(i), m_st and the RMS fit error of each load at sample i (as candidate_signals)."""
    zeta, tau = int(fx["zeta_min"]), int(tau)
    a = i - max(zeta, tau)
    g0 = y[a]
    div = np.mean(np.abs(y[i - zeta + 1:i + 1] - g0)) / g0
    above = y[i - tau:i + 1] > g0
    if not above[-1]:
        return g0, div, None, [np.nan] * len(fx["loads_g"])
    k = tau
    while k > 0 and above[k - 1]:
        k -= 1
    m = i - tau + k
    R = P._responses(fx, tau + 1)
    err = np.sqrt(np.mean((g0 + R[:, :i - m + 1] - y[m:i + 1]) ** 2, axis=1))
    return g0, div, m, err


def mst_delay_table():
    rows = []
    for rule, mr in [("refractory", "ours"), ("tp_lockout", "ours"), ("tp_lockout", "review")]:
        x = pd.read_csv(OUT / rule / "detections.csv",
                        parse_dates=["detection_time", "excursion_start", "matched_meal_start"])
        x = x[(x.rule == mr) & (x.route == "B") & (x.status == "TP")]
        dm = (x.excursion_start - x.matched_meal_start).dt.total_seconds() / 60
        rows.append([f"{rule}, {mr}", len(x), f"{dm.median():.0f}", f"{dm.mean():.1f}",
                     f"{dm.quantile(.25):.0f} to {dm.quantile(.75):.0f}", f"{x.delay_min.median():.0f}"])
    return md_table(pd.DataFrame(rows), ["Rule", "TP", "m_st delay median (min)", "m_st delay mean (min)",
                                         "m_st delay IQR (min)", "Detection delay median (min)"])


def main():
    cfg = load_config(*detectors.config_paths("popp"))
    cohort = build_cohort(cfg)
    det = pd.read_csv(OUT / "refractory" / "detections.csv", parse_dates=["detection_time", "excursion_start"])
    p = json.loads((OUT / "refractory" / "params" / "chosen_params_routeB_ours.json").read_text())
    fx = P.fixed_params(cfg)
    kept = det[det.status.isin(["TP", "FP"])]
    L = ["# Popp spot check: observed and simulated glucose around each detection", "",
         "## m_st delay (estimated meal start minus logged meal start)", "",
         "Route B, test data, TP detections. Detection delay = detection time minus logged start.", ""]
    L += mst_delay_table()
    L += ["", "## Spot check", "",
          "Main rule refractory, Route B, our matching rule. One participant-day per group: the first day "
          "with at least one TP and one FP. Each block shows minutes -10 to +10 around a kept detection "
          "(every 2 min). G = observed glucose; G' = no-meal prediction (the model at steady state at the "
          "anchor, i.e. G at i - max(zeta, tau)); Div in %; m_st as minutes relative to the detection; "
          "D25 ... D100 = RMS fit error (mg/dL) of each load over [m_st, i]. flag = Div > phi and "
          "min D < epsilon.", ""]
    for g in GROUPS:
        st = kept[kept.group == g].groupby("day_id").status.agg(set)
        day_id = sorted(st[st.map(lambda s: {"TP", "FP"} <= s)].index)[0]
        d = cohort.days.loc[day_id]
        fold = next(k for k, v in p.items() if k.startswith("fold") and d.subject in v["test_participants"])
        prm = p[fold]["params"]
        t, y = cohort.day_series(day_id, 1)
        L += [f"### {g}: {day_id}, {fold}: phi {prm['phi_pct']:g} %, tau {prm['tau_min']:g} min, "
              f"epsilon {prm['eps']:g} mg/dL", ""]
        x = det[(det.day_id == day_id) & ~det.status.str.startswith("removed")]
        for _, r in x.iterrows():
            i = int(np.flatnonzero(t == r.detection_time)[0])
            L += [f"Detection {r.detection_time:%H:%M}, status {r.status}"
                  + (f", delay {r.delay_min:.0f} min" if r.status == "TP" else "")
                  + f", m_st {r.excursion_start:%H:%M}", "", "```",
                  " min      G     G'   Div%  m_st   D25   D50   D75  D100  flag"]
            for j in range(max(i - 10, 0), min(i + 11, len(t)), 2):
                g0, div, m, err = fit_errors(y, j, fx, prm["tau_min"])
                flag = div * 100 > prm["phi_pct"] and np.nanmin(err) < prm["eps"] if m is not None else False
                ms = f"{m - i:+5d}" if m is not None else "    -"
                L.append(f"{j - i:+4d} {y[j]:6.1f} {g0:6.1f} {100 * div:6.1f} {ms} "
                         + " ".join(f"{e:5.1f}" for e in err) + f"  {int(flag):4d}")
            L += ["```", ""]
    write_ascii(RES / "spot_check.md", "\n".join(L) + "\n")
    print(f"wrote {RES / 'spot_check.md'}")


if __name__ == "__main__":
    main()
