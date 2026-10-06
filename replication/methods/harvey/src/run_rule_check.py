"""One-off check (2026-10-01): main adjacent rule, excursion_end vs refractory.

Reads the saved excursion_v2 outputs (detections.csv, meals.csv of excursion_end and
refractory); never writes to them. Rules, the frozen excursion definition and all earlier
results are unchanged. Writes methods/harvey/results/rule_check/.

Usage: python methods/harvey/src/run_rule_check.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_harvey  # noqa: E402
import run_harvey_peak_rules as PR  # noqa: E402
from common.evaluation import load_config  # noqa: E402
from common.evaluation import postprocess as P  # noqa: E402
from common.evaluation import scoring as S  # noqa: E402
from common.evaluation.data import build_cohort  # noqa: E402
from common.evaluation.postprocess import trace_for  # noqa: E402

EV2 = run_harvey.HARVEY / "results" / "excursion_v2"
OUT = run_harvey.HARVEY / "results" / "rule_check"
GROUPS = ["healthy", "prediabetes", "T2D"]
MIN = pd.Timedelta(minutes=1)

# Pre-set criteria, verbatim from the task (fixed before running; not changed after).
CRITERIA = [
    ("C1", ">= 10 % of refractory-kept events start inside an ongoing excursion (split excursions)."),
    ("C2", "The C1 percentage differs by >= 5 pp between any two groups (healthy, prediabetes, T2D)."),
    ("C3", "Events per participant-day differ by >= 10 % between the two rules within at least one group, "
           "and the direction or size of that difference is not the same across groups (state exactly "
           "what you compared)."),
]
RULE_TEXT = ("Choose excursion_end as main if ANY of these holds on Route B; otherwise choose refractory.")
# Operational definitions, written before any result was computed.
OPERATIONAL = [
    "All criteria use Route B, main analysis (each rule with its own locked parameters).",
    "Events = kept detections with onset 07:00 to 21:59 (night block-out excluded). The rules "
    "themselves run on the whole detector day, as in the pipeline.",
    "C1: M1 overall, % of refractory-kept events that are split. Met if >= 10.0 %.",
    "C2: M1 by group. Met if max minus min across the three groups >= 5.0 pp.",
    "C3: for each group g, d_g = 100 * (mean events per participant-day under excursion_end minus "
    "the same under refractory) / (refractory value). Participant-days = all evaluated test days, "
    "days with no event count as 0. Met if max abs(d_g) >= 10.0 AND (the signs of d_g differ across "
    "groups OR max(d_g) - min(d_g) >= 5.0 pp). The 5 pp size threshold mirrors C2.",
]


def daytime(t):
    t = pd.DatetimeIndex(t)
    return (t.hour >= 7) & (t.hour < 22)


def route_days(cohort, route):
    sp = pd.read_csv(EV2 / "refractory" / "splits.csv", index_col=0)
    ids = cohort.days.index if route == "B" else sp.index[sp.route_a == "test"]
    return cohort.days.loc[ids]


def load_rule(rule):
    d = pd.read_csv(EV2 / rule / "detections.csv", parse_dates=["detection_time"])
    d["kept"] = ~d.status.str.startswith("removed")
    m = pd.read_csv(EV2 / rule / "meals.csv", parse_dates=["start"])
    return d, m


def refractory_on(raw, cfg):
    """Refractory applied to given raw detections (same-raw analysis)."""
    rc = dict(cfg, scoring=dict(cfg["scoring"], adjacent_rule="refractory"))
    out = []
    for _, d in raw.groupby(["route", "day_id"], sort=False):
        d = d.sort_values("detection_time").copy()
        date = d.detection_time.iloc[0].normalize()
        mins = np.asarray((d.detection_time - date) / MIN)
        d["kept"] = P.keep_mask(mins, None, rc)
        out.append(d)
    return pd.concat(out)


def blocker_info(d, trace_of, E):
    """Refractory: for each detection, the previous kept detection of the day and its excursion end."""
    rows = []
    for (route, day_id), x in d.groupby(["route", "day_id"], sort=False):
        x = x.sort_values("detection_time")
        prev = None
        tr = trace_of(x.subject.iloc[0])
        for _, r in x.iterrows():
            end = tr.excursion(prev)["end"] if prev is not None else pd.NaT
            rows.append(dict(route=route, day_id=day_id, detection_time=r.detection_time,
                             prev_kept=prev, prev_end=end))
            if r.kept:
                prev = r.detection_time
    return d.merge(pd.DataFrame(rows), on=["route", "day_id", "detection_time"], how="left",
                   validate="one_to_one")


def score_refractory_same_raw(ref, cohort, cfg):
    """FN meals when refractory is applied to excursion_end's raw detections."""
    rc = dict(cfg, scoring=dict(cfg["scoring"], adjacent_rule="refractory"))
    ms = S.scored_meals(cohort, rc, "ours")
    rows = []
    for (route, day_id), x in ref.groupby(["route", "day_id"]):
        d = cohort.days.loc[day_id]
        _, mr = S.score_day(pd.DatetimeIndex(x.loc[x.kept, "detection_time"]), d,
                            ms[ms.day_id == day_id], rc, "ours")
        rows.append(mr.assign(route=route))
    return pd.concat(rows, ignore_index=True)


def by_group(df, f):
    """f(sub) for overall and each group -> list of dict rows."""
    return [dict(group=g, **f(df if g == "overall" else df[df.group == g])) for g in ["overall"] + GROUPS]


def metrics(analysis, route, ee, ref, ee_meals, ref_meals, days, trace_of, E):
    ee, ref = ee[ee.route == route], ref[ref.route == route]
    out = {}
    # M1 split excursions under refractory
    k = ref[ref.kept & daytime(ref.detection_time)]
    split = k.prev_kept.notna() & (k.detection_time < k.prev_end)
    out["M1"] = by_group(k.assign(split=split), lambda s: dict(
        kept_events=len(s), split=int(s.split.sum()), split_pct=round(100 * s.split.mean(), 1)))
    # M2 long merges under excursion_end
    mg = ee[~ee.kept & daytime(ee.detection_time)]
    gap = (mg.detection_time - pd.to_datetime(mg.event_anchor)) / MIN
    out["M2"] = by_group(mg.assign(long=gap > 120), lambda s: dict(
        merged=len(s), merged_over_120_min=int(s.long.sum()),
        long_pct=round(100 * s.long.mean(), 1) if len(s) else np.nan))
    # M3 rule-caused misses
    rows = []
    for rule, d, m in [("refractory", ref, ref_meals), ("excursion_end", ee, ee_meals)]:
        m = m[(m.route == route) & (m.status == "FN")]
        if rule == "refractory" and analysis == "same_raw":   # statuses there are excursion_end's
            rem = d[~d.kept & d.in_window]
        else:
            rem = d[d.status == "removed_in_window"]
        for _, r in m.iterrows():
            x = rem[(rem.day_id == r.day_id) & (rem.detection_time >= r.start - 30 * MIN)
                    & (rem.detection_time <= r.start + 120 * MIN)].sort_values("detection_time")
            if not len(x):
                reason = "no removed detection in TP window"
            elif rule == "excursion_end":
                reason = "excursion_end: removed while the anchor's excursion was ongoing"
            else:
                f = x.iloc[0]
                reason = ("refractory: removed after the blocking excursion had ended"
                          if f.prev_end <= f.detection_time else
                          "refractory: removed while the blocking excursion was ongoing")
            rows.append(dict(rule=rule, group=r.group, meal_id=r.meal_id, reason=reason))
    out["M3"] = rows
    # M4 events per participant-day, M5 duration
    m4, m5 = [], []
    for rule, d in [("excursion_end", ee), ("refractory", ref)]:
        ev = d[d.kept & daytime(d.detection_time)]
        n = ev.groupby("day_id").size().reindex(days.index, fill_value=0)
        per = pd.DataFrame(dict(n=n, group=days.group))
        for g in ["overall"] + GROUPS:
            s = per if g == "overall" else per[per.group == g]
            m4.append(dict(rule=rule, group=g, days=len(s), mean=s.n.mean(), median=s.n.median()))
        dur = [(trace_of(r.subject).excursion(r.detection_time)["end"] - r.detection_time) / MIN
               for r in ev.itertuples()]
        ev = ev.assign(duration=dur)
        for g in ["overall"] + GROUPS:
            s = ev if g == "overall" else ev[ev.group == g]
            m5.append(dict(rule=rule, group=g, events=len(s), median=s.duration.median(),
                           q1=s.duration.quantile(0.25), q3=s.duration.quantile(0.75)))
    out["M4"], out["M5"] = m4, m5
    return out


def tag(rows, analysis, route):
    return [dict(analysis=analysis, route=route, **r) for r in rows]


def main():
    cfg = load_config(run_harvey.HARVEY_CONFIG)
    E = cfg["excursion"]
    cohort = build_cohort(cfg)
    trace_of = lambda s: trace_for(cohort.series_1min[s], E)  # noqa: E731
    OUT.mkdir(parents=True, exist_ok=True)

    ee, ee_meals = load_rule("excursion_end")
    ref, ref_meals = load_rule("refractory")
    ref = blocker_info(ref, trace_of, E)
    # same raw detections: refractory applied to excursion_end's raw detections
    raw = ee.drop(columns=["kept"])
    ref2 = refractory_on(raw, cfg)
    win = cohort.days[["window_start", "window_end"]]
    ref2 = ref2.join(win, on="day_id")
    ref2["in_window"] = (ref2.detection_time >= ref2.window_start) & (ref2.detection_time <= ref2.window_end)
    ref2 = blocker_info(ref2, trace_of, E)
    ref2_meals = score_refractory_same_raw(ref2, cohort, cfg)

    res = {k: [] for k in ["M1", "M2", "M3", "M4", "M5"]}
    for analysis, R, RM in [("main", ref, ref_meals), ("same_raw", ref2, ref2_meals)]:
        for route in ["B", "A"]:
            days = route_days(cohort, route)
            m = metrics(analysis, route, ee, R, ee_meals, RM, days, trace_of, E)
            for k in res:
                res[k] += tag(m[k], analysis, route)
    t = {k: pd.DataFrame(v) for k, v in res.items()}
    m3 = (t["M3"].groupby(["analysis", "route", "rule", "group", "reason"]).size()
          .rename("fn_meals").reset_index())
    m3_all = t["M3"].copy()
    m4 = t["M4"].pivot_table(index=["analysis", "route", "group"], columns="rule",
                             values=["mean", "median", "days"], sort=False)
    m4.columns = [f"{a}_{b}" for a, b in m4.columns]
    m4 = m4.reset_index()
    m4["mean_diff_pct"] = 100 * (m4.mean_excursion_end - m4.mean_refractory) / m4.mean_refractory
    t["M1"].to_csv(OUT / "m1_split_excursions.csv", index=False)
    t["M2"].to_csv(OUT / "m2_long_merges.csv", index=False)
    m3.to_csv(OUT / "m3_rule_caused_misses.csv", index=False)
    m4.round(3).to_csv(OUT / "m4_events_per_day.csv", index=False)
    t["M5"].round(1).to_csv(OUT / "m5_event_duration.csv", index=False)

    crit = criteria(t, m4, "B")
    crit.to_csv(OUT / "criteria.csv", index=False)
    crit_a = criteria(t, m4, "A")
    choice = "excursion_end" if crit.met.any() else "refractory"
    write_readme(t, m3, m4, crit, choice, crit_a)
    print(crit.to_string(index=False))
    print("Route A (secondary):", dict(zip(crit_a.criterion, crit_a.met)))
    print("choice:", choice)
    spot_checks(ee, ref, ref_meals, trace_of)


def criteria(t, m4, route):
    """Pre-set criteria C1-C3 on the main analysis of one route."""
    b1 = t["M1"][(t["M1"].analysis == "main") & (t["M1"].route == route)].set_index("group")
    c1v = b1.loc["overall", "split_pct"]
    gp = b1.loc[GROUPS, "split_pct"]
    c2v = gp.max() - gp.min()
    b4 = m4[(m4.analysis == "main") & (m4.route == route)].set_index("group").loc[GROUPS, "mean_diff_pct"]
    c3_size = b4.abs().max() >= 10
    c3_dir = (np.sign(b4).nunique() > 1) or (b4.max() - b4.min() >= 5)
    crit = pd.DataFrame([
        dict(criterion="C1", value=f"{c1v:.1f} % split", threshold=">= 10.0 %", met=bool(c1v >= 10)),
        dict(criterion="C2", value=f"range {c2v:.1f} pp (" + ", ".join(f"{g} {v:.1f}" for g, v in gp.items()) + ")",
             threshold=">= 5.0 pp", met=bool(c2v >= 5)),
        dict(criterion="C3", value="d_g " + ", ".join(f"{g} {v:+.1f} %" for g, v in b4.items())
             + f"; max abs(d_g) {b4.abs().max():.1f}; spread {b4.max() - b4.min():.1f} pp",
             threshold=">= 10 % in a group AND (sign differs OR spread >= 5 pp)",
             met=bool(c3_size and c3_dir))])
    return crit


def _tbl(header, rows):
    return PR.md_table(pd.DataFrame(rows), header)


def write_readme(t, m3, m4, crit, choice, crit_a):
    L = ["# Main adjacent rule check: excursion_end vs refractory (2026-10-01)", "",
         "One-off check. No rule, no excursion parameter and no earlier result was changed.", "",
         "## Decision criteria (fixed before running)", "", RULE_TEXT, ""]
    L += [f"- {c}. {txt}" for c, txt in CRITERIA]
    L += ["", "Operational definitions (written before any result was computed):", ""]
    L += [f"- {x}" for x in OPERATIONAL]
    L += ["", "## Setup", "",
          "- Detections: the saved excursion_v2 runs of excursion_end and refractory (our matching rule).",
          "- Route B: each held-out participant with that fold's locked parameters. Route A (appendix): "
          "each participant's test days with that participant's parameters.",
          "- Main analysis: each rule with its own locked parameters, so raw detections differ.",
          "- Same-raw analysis: refractory applied to excursion_end's raw detections (excursion_end "
          "parameters), to isolate the rule effect.",
          "- Excursions: the shared function in `common/evaluation/excursion.py`, frozen parameters.",
          "- Events and merged detections count only with onset 07:00 to 21:59. M3 uses the scoring "
          "window and logged breakfast and lunch.", ""]

    def section(route):
        S_ = []
        for an, title in [("main", "main analysis"), ("same_raw", "same raw detections")]:
            m1 = t["M1"][(t["M1"].analysis == an) & (t["M1"].route == route)]
            S_ += ["", f"### M1. Split excursions under refractory ({title})", "",
                   f"Route {route}, test data. n = refractory-kept events (07:00 to 21:59). "
                   "Split = starts before the previous kept detection's excursion end.", ""]
            S_ += _tbl(["Group", "Kept events", "Split", "% split"],
                       [[r.group, r.kept_events, r.split, f"{r.split_pct:.1f}"] for r in m1.itertuples()])
        m2 = t["M2"][(t["M2"].analysis == "main") & (t["M2"].route == route)]
        S_ += ["", "### M2. Long merges under excursion_end", "",
               f"Route {route}, test data. n = merged detections (07:00 to 21:59). "
               "Long = more than 120 min after the event anchor.", ""]
        S_ += _tbl(["Group", "Merged", "> 120 min", "% long"],
                   [[r.group, r.merged, r.merged_over_120_min, f"{r.long_pct:.1f}"] for r in m2.itertuples()])
        for an, title in [("main", "main analysis"), ("same_raw", "same raw detections")]:
            x = m3[(m3.analysis == an) & (m3.route == route) & (m3.group.isin(GROUPS))]
            S_ += ["", f"### M3. Rule-caused misses ({title})", "",
                   f"Route {route}, scoring window, logged breakfast and lunch. n = FN meals.", ""]
            piv = x.pivot_table(index=["rule", "reason"], columns="group", values="fn_meals",
                                aggfunc="sum", fill_value=0).reindex(columns=GROUPS, fill_value=0)
            S_ += _tbl(["Rule", "Reason", "Healthy", "Prediabetes", "T2D", "Total"],
                       [[r, reason, *map(int, v), int(sum(v))] for (r, reason), v in
                        zip(piv.index, piv.to_numpy())])
        for an, title in [("main", "main analysis"), ("same_raw", "same raw detections")]:
            x = m4[(m4.analysis == an) & (m4.route == route)]
            S_ += ["", f"### M4. Events per participant-day ({title})", "",
                   f"Route {route}, test data. n = participant-days (days with no event count as 0). "
                   "Events with onset 07:00 to 21:59. Diff = excursion_end vs refractory, on the mean.", ""]
            S_ += _tbl(["Group", "Days", "excursion_end mean (median)", "refractory mean (median)", "Diff %"],
                       [[r.group, int(r.days_excursion_end), f"{r.mean_excursion_end:.2f} ({r.median_excursion_end:.0f})",
                         f"{r.mean_refractory:.2f} ({r.median_refractory:.0f})", f"{r.mean_diff_pct:+.1f}"]
                        for r in x.itertuples()])
        for an, title in [("main", "main analysis"), ("same_raw", "same raw detections")]:
            x = t["M5"][(t["M5"].analysis == an) & (t["M5"].route == route)]
            S_ += ["", f"### M5. Event duration, anchor to excursion end ({title})", "",
                   f"Route {route}, test data. n = kept events (07:00 to 21:59). Median [IQR], min.", ""]
            rows = []
            for g in ["overall"] + GROUPS:
                a = x[(x.rule == "excursion_end") & (x.group == g)].iloc[0]
                b = x[(x.rule == "refractory") & (x.group == g)].iloc[0]
                rows.append([g, f"{a['median']:.0f} [{a.q1:.0f}, {a.q3:.0f}] ({int(a.events)})",
                             f"{b['median']:.0f} [{b.q1:.0f}, {b.q3:.0f}] ({int(b.events)})"])
            S_ += _tbl(["Group", "excursion_end", "refractory"], rows)
        return S_

    L += ["## Results, Route B"] + section("B")
    L += ["", "## Result", "", "Route B, main analysis.", ""]
    L += _tbl(["Criterion", "Value", "Threshold", "Met"],
              [[c.criterion, c.value, c.threshold, "yes" if c.met else "no"] for c in crit.itertuples()])
    met = [c.criterion for c in crit.itertuples() if c.met]
    L += ["", f"Criteria met: {', '.join(met) if met else 'none'}.",
          f"Choice: **{choice}** is the main rule."]
    L += ["", "## Appendix: Route A (secondary check)", "",
          "Criteria on Route A, main analysis. Shown for information; the choice uses Route B only.", ""]
    L += _tbl(["Criterion", "Value", "Threshold", "Met"],
              [[c.criterion, c.value, c.threshold, "yes" if c.met else "no"] for c in crit_a.itertuples()])
    L += section("A")
    L += ["", "## Files", "",
          "`criteria.csv`, `m1_split_excursions.csv`, `m2_long_merges.csv`, `m3_rule_caused_misses.csv`, "
          "`m4_events_per_day.csv`, `m5_event_duration.csv`.", "",
          "Run from `replication/`: `python methods/harvey/src/run_rule_check.py`"]
    PR.write_ascii(OUT / "README.md", "\n".join(L) + "\n")


def spot_checks(ee, ref, ref_meals, trace_of):
    b, eb = ref[ref.route == "B"], ee[ee.route == "B"]
    k = b[b.kept & daytime(b.detection_time) & b.prev_kept.notna()]
    s = k[k.detection_time < k.prev_end].iloc[0]
    ex = trace_of(s.subject).excursion(s.prev_kept)
    print(f"\n[split, refractory] {s.day_id} ({s.group}): previous kept {s.prev_kept:%H:%M}, its excursion "
          f"ends {ex['end']:%H:%M} ({ex['end_type']}, glucose-based); the 120-min rule frees at "
          f"{s.prev_kept + 120 * MIN:%H:%M}; this kept detection {s.detection_time:%H:%M} starts inside it.")
    mg = eb[~eb.kept & daytime(eb.detection_time)]
    gap = (mg.detection_time - pd.to_datetime(mg.event_anchor)) / MIN
    lm = mg[(gap > 120) & (mg.day_id != s.day_id)]
    x = (lm[lm.group == "T2D"] if (lm.group == "T2D").any() else lm).iloc[0]
    exl = trace_of(x.subject).excursion(pd.Timestamp(x.event_anchor))
    assert exl["end"] == pd.Timestamp(x.event_close) and x.detection_time < exl["end"]
    print(f"[long merge, excursion_end] {x.day_id} ({x.group}): anchor {pd.Timestamp(x.event_anchor):%H:%M}, "
          f"merged {x.detection_time:%H:%M} (+{(x.detection_time - pd.Timestamp(x.event_anchor)) / MIN:.0f} min), "
          f"excursion end {pd.Timestamp(x.event_close):%H:%M} ({x.event_end_type}).")
    fn = ref_meals[(ref_meals.route == "B") & (ref_meals.status == "FN")]
    rem = b[b.status == "removed_in_window"]
    for _, m in fn.iterrows():
        y = rem[(rem.day_id == m.day_id) & (rem.detection_time >= m.start - 30 * MIN)
                & (rem.detection_time <= m.start + 120 * MIN)]
        if len(y):
            f = y.sort_values("detection_time").iloc[0]
            state = "had ended" if f.prev_end <= f.detection_time else "was ongoing"
            print(f"[rule-caused miss, refractory] {m.meal_id} ({m.group}): meal {m.start:%H:%M}; detection "
                  f"{f.detection_time:%H:%M} removed by refractory; blocking kept detection "
                  f"{f.prev_kept:%H:%M}, whose excursion ended {f.prev_end:%H:%M} ({state}).")
            break


if __name__ == "__main__":
    main()
