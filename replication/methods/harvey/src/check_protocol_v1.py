"""Check (2026-10-05): Harvey through the shared protocol runner must equal excursion_v2.

Compares, for Route B and our matching rule, refractory and tp_lockout in
results/protocol_v1/ with results/excursion_v2/: summary rows, recovery agreement, Route B
parameters (fold and all_participants sets), and the row-level detections, meals and
recovery features. Exact equality (identical CSV text). Also checks tp_lockout with the review
matching rule against results/reference_tp_lockout/ (Route B detections, meals and detection
metrics; recovery features differ there by design, provisional segmentation). Reads only; writes
results/protocol_v1/check_vs_excursion_v2.csv.

Usage: python methods/harvey/src/check_protocol_v1.py
"""
import io
import json
import sys
from pathlib import Path

import pandas as pd

RES = Path(__file__).resolve().parents[1] / "results"
NEW, OLD = RES / "protocol_v1", RES / "excursion_v2"
REF = RES / "reference_tp_lockout"
RULES = ["refractory", "tp_lockout"]
TABLES = ["summary.csv", "recovery_agreement.csv", "detections.csv", "meals.csv", "recovery_features.csv"]
DET_METRICS = ["participants", "days", "TP", "FP", "FN", "sensitivity", "precision", "F2", "FP_per_day",
               "FP_per_hour", "delay_median", "delay_mean"]


def rows(path, rule="ours", cols=None):
    """Route B, one matching rule, as text (columns as in the old file, or ``cols``)."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df = df[(df.route == "B") & (df.rule == rule)].reset_index(drop=True)
    return df if cols is None else df[[c for c in cols if c in df.columns]]


def main():
    out, ok = [], True
    for rule in RULES:
        for t in TABLES:
            old, new = rows(OLD / rule / t), rows(NEW / rule / t)
            same = list(old.columns) == list(new.columns) and \
                old.to_csv(index=False) == new.to_csv(index=False)
            out.append(dict(rule=rule, item=t, rows_old=len(old), rows_new=len(new), identical=same))
        po = json.loads((OLD / rule / "params" / "chosen_params_routeB_ours.json").read_text())
        pn = json.loads((NEW / rule / "params" / "chosen_params_routeB_ours.json").read_text())
        out.append(dict(rule=rule, item="params/chosen_params_routeB_ours.json", rows_old=len(po),
                        rows_new=len(pn), identical=po == pn))
    for t in ["summary.csv", "detections.csv", "meals.csv"]:
        old = rows(REF / t, "review")
        cols = [c for c in old.columns if t != "summary.csv" or c in ["stratum"] + DET_METRICS]
        old = old[cols]
        new = rows(NEW / "tp_lockout" / t, "review", cols)
        same = list(old.columns) == list(new.columns) and old.to_csv(index=False) == new.to_csv(index=False)
        out.append(dict(rule="tp_lockout review vs reference_tp_lockout", item=t, rows_old=len(old),
                        rows_new=len(new), identical=same))
    df = pd.DataFrame(out)
    ok = bool(df.identical.all())
    df.to_csv(NEW / "check_vs_excursion_v2.csv", index=False)
    buf = io.StringIO()
    df.to_string(buf, index=False)
    print(buf.getvalue())
    print("ALL IDENTICAL" if ok else "!!! DIFFERENCE")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
