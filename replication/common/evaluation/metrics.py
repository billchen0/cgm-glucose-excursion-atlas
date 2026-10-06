"""Detection metrics with participant-level bootstrap, recovery features, ICC and
Bland-Altman (plan v3 section 8). Recovery segmentation: ``[features] segmentation`` =
"provisional" (deviations E9) or "excursion" (shared definition in excursion.py, 2026-10-01).
"""
import numpy as np
import pandas as pd

import cgmacros as C   # on sys.path via the package __init__

from .postprocess import trace_for

GROUPS = ["healthy", "prediabetes", "T2D"]
FEATURES = ["peak_time_min", "peak_height", "iauc", "recovery_time_min"]


# ---------------------------------------------------------------- detection level
def per_participant(det, meals, days):
    """Per participant: TP, FP, FN, lockout, days, hours, and the list of TP delays."""
    rows = []
    for s, dd in days.groupby("subject"):
        d = det[det.subject == s]
        m = meals[(meals.subject == s) & (meals.status != "not_scored")]
        rows.append(dict(subject=s, group=dd.group.iloc[0],
                         TP=int((d.status == "TP").sum()), FP=int((d.status == "FP").sum()),
                         FN=int((m.status == "FN").sum()), lockout=int((d.status == "lockout").sum()),
                         days=int(dd.scored.sum()), hours=float(dd.scored_hours.sum()),
                         delays=d.loc[d.status == "TP", "delay_min"].to_numpy()))
    return pd.DataFrame(rows)


def pooled(pp, beta=2.0):
    tp, fp, fn = pp.TP.sum(), pp.FP.sum(), pp.FN.sum()
    delays = np.concatenate(pp.delays.to_list()) if len(pp) else np.array([])
    b2 = beta ** 2
    return dict(
        TP=tp, FP=fp, FN=fn,
        sensitivity=tp / (tp + fn) if tp + fn else np.nan,
        precision=tp / (tp + fp) if tp + fp else np.nan,
        F2=(1 + b2) * tp / ((1 + b2) * tp + b2 * fn + fp) if tp + fn + fp else np.nan,
        FP_per_day=fp / pp.days.sum() if pp.days.sum() else np.nan,
        FP_per_hour=fp / pp.hours.sum() if pp.hours.sum() else np.nan,
        delay_median=float(np.median(delays)) if len(delays) else np.nan,
        delay_mean=float(np.mean(delays)) if len(delays) else np.nan,
    )


CI_METRICS = ["sensitivity", "precision", "F2", "FP_per_day", "FP_per_hour",
              "delay_median", "delay_mean"]


def bootstrap(pp, n, seed, ci=0.95):
    rng = np.random.default_rng(seed)
    idx = np.arange(len(pp))
    reps = [pooled(pp.iloc[rng.choice(idx, len(idx))]) for _ in range(n)]
    r = pd.DataFrame(reps)[CI_METRICS]
    a = (1 - ci) / 2
    return r.quantile(a), r.quantile(1 - a)


def summary_table(det, meals, days, cfg, extra=None):
    """Rows: overall, each group (all metrics); breakfast, lunch (TP/FN/sens/delay)."""
    n, seed = cfg["metrics"]["bootstrap_n"], cfg["seed"]
    pp = per_participant(det, meals, days)
    rows = []
    for stratum, sub in [("overall", pp)] + [(g, pp[pp.group == g]) for g in GROUPS]:
        r = dict(stratum=stratum, participants=len(sub), days=int(sub.days.sum()),
                 scored_hours=round(sub.hours.sum(), 1), lockout_ignored=int(sub.lockout.sum()),
                 **pooled(sub))
        lo, hi = bootstrap(sub, n, seed)
        for k in CI_METRICS:
            r[f"{k}_lo"], r[f"{k}_hi"] = lo[k], hi[k]
        rows.append(r)
    for mt in ["breakfast", "lunch"]:
        dm = det[det.matched_meal_type == mt]
        mm = meals[meals.meal_type == mt]
        pm = per_participant(dm, mm, days)
        pm["FP"] = 0
        p = pooled(pm)
        r = dict(stratum=mt, participants=len(pm), days=int(pm.days.sum()), TP=p["TP"], FN=p["FN"],
                 sensitivity=p["sensitivity"], delay_median=p["delay_median"],
                 delay_mean=p["delay_mean"])
        lo, hi = bootstrap(pm, n, seed)
        for k in ["sensitivity", "delay_median", "delay_mean"]:
            r[f"{k}_lo"], r[f"{k}_hi"] = lo[k], hi[k]
        rows.append(r)
    out = pd.DataFrame(rows)
    out["n_delay_zero"] = [int((np.concatenate(pp.delays.to_list()) == 0).sum())] + [np.nan] * (len(out) - 1)
    if extra:
        for k, v in extra.items():
            out.insert(0, k, v)
    return out


# ---------------------------------------------------------------- recovery features
def recovery_features(series, anchor, fcfg):
    """Features for one anchor on a 1-min series. None if the window has missing data."""
    bmin, hmin = fcfg["baseline_min"], fcfg["horizon_min"]
    anchor = pd.Timestamp(anchor).floor("min")
    w = series.reindex(pd.date_range(anchor - pd.Timedelta(minutes=bmin),
                                     anchor + pd.Timedelta(minutes=hmin), freq="1min"))
    v = w.to_numpy(float)
    if np.isnan(v).any():
        return None
    base = v[:bmin].mean()
    after = v[bmin:]                                # anchor .. anchor + horizon (t = 0..h)
    pk = 1 + int(np.argmax(after[1:]))              # peak in (anchor, anchor + h]
    below = np.flatnonzero(after[pk + 1:] <= base)
    end = pk + 1 + int(below[0]) if len(below) else hmin
    exc = np.clip(after[:end + 1] - base, 0, None)
    return dict(baseline=base, peak_time_min=float(pk), peak_height=after[pk] - base,
                iauc=float(np.trapezoid(exc, dx=1.0)), recovery_time_min=float(end - pk),
                recovery_censored=not len(below))


def recovery_features_excursion(series, anchor, fcfg, ecfg, new_starts, window, closed_lo):
    """As recovery_features, but baseline, peak and end come from the shared excursion
    definition. Peak = max in (anchor, end]. Same completeness check ([anchor - 30, anchor + 180])."""
    bmin, hmin = fcfg["baseline_min"], fcfg["horizon_min"]
    anchor = pd.Timestamp(anchor).floor("min")
    w = series.reindex(pd.date_range(anchor - pd.Timedelta(minutes=bmin),
                                     anchor + pd.Timedelta(minutes=hmin), freq="1min"))
    v = w.to_numpy(float)
    if np.isnan(v).any():
        return None
    ex = trace_for(series, ecfg).excursion(anchor, new_starts, window, closed_lo)
    base, pk, end = ex["baseline"], ex["peak_min"], ex["end_min"]
    after = v[bmin:]                                # anchor .. anchor + horizon (t = 0..h)
    exc = np.clip(after[:end + 1] - base, 0, None)
    return dict(baseline=base, peak_time_min=float(pk), peak_height=ex["peak"] - base,
                iauc=float(np.trapezoid(exc, dx=1.0)), recovery_time_min=float(end - pk),
                recovery_censored=ex["censored"], end_type=ex["end_type"])


_FOOD = {}


def food_entries(subject):
    """All logged food entries (any meal type, not merged)."""
    if subject not in _FOOD:
        _FOOD[subject] = pd.DatetimeIndex(C.load_subject(subject, merge_min=0)["meals"].Timestamp)
    return _FOOD[subject]


def feature_pairs(det, cohort, fcfg, ecfg=None):
    """One row per TP pair with detector (_det) and reference (_ref) features."""
    excursion = fcfg.get("segmentation", "provisional") == "excursion"
    rows = []
    for _, r in det[det.status == "TP"].iterrows():
        s = cohort.series_1min[r.subject]
        if excursion:
            iw = int(ecfg["interrupt_window_min"])
            raw = pd.DatetimeIndex(det.loc[det.day_id == r.day_id, "detection_time"])
            fd = recovery_features_excursion(s, r.detection_time, fcfg, ecfg, raw, (0, iw), False)
            fr = recovery_features_excursion(s, r.matched_meal_start, fcfg, ecfg,
                                             food_entries(r.subject), (-iw, iw), True)
        else:
            fd = recovery_features(s, r.detection_time, fcfg)
            fr = recovery_features(s, r.matched_meal_start, fcfg)
        row = dict(subject=r.subject, group=r.group, day_id=r.day_id, meal_type=r.matched_meal_type,
                   meal_start=r.matched_meal_start, detection_time=r.detection_time,
                   delay_min=r.delay_min, featurised=fd is not None and fr is not None)
        for tag, f in [("det", fd), ("ref", fr)]:
            for k, v in (f or {}).items():
                row[f"{k}_{tag}"] = v
        rows.append(row)
    return pd.DataFrame(rows)


def icc_a1(x, y):
    """ICC(A,1): two-way random, absolute agreement, single measure (McGraw & Wong 1996)."""
    X = np.column_stack([x, y]).astype(float)
    n, k = X.shape
    if n < 3:
        return np.nan
    gm = X.mean()
    msr = k * ((X.mean(1) - gm) ** 2).sum() / (n - 1)
    msc = n * ((X.mean(0) - gm) ** 2).sum() / (k - 1)
    sse = ((X - X.mean(1, keepdims=True) - X.mean(0, keepdims=True) + gm) ** 2).sum()
    mse = sse / ((n - 1) * (k - 1))
    return (msr - mse) / (msr + (k - 1) * mse + k * (msc - mse) / n)


def agreement_table(pairs, extra=None):
    """ICC and Bland-Altman (detector - reference) per feature, overall / group / meal.

    With excursion segmentation, pairs where either anchor is ``no_rise`` are left out of the
    recovery-time row only (``n`` then counts the pairs used).
    """
    ok = pairs[pairs.featurised] if len(pairs) else pairs
    rows = []
    strata = [("overall", ok)] + [(g, ok[ok.group == g]) for g in GROUPS] + \
             [(m, ok[ok.meal_type == m]) for m in ["breakfast", "lunch"]]
    for stratum, sub in strata:
        for f in FEATURES:
            if len(sub) == 0:
                rows.append(dict(stratum=stratum, feature=f, n=0))
                continue
            if f == "recovery_time_min" and "end_type_det" in sub:
                sub = sub[(sub.end_type_det != "no_rise") & (sub.end_type_ref != "no_rise")]
            d, r = sub[f"{f}_det"].to_numpy(float), sub[f"{f}_ref"].to_numpy(float)
            diff = d - r
            bias, sd = diff.mean(), diff.std(ddof=1) if len(diff) > 1 else np.nan
            rows.append(dict(stratum=stratum, feature=f, n=len(sub),
                             mean_det=d.mean(), mean_ref=r.mean(), ICC_A1=icc_a1(d, r),
                             BA_bias=bias, BA_loa_low=bias - 1.96 * sd, BA_loa_high=bias + 1.96 * sd))
    out = pd.DataFrame(rows)
    if extra:
        for k, v in extra.items():
            out.insert(0, k, v)
    return out


# ---------------------------------------------------------------- plots
LABELS = {"peak_time_min": "Peak time from anchor (min)", "peak_height": "Peak height above baseline (mg/dL)",
          "iauc": "iAUC above baseline (mg/dL·min)", "recovery_time_min": "Recovery time, peak to end (min)"}
COLORS = {"healthy": "#2a78d6", "prediabetes": "#eb6834", "T2D": "#1baf7a"}
MARKERS = {"healthy": "o", "prediabetes": "s", "T2D": "^"}


def bland_altman_plot(pairs, title, path, note="PROVISIONAL segmentation"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ok = pairs[pairs.featurised]
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), constrained_layout=True)
    for ax, f in zip(axes.flat, FEATURES):
        d, r = ok[f"{f}_det"], ok[f"{f}_ref"]
        mean, diff = (d + r) / 2, d - r
        for g in GROUPS:
            m = ok.group == g
            ax.scatter(mean[m], diff[m], s=22, marker=MARKERS[g], color=COLORS[g], alpha=0.75,
                       edgecolors="white", linewidths=0.6, label=f"{g} (n={m.sum()})")
        bias, sd = diff.mean(), diff.std(ddof=1)
        for y, ls in [(bias, "-"), (bias - 1.96 * sd, "--"), (bias + 1.96 * sd, "--")]:
            ax.axhline(y, color="#52514e", lw=1.2, ls=ls)
        ax.text(1.0, bias, f" bias {bias:.1f}", va="bottom", ha="right", fontsize=8,
                color="#0b0b0b", transform=ax.get_yaxis_transform())
        ax.text(1.0, bias + 1.96 * sd, f" +1.96 SD {bias + 1.96 * sd:.1f}", va="bottom", ha="right",
                fontsize=8, color="#52514e", transform=ax.get_yaxis_transform())
        ax.text(1.0, bias - 1.96 * sd, f" -1.96 SD {bias - 1.96 * sd:.1f}", va="top", ha="right",
                fontsize=8, color="#52514e", transform=ax.get_yaxis_transform())
        ax.axhline(0, color="#d6d5d0", lw=0.8, zorder=0)
        ax.set_title(LABELS[f], fontsize=10, color="#0b0b0b")
        ax.set_xlabel("Mean of detector and reference", fontsize=9, color="#52514e")
        ax.set_ylabel("Detector − reference", fontsize=9, color="#52514e")
        ax.tick_params(labelsize=8, colors="#52514e")
        for s in ["top", "right"]:
            ax.spines[s].set_visible(False)
        ax.grid(axis="y", color="#ecebe7", lw=0.6)
    axes.flat[0].legend(fontsize=8, frameon=False, loc="upper left")
    fig.suptitle(f"{title}  (n = {len(ok)} TP pairs; {note})", fontsize=11)
    fig.savefig(path, dpi=130)
    plt.close(fig)
