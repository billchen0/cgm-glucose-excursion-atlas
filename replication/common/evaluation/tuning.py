"""Grid tuning (plan v3 section 6).

``grid_day_counts`` scores every grid point on every day once, giving per-day
(TP, FP, FN, delay sum). Route A and Route B then only aggregate day subsets.
Selection: highest F2, then lower FP/day, then shorter mean delay, then grid order.
"""
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from . import postprocess as P
from .scoring import MIN, day_minutes, match_fast, rule_params, scored_meals


def grid_detections(cohort, cfg, det_mod, sampling_min):
    """{day_id: list over grid of detection times in minutes since midnight}."""
    grid = det_mod.param_grid(cfg)
    out = {}
    for day_id, d in cohort.days.iterrows():
        t, g = cohort.day_series(day_id, sampling_min)
        mins = np.asarray((t - d.date) / MIN)
        if hasattr(det_mod, "detect_grid"):
            idx = det_mod.detect_grid(t, g, cfg)
            out[day_id] = [mins[k] for k in idx]
        else:
            out[day_id] = [np.asarray((det_mod.detect(t, g, p) - d.date) / MIN) for p in grid]
    return grid, out


def apply_adjacent(cohort, cfg, grid_det, sampling_min):
    """Apply the configured label-free adjacent-detection rule to every grid point's detections.

    Returns (filtered grid_det, number of detections removed per grid point).
    """
    if P.uses_tp_lockout(cfg):
        return grid_det, None
    out, removed = {}, None
    for day_id, dets in grid_det.items():
        d = cohort.days.loc[day_id]
        t, _ = cohort.day_series(day_id, sampling_min)
        mins = np.asarray((t - d.date) / MIN)
        pk = (P.forward_peak(cohort.series_1min[d.subject], t, P.peak_horizon(cfg))
              if P.needs_peaks(cfg) else np.full(len(t), np.nan))
        cl = P.close_minutes(cohort.series_1min[d.subject], t, d.date, cfg)
        kept = []
        for det in dets:
            j = np.searchsorted(mins, det)
            k = P.keep_mask(det, pk[j], cfg, close_min=cl[j])
            kept.append(det[k])
        if removed is None:
            removed = np.zeros(len(dets), int)
        removed += np.array([len(a) - len(b) for a, b in zip(dets, kept)])
        out[day_id] = kept
    return out, removed


def grid_day_counts(cohort, cfg, rule, grid_det):
    """counts[grid point, day, (TP, FP, FN, delay_sum)] for one matching rule."""
    before, after, lockout = rule_params(cfg, rule)
    dm = day_minutes(cohort, scored_meals(cohort, cfg, rule))
    day_ids = list(cohort.days.index)
    n_grid = len(next(iter(grid_det.values())))
    counts = np.zeros((n_grid, len(day_ids), 4))
    for j, day_id in enumerate(day_ids):
        ws, we, meals = dm[day_id]
        cache = {}
        for i, det in enumerate(grid_det[day_id]):
            key = tuple(x for x in det if ws <= x <= we)
            if key not in cache:
                cache[key] = match_fast(key, meals, before, after, lockout)
            counts[i, j] = cache[key]
    return counts


def objective(tp, fp, fn, dsum, n_days, beta=2.0):
    b2 = beta ** 2
    den = (1 + b2) * tp + b2 * fn + fp
    f = np.where(den > 0, (1 + b2) * tp / np.where(den > 0, den, 1), 0.0)
    delay = np.where(tp > 0, dsum / np.where(tp > 0, tp, 1), np.inf)
    return f, fp / n_days, delay


def select(counts, day_mask, scored, beta=2.0):
    """Best grid index on the days in day_mask (FP/day over days with a scoring window)."""
    c = counts[:, day_mask].sum(axis=1)
    n_days = (day_mask & scored).sum()
    f, fpd, delay = objective(c[:, 0], c[:, 1], c[:, 2], c[:, 3], n_days, beta)
    order = np.lexsort((np.arange(len(f)), delay, fpd, -np.round(f, 12)))
    best = order[0]
    tied = (np.round(f, 12) == np.round(f[best], 12)) & (fpd == fpd[best]) & (delay == delay[best])
    ties = int(tied.sum())
    return int(best), tied, dict(val_F2=float(f[best]), val_FP_per_day=float(fpd[best]),
                           val_delay_mean=float(delay[best]), val_TP=int(c[best, 0]),
                           val_FP=int(c[best, 1]), val_FN=int(c[best, 2]),
                           val_days=int(n_days), n_tied=ties)


def _on_edge(v, ax):
    return np.isclose(v, ax.min()) or np.isclose(v, ax.max())


def grid_edges(params, axes):
    return [k for k, v in params.items() if k in axes and _on_edge(v, axes[k])]


def forced_edges(grid, tied, axes):
    """Edge parameters that every tied grid point shares (not a tie-break artefact)."""
    pts = [grid[i] for i in np.flatnonzero(tied)]
    return [k for k in axes if all(_on_edge(p[k], axes[k]) for p in pts)]


def route_a_split(cohort, cfg):
    """Series day_id -> 'validation' | 'test' (per participant, seeded)."""
    rng = np.random.default_rng(cfg["seed"])
    frac = cfg["tuning"]["route_a_validation_fraction"]
    split = pd.Series("test", index=cohort.days.index)
    for subject in cohort.participants.subject:
        ids = np.array(cohort.days.index[cohort.days.subject == subject])
        ids = ids[rng.permutation(len(ids))]
        split[ids[:int(np.floor(len(ids) * frac))]] = "validation"
    return split


def route_b_folds(cohort, cfg):
    """Series subject -> fold (0..k-1), stratified by glycaemic group."""
    p = cohort.participants
    skf = StratifiedKFold(cfg["tuning"]["route_b_folds"], shuffle=True, random_state=cfg["seed"])
    fold = pd.Series(-1, index=p.subject)
    for k, (_, test) in enumerate(skf.split(p.subject, p.group)):
        fold.iloc[test] = k
    return fold
