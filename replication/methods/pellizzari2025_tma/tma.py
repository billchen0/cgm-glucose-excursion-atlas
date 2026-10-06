"""Template Matching Algorithm (TMA), Pellizzari et al., Sci Rep 2025;15:7797.

Python port of the logic in github.com/elisapellizzari/TMA (commit 55baa8b). The
repository has no license file, so no code is copied verbatim; each function
below re-implements one MATLAB file and says which. Indices are 0-based here, where
MATLAB is 1-based; each conversion is noted where it happens.

Taken from the repository (not from the paper text):
* zero-phase filter  = butter(4, 0.25) + filtfilt, applied to the gap-filled trace
* glucose is centred on the subject's mean *training* glucose, the template on its
  own mean
* cross-correlation  = filter(fliplr(template), 1, x), then advanced by `delay`
  samples. The recovered personalized_template.mat files (git history, commit
  bc2b3c2) show `delay` == 0-based index of the template's peak sample
  (e.g. PBHF00001: len 21, peak at 0-based idx 9, delay 9)
* the first len(template) samples are NaN (burn-in), NaNs are restored at missing
  samples, and len(template)+1 samples after every NaN island are NaN
* events = findpeaks(cc, 'MinPeakHeight', TH); alarms are silenced 1 h before
  every NaN island and in the windows of meals that sit next to NaN islands
* native evaluation: meal window = [meal - 3, meal + 24] samples (-15..+120 min)
  on the cc index; first peak in the window = TP (and consumed), no peak = FN,
  every other peak = FP (evaluatePerformances.m)

Not in the repository (the templates and thresholds were built outside it) and
therefore implemented here from the paper text:
* template selection (select_template_curves) and peak-aligned averaging
* TH grid search (min..max of cc on the training set, maximise F1)
* meal-time estimate = similarity peak - half the template length
"""
import numpy as np
from scipy.signal import butter, filtfilt, lfilter

SAMPLE_MIN = 5
WIN_BEFORE = 3    # samples, 15 min   (evaluatePerformances.m)
WIN_AFTER = 24    # samples, 120 min
SILENCE_BEFORE_NAN = 12   # samples, 1 h (retrieveCategoricalCrossCorrelation.m)
MEAL_BEFORE_NAN = 24      # samples, 2 h


# ---------------------------------------------------------------- helpers
def nan_islands(x):
    """AGATA findNanIslands(TT, 1): (start, end) of every NaN run, inclusive, 0-based."""
    isn = np.isnan(x).astype(int)
    if not isn.any():
        return np.array([], int), np.array([], int)
    d = np.diff(np.r_[0, isn, 0])
    return np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1


def interpolate_short_gaps(x, max_gap_samples=5):
    """Paper, 'Pre-processing of data': missing runs < 30 min are linearly interpolated."""
    x = x.copy()
    s, e = nan_islands(x)
    for a, b in zip(s, e):
        if b - a + 1 <= max_gap_samples and a > 0 and b < len(x) - 1:
            x[a:b + 1] = np.interp(np.arange(a, b + 1), [a - 1, b + 1], [x[a - 1], x[b + 1]])
    return x


def fill_missing_linear_nearest(x):
    """MATLAB fillmissing(x, 'linear', 'EndValues', 'nearest')."""
    ok = ~np.isnan(x)
    return np.interp(np.arange(len(x)), np.flatnonzero(ok), x[ok])


def find_peaks_matlab(y):
    """Local maxima as MATLAB findpeaks returns them (before MinPeakHeight):
    plateaus collapse to their first sample, and samples next to NaN (or at the
    edges) cannot be peaks."""
    yt = np.r_[np.nan, y, np.nan]
    idx = np.arange(len(yt))
    fin = ~np.isnan(yt)
    neq = np.r_[True, (yt[:-1] != yt[1:]) & (fin[:-1] | fin[1:])]
    it = idx[neq]
    with np.errstate(invalid="ignore"):
        s = np.sign(np.diff(yt[it]))
        imax = 1 + np.flatnonzero(np.diff(s) < 0)
    return it[imax] - 1


# ------------------------------------------------ calculateCrossCorrelation.m
def cross_correlation(glucose, mean_glucose, template, delay):
    template = np.asarray(template, float) - np.mean(template)
    g = np.asarray(glucose, float) - mean_glucose
    starts, ends = nan_islands(g)
    nan_idx = np.isnan(g)
    filled = fill_missing_linear_nearest(g)
    b, a = butter(4, 0.25)
    filt = filtfilt(b, a, filled)          # zero-phase
    y = lfilter(template[::-1], 1.0, filt)
    L, M = len(y), len(template)
    cc = np.zeros(L)
    cc[:L - delay] = y[delay:]
    cc[:M] = np.nan                        # MATLAB cc(1:length(template)) = NaN
    cc[nan_idx] = np.nan
    for e in ends:                         # MATLAB cc(nanEnd:min(nanEnd+l, end)) = NaN
        cc[e:min(e + M, L - 1) + 1] = np.nan
    return cc


# ------------------------------------- retrieveCategoricalCrossCorrelation.m
def non_evaluable_meals(glucose, meal_idx, M):
    """Meals the MATLAB code silences (`to_be_silenced`): within 2 h before a NaN
    island or within one template length after it. Meals inside an island are added
    (the authors removed those in pre-processing). Returns a boolean mask."""
    s, e = nan_islands(glucose)
    bad = np.zeros(len(meal_idx), bool)
    for a, b in zip(s, e):
        bad |= (meal_idx >= max(a - MEAL_BEFORE_NAN, 0)) & (meal_idx <= min(b + M, len(glucose) - 1))
    return bad


def silence_mask(glucose, silenced_meal_idx, n):
    """True where alarms are silenced."""
    m = np.zeros(n, bool)
    s, _ = nan_islands(glucose)
    for a in s:
        m[max(a - SILENCE_BEFORE_NAN, 0):a + 1] = True
    for mi in silenced_meal_idx:
        m[max(mi - WIN_BEFORE, 0):mi + WIN_AFTER + 1] = True
    return m


def outside_window_mask(times, start_min, end_min):
    """True for samples whose clock time (minutes after midnight) is outside the
    daily scoring window [start_min, end_min]. Events there are not evaluated:
    neither TP nor FP (breakfast+lunch evaluation, run_bl.py)."""
    tod = times.hour * 60 + times.minute
    return np.asarray((tod < start_min) | (tod > end_min))


def detect(cc, threshold, silenced):
    """Peak indices of cc above TH, silenced alarms removed."""
    pk = find_peaks_matlab(cc)
    pk = pk[cc[pk] >= threshold]           # findpeaks MinPeakHeight is inclusive
    return pk[~silenced[pk]]


# ---------------------------------------------------- evaluatePerformances.m
def evaluate_native(peaks, meal_idx, n):
    """Pellizzari's own event counting on cc indices."""
    cat = np.zeros(n, int)
    cat[peaks] = 1
    tp, fn, onset_pairs = 0, 0, []
    for m in np.sort(meal_idx):
        w0, w1 = max(0, m - WIN_BEFORE), min(m + WIN_AFTER, n - 1)
        loc = np.flatnonzero(cat[w0:w1 + 1])
        if len(loc):
            tp += 1
            cat[w0 + loc[0]] = 0
            onset_pairs.append((m, w0 + loc[0]))
        else:
            fn += 1
    return tp, int(cat.sum()), fn, onset_pairs


def onset_index(peaks, M):
    """Meal time = similarity peak - half the template length (paper, 'Meal timing
    estimation'). cc is already advanced by `delay`, so cc[n] scores the window
    [n+delay-M+1, n+delay]; with delay ~ M/2 the template's first sample
    (pre-meal baseline) sits ~M/2 samples before the cc peak."""
    return peaks - M // 2


# ------------------------------------------------------ template construction
def candidate_curve(g, i0, next_meal_idx, min_rise, require_isolated, max_len=36):
    """One post-prandial curve starting at the meal sample i0, or None.

    Paper criteria: (1) glucose rises and then decreases, (2) no missing data,
    (3) no compression artefact, (4) starts in the euglycaemic range. The authors
    hand-picked curves; the thresholds below are this replication's choice.
    """
    seg = g[i0:i0 + max_len + 1]
    if len(seg) < max_len + 1 or np.isnan(seg).any():
        return None
    g0 = seg[0]
    if not (70 <= g0 <= 180):
        return None
    ipk = 2 + int(np.argmax(seg[2:25]))          # peak 10..120 min after the meal
    rise = seg[ipk] - g0
    if rise < min_rise:
        return None
    post = seg[ipk + 1:]
    back = np.flatnonzero(post <= g0)
    if len(back):
        iend = ipk + 1 + back[0]
    else:
        iend = ipk + 1 + int(np.argmin(post))
        if seg[ipk] - seg[iend] < 0.5 * rise:
            return None
    if iend - ipk < 3:
        return None
    if require_isolated and next_meal_idx is not None and next_meal_idx <= i0 + iend:
        return None
    return {"curve": seg[:iend + 1], "peak": ipk, "rise": rise}


def select_template_curves(g, meal_idx, n_curves=5, order_by="rise", all_meal_idx=None):
    """Pick n_curves eligible curves, relaxing criteria step by step if fewer are
    eligible. order_by="rise": largest rise first (default, used in the main
    run); "chrono": first eligible meals in time. all_meal_idx: every logged meal,
    used for the "no next meal before the curve ends" check when meal_idx is a
    subset (e.g. breakfast+lunch only). Returns (curves, rule_used)."""
    order = np.sort(meal_idx)
    every = np.sort(meal_idx if all_meal_idx is None else all_meal_idx)
    nxt = {}
    for m in order:
        later = every[every > m]
        nxt[m] = later[0] if len(later) else None
    rules = [(20, True), (10, True), (10, False), (5, False)]
    for min_rise, iso in rules:
        cs = [c for m in order
              if (c := candidate_curve(g, m, nxt[m], min_rise, iso)) is not None]
        if len(cs) >= n_curves:
            break
    if order_by == "rise":
        cs = sorted(cs, key=lambda c: -c["rise"])
    cs = cs[:n_curves]
    return cs, f"rise>={min_rise}mg/dL,isolated={iso}"


def average_aligned(curves, min_fraction=1.0):
    """Peak-aligned average. min_fraction=1.0 keeps only lags where every curve has
    a sample (paper, personalized template); 0.5 truncates where fewer than half
    the curves remain (supplement, population template)."""
    pre = np.array([c["peak"] for c in curves])
    post = np.array([len(c["curve"]) - 1 - c["peak"] for c in curves])
    need = min_fraction * len(curves)
    lags = range(-int(pre.max()), int(post.max()) + 1)
    vals, keep_lags = [], []
    for lag in lags:
        have = [c["curve"][c["peak"] + lag] for c, a, b in zip(curves, pre, post)
                if -a <= lag <= b]
        if len(have) >= need:
            vals.append(np.mean(have))
            keep_lags.append(lag)
    template = np.array(vals)
    delay = -keep_lags[0]                  # 0-based index of the peak sample
    return template, delay


# ------------------------------------------------------------- TH grid search
def grid_search_threshold(items, n_grid=200):
    """items: list of (cc, meal_idx, silenced, lo, hi) training portions (one per
    subject; several subjects pooled for the population threshold).
    Grid from min to max of cc over the training portions; TH maximising pooled F1.
    Ties go to the lowest TH (MATLAB max returns the first index)."""
    allcc = np.concatenate([it[0][it[3]:it[4]] for it in items])
    allcc = allcc[~np.isnan(allcc)]
    grid = np.linspace(allcc.min(), allcc.max(), n_grid)
    pre = []
    for cc, mi, sil, lo, hi in items:
        pk = find_peaks_matlab(cc)
        pk = pk[(pk >= lo) & (pk < hi) & ~sil[pk]]
        pre.append((pk, cc[pk], mi, len(cc)))
    best_th, best_f1 = grid[0], -1.0
    for th in grid:
        TP = FP = FN = 0
        for pk, h, mi, n in pre:
            tp, fp, fn, _ = evaluate_native(pk[h >= th], mi, n)
            TP += tp; FP += fp; FN += fn
        f1 = 2 * TP / (2 * TP + FP + FN) if (TP + FP + FN) else 0.0
        if f1 > best_f1:
            best_th, best_f1 = th, f1
    return best_th, best_f1
