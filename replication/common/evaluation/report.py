"""Shared report helpers: table formatting, plain-ASCII writing, detection counts and
locked-parameter rows. Used by the protocol runner and the method-specific runners."""
import json
from pathlib import Path

import pandas as pd

GROUPS = ["healthy", "prediabetes", "T2D"]
FEATURES = ["recovery_time_min", "peak_height", "iauc", "peak_time_min"]
KEYS = ["TP", "FP", "FN", "sensitivity", "precision", "F2", "FP_per_day", "FP_per_hour",
        "delay_median", "delay_mean"]


def fmt(r, k):
    if k in ("TP", "FP", "FN"):
        return "" if pd.isna(r[k]) else str(int(r[k]))
    f = {"sensitivity": "{:.1%}", "precision": "{:.1%}", "F2": "{:.3f}", "FP_per_day": "{:.2f}",
         "FP_per_hour": "{:.3f}", "delay_median": "{:.0f}", "delay_mean": "{:.1f}"}[k]
    if pd.isna(r.get(k)):
        return ""
    s = f.format(r[k])
    if f"{k}_lo" in r and pd.notna(r[f"{k}_lo"]):
        s += f" [{f.format(r[f'{k}_lo'])}, {f.format(r[f'{k}_hi'])}]"
    return s.replace("%", "")


def detection_counts(det, rule):
    """Raw detections at the locked parameters and what the rule did with them."""
    rows = []
    for route, d in det.groupby("route"):
        st = d.status.value_counts()
        kept_scored = int(st.get("TP", 0) + st.get("FP", 0))
        before7 = d.status.eq("not_scored") & (pd.to_datetime(d.detection_time).dt.hour == 6)
        rows.append(dict(
            adjacent_rule=rule, route=route, raw_detections=len(d),
            removed_by_rule=int(st.get("removed_in_window", 0) + st.get("removed_outside_window", 0)),
            removed_in_scoring_window=int(st.get("removed_in_window", 0)),
            removed_outside_scoring_window=int(st.get("removed_outside_window", 0)),
            ignored_by_tp_lockout=int(st.get("lockout", 0)),
            kept_scored_TP_FP=kept_scored,
            kept_not_scored=int(st.get("not_scored", 0)),
            kept_06_to_07_not_scored=int(before7.sum()) if rule == "meal_window_max_peak" else None))
    return rows


def params_rows(path, rule, route):
    """Locked parameters for one rule and route, with forced grid edges."""
    rec = json.load(open(path))
    if route == "B":
        return [dict(rule=rule, route="B", set=k, **v["params"],
                     forced_edges=", ".join(v["grid_edges_forced"]) or "none")
                for k, v in rec.items()]
    P = pd.DataFrame({k: v["params"] for k, v in rec.items()}).T
    forced = pd.Series([e for v in rec.values() for e in v["grid_edges_forced"]]).value_counts()
    return [dict(rule=rule, route="A", set="mean +/- SD (42)",
                 **{p: f"{P[p].mean():.2f} +/- {P[p].std():.2f}" for p in P},
                 forced_edges=", ".join(f"{p} {n}/42" for p, n in forced.items()) or "none")]


def md_table(df, header):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return out


def write_ascii(path, text):
    """Write a generated text file as plain ASCII (UTF-8 without BOM)."""
    bad = sorted({c for c in text if ord(c) > 127})
    assert not bad, f"non-ASCII characters in {path}: {bad}"
    Path(path).write_text(text, encoding="utf-8")
