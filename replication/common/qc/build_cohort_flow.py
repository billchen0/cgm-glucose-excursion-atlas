"""Cohort flow for the CGMacros evaluation plan (Section 2.4 QC rules, Dexcom only), v3.

Data inventory only: no detector is run and no outcome data are loaded.
v2 outputs are kept in common/results/cohort_flow/v2/.

Conventions
* Dexcom GL on the 1-min grid as provided. Missing minutes are NaN (the CSVs do not
  interpolate across sensor gaps: native readings are integers and no interpolated
  values appear inside gaps).
* Gap = run of consecutive missing minutes between the first and last Dexcom reading.
  Isolated data islands shorter than one native sample (< 5 min) between two gaps of
  >= 30 min are treated as missing (CGMacros-026 has single stray readings every ~8 h
  inside one ~40 h dropout).
* Sensor segments: the record is split into blocks at every gap >= 30 min. A block
  starts a new sensor segment if the gap before it is > 120 min, or if the minute
  phase of its native 5-min readings (minutes mod 5 of the integer-valued rows)
  differs from the previous block. The first reading is always a segment start.
* Rule 1: drop the first 24 h after each segment start (sensor insertion).
* Short gaps <= 30 min are linearly interpolated before rule 2. Longer gaps stay NaN.
* One analysis day is one calendar day, from the first retained minute to the last
  reading.
* Rule 2: a day is dropped if its longest continuous stretch without retained data is
  > 120 min. Warm-up time and time outside the record count as missing, so partial
  days at a sensor start or end are dropped here. The removal is split into
  "partial day" (sensor start or end) and "internal sensor gap".
* Rule 3: day needs >= 1 breakfast and >= 1 lunch (merged meals) on that calendar day.
* Rule 4: minimum valid days per participant, reported for THRESHOLDS.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))
import cgmacros as C  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "results" / "cohort_flow"
WARMUP = pd.Timedelta(hours=24)
WARMUP_MIN = 24 * 60
SHORT_GAP = 30
BLOCK_GAP = 30
NEW_SENSOR_GAP = 120
MAX_GAP = 120
THRESHOLDS = [7, 8]
GAP_BINS = [0, 5, 15, 30, 60, 120, np.inf]
GAP_LABELS = ["<=5", "5-15", "15-30", "30-60", "60-120", ">120"]


def runs(mask):
    """(start_index, length) of True runs."""
    m = np.concatenate([[False], mask, [False]])
    e = np.flatnonzero(np.diff(m.astype(int)))
    return e[::2], e[1::2] - e[::2]


def longest_run(mask):
    _, n = runs(mask)
    return int(n.max()) if len(n) else 0


def load_1min(subject):
    f = C.CGMACROS_DIR / subject / f"{subject}.csv"
    d = pd.read_csv(f, usecols=["Timestamp", "Dexcom GL"])
    d["Timestamp"] = pd.to_datetime(d["Timestamp"])
    d = d.drop_duplicates("Timestamp").set_index("Timestamp").sort_index()
    g = d["Dexcom GL"].dropna()
    g = d["Dexcom GL"].reindex(pd.date_range(g.index[0], g.index[-1], freq="1min"))
    s, n = runs(g.isna().to_numpy())
    for k in range(1, len(s)):
        a, b = s[k - 1] + n[k - 1], s[k]           # data island [a, b)
        if b - a < 5 and n[k - 1] >= 30 and n[k] >= 30:
            g.iloc[a:b] = np.nan
    return g


def sensor_starts(g):
    """Indices (into g) where a new sensor segment starts."""
    v = g.to_numpy()
    s, n = runs(np.isnan(v))
    big = n >= BLOCK_GAP
    gs, gn = s[big], n[big]
    bstart = np.concatenate([[0], gs + gn])
    bend = np.concatenate([gs, [len(v)]])
    minutes = (g.index.astype("int64") // 60_000_000_000).to_numpy()
    starts, prev_phase = [0], None
    for k, (a, b) in enumerate(zip(bstart, bend)):
        seg = v[a:b]
        isint = ~np.isnan(seg) & (np.abs(seg - np.round(seg)) < 1e-6)
        ph = pd.Series(minutes[a:b][isint] % 5).mode()
        phase = int(ph.iloc[0]) if len(ph) else prev_phase
        if k > 0 and (gn[k - 1] > NEW_SENSOR_GAP or (phase is not None and phase != prev_phase)):
            starts.append(int(a))
        prev_phase = phase
    return starts


def interpolate_short(g):
    v = g.to_numpy().copy()
    s, n = runs(np.isnan(v))
    for a, k in zip(s, n):
        if k <= SHORT_GAP and a > 0 and a + k < len(v):
            v[a:a + k] = np.interp(np.arange(a, a + k), [a - 1, a + k], [v[a - 1], v[a + k]])
    return pd.Series(v, index=g.index)


def process(subject, per_sensor=True):
    g = load_1min(subject)
    first, last = g.index[0], g.index[-1]
    starts = sensor_starts(g) if per_sensor else [0]
    warm = np.zeros(len(g), bool)
    for a in starts:
        warm[a:a + WARMUP_MIN] = True
    meals = C.load_subject(subject)["meals"]
    bl = meals[meals["Meal Type"].isin(["breakfast", "lunch"])].copy()
    bl["day"] = bl["Timestamp"].dt.normalize()

    # raw gap list (before interpolation), length in minutes, and minutes outside warm-up
    s, n = runs(g.isna().to_numpy())
    gaps = pd.DataFrame({"subject": subject, "start": g.index[s], "len_min": n})
    gaps["len_after_warmup_min"] = [int((~warm[a:a + k]).sum()) for a, k in zip(s, n)]

    # screened: every calendar day touched by the record
    days_all = pd.date_range(first.normalize(), last.normalize(), freq="D")
    in_rec = bl[(bl.Timestamp >= first) & (bl.Timestamp <= last)]
    rec = dict(subject=subject, n_sensor_segments=len(starts),
               sensor_starts=";".join(str(g.index[a]) for a in starts),
               meals_outside_record=len(bl) - len(in_rec),
               screened_days=len(days_all), screened_meals=len(in_rec))

    # rule 1
    keep_t = ~warm
    first_ret = g.index[np.flatnonzero(keep_t)[0]] if keep_t.any() else None
    warm_s = pd.Series(warm, index=g.index)
    bl1 = in_rec[(in_rec.Timestamp >= first_ret) & ~warm_s.reindex(in_rec.Timestamp.dt.floor("min")).to_numpy()]
    days1 = pd.date_range(first_ret.normalize(), last.normalize(), freq="D") if first_ret is not None else []
    rec.update(r1_days=len(days1), r1_meals=len(bl1))

    # short-gap interpolation, then rule 2 per day
    gi = interpolate_short(g)
    full = pd.date_range(days_all[0], days_all[-1] + pd.Timedelta(days=1), freq="1min", inclusive="left")
    gf = gi.reindex(full)
    wf = warm_s.reindex(full, fill_value=False).to_numpy()
    after = np.asarray(full >= first_ret)
    retained = (gf.notna().to_numpy() & ~wf & after)
    internal_nan = gf.isna().to_numpy() & ~wf & after & np.asarray(full <= last)
    day_rows = []
    for day in days1:
        i0 = full.get_loc(day)
        sl = slice(i0, i0 + 1440)
        lr = longest_run(~retained[sl])
        li = longest_run(internal_nan[sl])
        nb = int(((bl1.day == day) & (bl1["Meal Type"] == "breakfast")).sum())
        nl = int(((bl1.day == day) & (bl1["Meal Type"] == "lunch")).sum())
        if lr <= MAX_GAP:
            status = "gap_ok"
        elif li > MAX_GAP:
            status = "gap_internal"
        else:
            status = "gap_partial"
        valid = status == "gap_ok" and nb > 0 and nl > 0
        day_rows.append(dict(subject=subject, day=day.date(), coverage=round(retained[sl].mean(), 3),
                             longest_missing_min=lr, longest_internal_gap_min=li,
                             n_breakfast=nb, n_lunch=nl, gap_status=status, valid=valid))
    return rec, pd.DataFrame(day_rows), gaps


def flow_table(subj, days, groups):
    meals = lambda x: int((x.n_breakfast + x.n_lunch).sum())
    rows = []
    for grp in groups:
        S = subj if grp == "overall" else subj[subj.group == grp]
        D = days[days.subject.isin(S.subject)]
        D2 = D[D.gap_status == "gap_ok"]
        D3 = D2[D2.valid]

        def row(step, p, d, m, rp=None, rd=None, rm=None):
            rows.append(dict(group=grp, step=step, participants=p, participants_removed=rp,
                             days=d, days_removed=rd, bl_meals=m, bl_meals_removed=rm))

        p0, d0, m0 = S.subject.nunique(), int(S.screened_days.sum()), int(S.screened_meals.sum())
        p1, d1, m1 = int((S.r1_days > 0).sum()), int(S.r1_days.sum()), int(S.r1_meals.sum())
        p2, d2, m2 = D2.subject.nunique(), len(D2), meals(D2)
        p3, d3, m3 = D3.subject.nunique(), len(D3), meals(D3)
        Dp, Di = D[D.gap_status == "gap_partial"], D[D.gap_status == "gap_internal"]
        row("0 Screened (all Dexcom data)", p0, d0, m0)
        row("1 Remove first 24 h after each sensor insertion", p1, d1, m1, p0 - p1, d0 - d1, m0 - m1)
        row("2 Remove days with a gap > 120 min", p2, d2, m2, p1 - p2, d1 - d2, m1 - m2)
        row("   2a of which partial first or last day of a sensor", None, None, None, None, len(Dp), meals(Dp))
        row("   2b of which internal sensor gap", None, None, None, None, len(Di), meals(Di))
        row("3 Remove days without both breakfast and lunch", p3, d3, m3, p2 - p3, d2 - d3, m2 - m3)
        vd = D3.groupby("subject").size()
        for k in THRESHOLDS:
            Dk = D3[D3.subject.isin(vd[vd >= k].index)]
            pk, dk, mk = Dk.subject.nunique(), len(Dk), meals(Dk)
            row(f"4 Minimum valid days >= {k} [Confirm with PhD]", pk, dk, mk, p3 - pk, d3 - dk, m3 - mk)
    t = pd.DataFrame(rows)
    for c in t.columns[2:]:
        t[c] = t[c].astype("Int64")
    return t


def run_all(per_sensor=True):
    recs, dls, gls = [], [], []
    for s in C.list_subjects():
        r, dd, gg = process(s, per_sensor)
        recs.append(r); dls.append(dd); gls.append(gg)
    subj = pd.DataFrame(recs).merge(C.load_bio(), on="subject", how="left")
    assert subj.group.notna().all()
    return subj, pd.concat(dls, ignore_index=True), pd.concat(gls, ignore_index=True)


def main():
    subj, days, gaps = run_all(per_sensor=True)
    bio = C.load_bio()
    flow = flow_table(subj, days, ["overall", "healthy", "prediabetes", "T2D"])
    flow.to_csv(OUT / "cohort_flow.csv", index=False)

    cut = lambda x: pd.cut(x, GAP_BINS, labels=GAP_LABELS, right=True)
    ga = gaps[gaps.len_after_warmup_min > 0].copy()
    ga["bin"] = cut(ga.len_after_warmup_min)
    gaps["bin"] = cut(gaps.len_min)
    by_all, by_w = gaps.groupby("bin", observed=False), ga.groupby("bin", observed=False)
    gt = pd.DataFrame({
        "gap_length_min": GAP_LABELS,
        "n_gaps_all_data": by_all.size().values,
        "n_gaps_after_warmup": by_w.size().values,
        "n_participants_after_warmup": by_w.subject.nunique().values,
        "missing_min_after_warmup": by_w.len_after_warmup_min.sum().values,
        "interpolated": [b <= SHORT_GAP for b in GAP_BINS[1:]],
    })
    gt["top_participant_share_after_warmup"] = [
        (f"{b.subject.value_counts().index[0]} ({b.subject.value_counts().iloc[0] / len(b):.0%})" if len(b) else "")
        for _, b in by_w]
    gt.to_csv(OUT / "gap_lengths.csv", index=False)

    # effect of the per-sensor warm-up rule (vs first insertion only)
    _, days_first, _ = run_all(per_sensor=False)
    vd = lambda d: d.groupby("subject").valid.sum()
    per = days.groupby("subject").agg(calendar_days_after_warmup=("day", "size"),
                                      valid_days=("valid", "sum"),
                                      mean_day_coverage=("coverage", "mean")).reset_index()
    per["valid_days_first_insertion_only"] = per.subject.map(vd(days_first))
    per = subj[["subject", "group", "n_sensor_segments", "sensor_starts", "screened_days"]].merge(per, on="subject")
    per.round(3).to_csv(OUT / "participant_valid_days.csv", index=False)
    days.merge(bio[["subject", "group"]], on="subject").to_csv(OUT / "day_level_qc.csv", index=False)
    gaps.drop(columns="bin").to_csv(OUT / "gap_list.csv", index=False)

    pd.set_option("display.width", 250)
    print(flow.to_string()); print(gt.to_string())
    print(per[per.n_sensor_segments > 1].to_string())
    print(per[per.valid_days != per.valid_days_first_insertion_only].to_string())
    print(per.groupby("group").valid_days.value_counts().unstack(fill_value=0))


if __name__ == "__main__":
    main()
