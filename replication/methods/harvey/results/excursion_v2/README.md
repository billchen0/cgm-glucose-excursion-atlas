# Harvey (GRID): shared excursion definition (excursion_v2)

## Summary

- Harvey GRID on CGMacros (Dexcom, 42 participants), test data, our matching window (-30 to +120 min).
- One shared excursion definition drives the merge rule excursion_end and the recovery features.
- Candidate main rule: excursion_end. It needs no meal log.
- Route B, excursion_end: Sens 77.4 [73.6, 80.7] %, Prec 71.5 [66.0, 77.2] %, F2 0.761 [0.729, 0.792], FP/day 0.61 [0.46, 0.79].
- Recovery-time ICC, Route B, excursion_end: 0.74 new vs 0.63 provisional.
- % censored at 180 min, Route B, excursion_end: reference anchors healthy 15.3, prediabetes 33.8, T2D 36.0; detector anchors healthy 8.5, prediabetes 19.1, T2D 27.5.
- The excursion definition is frozen as of 2026-10-01. Later changes go to sensitivity analyses only.

## Rules

Route A and B, our matching rule. Applied to detections before scoring.

| Rule | What it does | Needs meal log? | Role |
|---|---|---|---|
| tp_lockout | Ignore unmatched detections within 120 min after a TP (Hochsmann 2026). | yes | reference only |
| excursion_end | Merge detections until the shared excursion end (below). | no | candidate main |
| refractory | Drop detections <= 120 min after the previous kept one. | no | sensitivity |
| meal_window_max_peak | Keep the highest-peak detection per Lim 2026 meal window. | no | sensitivity |

## Excursion definition

Code: `common/evaluation/excursion.py`. Input: an anchor a and the QC'd 1-min glucose.
The anchor is a detection (detector) or the logged meal start (reference).

- Baseline b = min glucose over the valid minutes in [a - 60 min, a].
- Running peak P(t) = max glucose in (a, t]. If glucose later exceeds P, P updates.
- Rise gate: an end counts only once P(t) - b >= 10 mg/dL.
- Fall requirement: any end also needs P(t) - glucose(t) >= 0.50 * (P(t) - b).
- The excursion ends at the earliest of:
  1. Return: glucose(t) <= b + max(10 mg/dL, 0.20 * (P(t) - b)), after the time of P(t).
  2. Trough: a local minimum m after the peak, confirmed when glucose rises to >= m + 10 mg/dL within 30 min. The end is the time of m. A dip under 50 % of the rise is not an end, so a double peak stays one excursion.
  3. Censor: a + 180 min.
- A QC gap never counts as a return or a trough. Missing minutes in the trough confirmation mean no confirmation.
- End types: returned, trough, trough_interrupted, censored, no_rise.
  - trough_interrupted: a trough followed by a new start. Detector: a raw detection in (t_m, t_m + 30]. Reference: any logged food entry (any type) in [t_m - 30, t_m + 30].
  - no_rise: glucose never rose 10 mg/dL above b within 180 min.
  - censored: the excursion rose but did not end by a + 180.
- Features: peak = max in (a, end]. Recovery time = end minus peak time. iAUC = area above b from a to the end. Peak time is measured from a. Completeness check unchanged: no missing minute in [a - 30, a + 180].
- Sources: trough end follows Lim 2026 (PPGR end at the wavelet minimum after the peak) and Fernandes 2022 (MAGE, peak to nadir). The 50 % drop that keeps double peaks together follows Archavli 2024. The 10 mg/dL rise matches the Lim 2026 minimum PPGR rise.

**Worked example.** Baseline 90 mg/dL, peak 150 mg/dL, so the rise is 60.
The return tolerance is max(10, 0.20 * 60) = 12, so the return threshold is 90 + 12 = 102 mg/dL.
The fall requirement is 0.50 * 60 = 30, so glucose must be <= 150 - 30 = 120 mg/dL.
A return therefore happens at the first minute after the peak with glucose <= 102.
A trough can end it earlier only at a local minimum <= 120 that is followed by a 10 mg/dL rise within 30 min.

Parameters (`[excursion]` in `common/configs/cgmacros_eval.toml`), fixed and not tuned:

| Name | Value | Meaning |
|---|---|---|
| lookback_min | 60 | Baseline window before the anchor (min) |
| abs_tol_mg_dl | 10 | Minimum return tolerance and rise gate (mg/dL) |
| rel_tol | 0.20 | Return tolerance as a fraction of the rise |
| trough_drop | 0.50 | Minimum fall from the peak, as a fraction of the rise |
| trough_rise_mg_dl | 10 | Rise that confirms a trough (mg/dL) |
| trough_confirm_min | 30 | Time allowed for that rise (min) |
| max_event_min | 180 | Censor time after the anchor (min) |

## Main results, Route B

#### Detection

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. 95 % participant-bootstrap CI in brackets.

| Rule | Sens % | Prec % | F2 | FP/day | Delay median (min) |
|---|---|---|---|---|---|
| excursion_end | 77.4 [73.6, 80.7] | 71.5 [66.0, 77.2] | 0.761 [0.729, 0.792] | 0.61 [0.46, 0.79] | 28 [26, 30] |
| tp_lockout | 82.1 [78.6, 85.3] | 74.9 [69.2, 80.4] | 0.806 [0.775, 0.836] | 0.55 [0.40, 0.72] | 27 [24, 29] |
| refractory | 73.6 [69.7, 77.3] | 80.5 [76.2, 84.9] | 0.749 [0.714, 0.782] | 0.36 [0.27, 0.45] | 29 [27, 32] |
| meal_window_max_peak | 66.8 [62.1, 71.0] | 86.0 [81.8, 89.9] | 0.699 [0.656, 0.739] | 0.22 [0.15, 0.29] | 28 [26, 31] |

#### Sensitivity (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| excursion_end | 74.3 [69.1, 79.8] | 77.3 [67.8, 84.2] | 80.9 [77.5, 84.1] | 6.7 |
| tp_lockout | 81.9 [75.8, 87.9] | 78.8 [70.3, 84.7] | 85.5 [82.4, 88.3] | 6.6 |
| refractory | 70.0 [63.7, 76.7] | 73.9 [64.4, 81.2] | 77.3 [73.0, 80.9] | 7.2 |
| meal_window_max_peak | 66.2 [59.2, 73.7] | 67.5 [58.1, 75.0] | 66.8 [59.2, 74.1] | 1.3 |

#### Precision (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| excursion_end | 64.9 [54.7, 76.1] | 77.0 [68.9, 85.4] | 74.2 [66.3, 82.3] | 12.0 |
| tp_lockout | 73.8 [61.9, 84.5] | 81.2 [75.0, 88.0] | 71.2 [62.7, 80.0] | 10.0 |
| refractory | 80.2 [71.4, 88.8] | 84.8 [79.1, 90.5] | 77.3 [70.8, 84.3] | 7.5 |
| meal_window_max_peak | 84.9 [77.3, 91.8] | 90.1 [84.0, 95.4] | 83.5 [75.6, 90.6] | 6.6 |

#### FP/day by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (per day).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| excursion_end | 0.80 [0.47, 1.23] | 0.46 [0.26, 0.70] | 0.56 [0.35, 0.82] | 0.34 |
| tp_lockout | 0.58 [0.30, 0.97] | 0.36 [0.21, 0.51] | 0.69 [0.42, 1.02] | 0.33 |
| refractory | 0.34 [0.18, 0.54] | 0.26 [0.16, 0.38] | 0.45 [0.28, 0.64] | 0.19 |
| meal_window_max_peak | 0.24 [0.12, 0.37] | 0.15 [0.07, 0.24] | 0.26 [0.15, 0.41] | 0.12 |

#### Recovery agreement, ICC(A,1) (new definition)

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs; recovery time leaves out pairs with no_rise at either anchor.

| Rule | n pairs | n (recovery time) | Recovery time | Peak height | iAUC | Peak time |
|---|---|---|---|---|---|---|
| excursion_end | 511 | 503 | 0.74 | 0.91 | 0.94 | 0.54 |
| tp_lockout | 542 | 532 | 0.75 | 0.91 | 0.93 | 0.54 |
| refractory | 486 | 478 | 0.72 | 0.90 | 0.92 | 0.52 |
| meal_window_max_peak | 441 | 436 | 0.75 | 0.92 | 0.95 | 0.55 |

#### Recovery time: agreement, new vs provisional

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs used (new). Bias = detector minus reference (min).

| Rule | n | ICC new | ICC provisional | Bias new (min) | 95 % LoA new (min) |
|---|---|---|---|---|---|
| excursion_end | 503 | 0.74 | 0.63 | 12 | -38 to 61 |
| tp_lockout | 532 | 0.75 | 0.64 | 11 | -37 to 59 |
| refractory | 478 | 0.72 | 0.61 | 12 | -40 to 63 |
| meal_window_max_peak | 436 | 0.75 | 0.61 | 11 | -38 to 59 |

#### Recovery time by stratum, excursion_end (new definition)

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs used. Bias = detector minus reference (min).

| Stratum | n | ICC | Bias (min) | 95 % LoA (min) |
|---|---|---|---|---|
| overall | 503 | 0.74 | 12 | -38 to 61 |
| healthy | 175 | 0.79 | 7 | -38 to 52 |
| prediabetes | 155 | 0.77 | 13 | -34 to 61 |
| T2D | 173 | 0.63 | 14 | -40 to 68 |
| breakfast | 278 | 0.87 | 5 | -26 to 35 |
| lunch | 225 | 0.64 | 20 | -41 to 81 |

The detector over-estimates recovery time more in prediabetes, T2D and lunch.

#### End type by group, excursion_end, detector anchor

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs. Values are % of n.

| Group | n | Returned | Trough | Trough interrupted | Censored | No rise |
|---|---|---|---|---|---|---|
| overall | 511 | 62.4 | 12.9 | 6.3 | 18.4 | 0.0 |
| healthy | 176 | 72.7 | 13.1 | 5.7 | 8.5 | 0.0 |
| prediabetes | 157 | 61.1 | 12.1 | 7.6 | 19.1 | 0.0 |
| T2D | 178 | 53.4 | 13.5 | 5.6 | 27.5 | 0.0 |

#### End type by group, excursion_end, reference anchor (logged meal start)

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs. Values are % of n.

| Group | n | Returned | Trough | Trough interrupted | Censored | No rise |
|---|---|---|---|---|---|---|
| overall | 511 | 55.4 | 14.1 | 0.8 | 28.2 | 1.6 |
| healthy | 176 | 67.0 | 16.5 | 0.6 | 15.3 | 0.6 |
| prediabetes | 157 | 52.2 | 12.1 | 0.6 | 33.8 | 1.3 |
| T2D | 178 | 46.6 | 13.5 | 1.1 | 36.0 | 2.8 |

#### Recovery time (min) by end type, excursion_end, detector anchor

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Median [IQR] (n = TP pairs).

| Group | Returned | Trough | Trough interrupted | Censored | No rise |
|---|---|---|---|---|---|
| overall | 49 [25, 79] (319) | 45 [35, 69] (66) | 55 [40, 78] (32) | 105 [75, 125] (94) |  |
| healthy | 37 [20, 62] (128) | 45 [32, 68] (23) | 50 [36, 68] (10) | 125 [78, 138] (15) |  |
| prediabetes | 61 [27, 104] (96) | 45 [35, 52] (19) | 60 [51, 88] (12) | 112 [79, 134] (30) |  |
| T2D | 58 [32, 80] (95) | 55 [40, 76] (24) | 48 [41, 70] (10) | 100 [65, 115] (49) |  |

#### Recovery time (min) by end type, excursion_end, reference anchor

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Median [IQR] (n = TP pairs).

| Group | Returned | Trough | Trough interrupted | Censored | No rise |
|---|---|---|---|---|---|
| overall | 36 [19, 61] (283) | 45 [33, 60] (72) | 58 [36, 80] (4) | 82 [52, 99] (144) | 174 [126, 179] (8) |
| healthy | 29 [17, 50] (118) | 40 [30, 65] (29) | 95 [95, 95] (1) | 94 [68, 108] (27) | 179 [179, 179] (1) |
| prediabetes | 42 [20, 76] (82) | 45 [32, 62] (19) | 40 [40, 40] (1) | 90 [52, 102] (53) | 137 [116, 158] (2) |
| T2D | 43 [22, 63] (83) | 45 [35, 55] (24) | 50 [38, 62] (2) | 74 [49, 88] (64) | 168 [126, 179] (5) |

#### Merging by group, excursion_end

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Raw = all detections at the locked parameters, all day.

| Group | Raw detections | % merged | Events |
|---|---|---|---|
| overall | 2224 | 23.9 | 1693 |
| healthy | 755 | 16.3 | 632 |
| prediabetes | 692 | 21.7 | 542 |
| T2D | 777 | 33.2 | 519 |

## Locked parameters, Route B (all-participant set)

Route B, tuned on all 42 participants; candidate lock for AI-READI; no held-out score.

| Rule | tau_F | G_min | G'_min,3 | G'_min,2 | Forced grid edges |
|---|---|---|---|---|---|
| excursion_end | 5 | 105 | 0.8 | 0.8 | G'_min,2 |
| tp_lockout | 4 | 100 | 0.8 | 0.8 | tau_F, G_min, G'_min,2 |
| refractory | 5 | 100 | 0.8 | 0.8 | G_min, G'_min,2 |
| meal_window_max_peak | 5 | 105 | 0.8 | 0.8 | G'_min,2 |

Forced grid edges are parameters that every tied grid point shares. G'_min,2 = 0.8 sits on the lower grid edge for every rule. With G'_min,2 = 0.8, G'_min,3 has no effect and its value comes from the grid order.

## Reading notes

- Route B: excursion_end Sens 77.4 % vs tp_lockout 82.1 %; FP/day 0.61 vs 0.55.
- Recovery-time ICC (new) is 0.72 to 0.75 across rules (Route B). Provisional: 0.61 to 0.64.
- excursion_end recovery-time bias: breakfast 5 min, lunch 20 min (Route B).
- excursion_end peak height: ICC 0.91, bias +5.2 mg/dL (Route B).
- Detector anchors were never no_rise. T2D has the most censored excursions at both anchors (Route B).

## Appendix

### Route A (per-participant split)

#### Detection

Route A, test data (per-participant test days), 42 participants, 167 scored days. 95 % participant-bootstrap CI in brackets.

| Rule | Sens % | Prec % | F2 | FP/day | Delay median (min) |
|---|---|---|---|---|---|
| excursion_end | 72.4 [67.3, 77.7] | 75.8 [70.4, 81.1] | 0.730 [0.685, 0.775] | 0.46 [0.33, 0.61] | 28 [26, 31] |
| tp_lockout | 76.0 [70.7, 81.3] | 79.1 [75.3, 83.1] | 0.766 [0.721, 0.812] | 0.40 [0.31, 0.49] | 27 [25, 30] |
| refractory | 69.7 [63.5, 75.5] | 80.0 [75.9, 84.5] | 0.715 [0.661, 0.768] | 0.35 [0.26, 0.43] | 28 [26, 31] |
| meal_window_max_peak | 66.4 [60.1, 72.8] | 86.0 [81.0, 91.2] | 0.695 [0.637, 0.756] | 0.22 [0.14, 0.29] | 28 [26, 31] |

#### Sensitivity (%) by group

Route A, test data (per-participant test days), 42 participants, 167 scored days. Healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| excursion_end | 68.3 [59.2, 77.5] | 73.3 [62.1, 83.0] | 75.9 [69.6, 82.1] | 7.6 |
| tp_lockout | 70.0 [60.0, 80.0] | 79.2 [69.9, 86.5] | 79.5 [73.2, 85.7] | 9.5 |
| refractory | 61.7 [50.0, 73.3] | 73.3 [62.7, 82.5] | 75.0 [67.9, 82.1] | 13.3 |
| meal_window_max_peak | 61.7 [49.2, 73.3] | 68.3 [58.4, 78.0] | 69.6 [60.7, 77.7] | 8.0 |

#### Precision (%) by group

Route A, test data (per-participant test days), 42 participants, 167 scored days. Healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| excursion_end | 68.9 [61.3, 78.0] | 82.2 [71.2, 94.0] | 78.0 [69.2, 86.0] | 13.3 |
| tp_lockout | 78.5 [73.2, 84.4] | 79.2 [71.4, 87.9] | 79.5 [73.3, 86.8] | 1.0 |
| refractory | 76.3 [67.7, 84.4] | 82.2 [76.0, 89.8] | 81.5 [74.1, 89.5] | 5.9 |
| meal_window_max_peak | 80.4 [70.3, 88.9] | 88.5 [79.0, 97.3] | 89.7 [82.2, 96.4] | 9.2 |

#### FP/day by group

Route A, test data (per-participant test days), 42 participants, 167 scored days. Healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (per day).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| excursion_end | 0.62 [0.37, 0.88] | 0.31 [0.08, 0.60] | 0.43 [0.25, 0.64] | 0.30 |
| tp_lockout | 0.38 [0.25, 0.52] | 0.41 [0.22, 0.63] | 0.41 [0.25, 0.55] | 0.03 |
| refractory | 0.38 [0.25, 0.53] | 0.31 [0.16, 0.47] | 0.34 [0.18, 0.50] | 0.07 |
| meal_window_max_peak | 0.30 [0.17, 0.43] | 0.18 [0.04, 0.33] | 0.16 [0.05, 0.29] | 0.14 |

#### Recovery agreement, ICC(A,1) (new definition)

Route A, test data (per-participant test days), 42 participants, 167 scored days. n = TP pairs; recovery time leaves out pairs with no_rise at either anchor.

| Rule | n pairs | n (recovery time) | Recovery time | Peak height | iAUC | Peak time |
|---|---|---|---|---|---|---|
| excursion_end | 241 | 237 | 0.79 | 0.93 | 0.95 | 0.58 |
| tp_lockout | 253 | 248 | 0.77 | 0.93 | 0.95 | 0.56 |
| refractory | 232 | 227 | 0.78 | 0.92 | 0.94 | 0.55 |
| meal_window_max_peak | 221 | 219 | 0.78 | 0.93 | 0.95 | 0.56 |

#### Recovery time: agreement, new vs provisional

Route A, test data (per-participant test days), 42 participants, 167 scored days. n = TP pairs used (new). Bias = detector minus reference (min).

| Rule | n | ICC new | ICC provisional | Bias new (min) | 95 % LoA new (min) |
|---|---|---|---|---|---|
| excursion_end | 237 | 0.79 | 0.61 | 11 | -32 to 54 |
| tp_lockout | 248 | 0.77 | 0.60 | 12 | -32 to 56 |
| refractory | 227 | 0.78 | 0.61 | 12 | -31 to 55 |
| meal_window_max_peak | 219 | 0.78 | 0.58 | 11 | -34 to 55 |

#### Recovery time by stratum, excursion_end (new definition)

Route A, test data (per-participant test days), 42 participants, 167 scored days. n = TP pairs used. Bias = detector minus reference (min).

| Stratum | n | ICC | Bias (min) | 95 % LoA (min) |
|---|---|---|---|---|
| overall | 237 | 0.79 | 11 | -32 to 54 |
| healthy | 81 | 0.89 | 5 | -27 to 37 |
| prediabetes | 73 | 0.80 | 12 | -31 to 56 |
| T2D | 83 | 0.61 | 15 | -35 to 65 |
| breakfast | 138 | 0.91 | 4 | -22 to 30 |
| lunch | 99 | 0.67 | 21 | -34 to 75 |

The detector over-estimates recovery time more in prediabetes, T2D and lunch.

#### End type by group, excursion_end, detector anchor

Route A, test data (per-participant test days), 42 participants, 167 scored days. n = TP pairs. Values are % of n.

| Group | n | Returned | Trough | Trough interrupted | Censored | No rise |
|---|---|---|---|---|---|---|
| overall | 241 | 62.2 | 15.4 | 3.7 | 18.7 | 0.0 |
| healthy | 82 | 74.4 | 15.9 | 2.4 | 7.3 | 0.0 |
| prediabetes | 74 | 59.5 | 16.2 | 6.8 | 17.6 | 0.0 |
| T2D | 85 | 52.9 | 14.1 | 2.4 | 30.6 | 0.0 |

#### End type by group, excursion_end, reference anchor (logged meal start)

Route A, test data (per-participant test days), 42 participants, 167 scored days. n = TP pairs. Values are % of n.

| Group | n | Returned | Trough | Trough interrupted | Censored | No rise |
|---|---|---|---|---|---|---|
| overall | 241 | 55.2 | 13.7 | 0.8 | 28.6 | 1.7 |
| healthy | 82 | 67.1 | 19.5 | 1.2 | 11.0 | 1.2 |
| prediabetes | 74 | 51.4 | 9.5 | 1.4 | 36.5 | 1.4 |
| T2D | 85 | 47.1 | 11.8 | 0.0 | 38.8 | 2.4 |

#### Recovery time (min) by end type, excursion_end, detector anchor

Route A, test data (per-participant test days), 42 participants, 167 scored days. Median [IQR] (n = TP pairs).

| Group | Returned | Trough | Trough interrupted | Censored | No rise |
|---|---|---|---|---|---|
| overall | 52 [25, 84] (150) | 45 [35, 65] (37) | 55 [55, 85] (9) | 100 [75, 125] (45) |  |
| healthy | 29 [18, 55] (61) | 44 [30, 65] (13) | 92 [74, 111] (2) | 102 [76, 129] (6) |  |
| prediabetes | 77 [38, 111] (44) | 40 [34, 56] (12) | 60 [55, 85] (5) | 115 [90, 135] (13) |  |
| T2D | 61 [37, 81] (45) | 55 [45, 76] (12) | 50 [48, 52] (2) | 100 [65, 115] (26) |  |

#### Recovery time (min) by end type, excursion_end, reference anchor

Route A, test data (per-participant test days), 42 participants, 167 scored days. Median [IQR] (n = TP pairs).

| Group | Returned | Trough | Trough interrupted | Censored | No rise |
|---|---|---|---|---|---|
| overall | 37 [20, 63] (133) | 45 [35, 60] (33) | 68 [54, 81] (2) | 86 [53, 100] (69) | 147 [118, 171] (4) |
| healthy | 28 [17, 46] (55) | 45 [30, 65] (16) | 95 [95, 95] (1) | 92 [45, 117] (9) | 179 [179, 179] (1) |
| prediabetes | 54 [21, 84] (38) | 35 [32, 58] (7) | 40 [40, 40] (1) | 91 [60, 102] (27) | 95 [95, 95] (1) |
| T2D | 43 [28, 65] (40) | 50 [45, 55] (10) |  | 79 [50, 88] (33) | 147 [136, 158] (2) |

#### Merging by group, excursion_end

Route A, test data (per-participant test days), 42 participants, 167 scored days. Raw = all detections at the locked parameters, all day.

| Group | Raw detections | % merged | Events |
|---|---|---|---|
| overall | 937 | 20.5 | 745 |
| healthy | 335 | 12.2 | 294 |
| prediabetes | 289 | 19.0 | 234 |
| T2D | 313 | 30.7 | 217 |

### Locked parameters, all sets

Route B: one set per fold plus the all-participant set. Forced grid edges as above.

| Rule | Set | tau_F | G_min | G'_min,3 | G'_min,2 | Forced grid edges |
|---|---|---|---|---|---|---|
| excursion_end | fold_0 | 5 | 105 | 0.8 | 0.8 | G'_min,2 |
| excursion_end | fold_1 | 7 | 105 | 0.8 | 0.8 | G'_min,2 |
| excursion_end | fold_2 | 5 | 105 | 0.8 | 0.8 | G'_min,2 |
| excursion_end | fold_3 | 4 | 100 | 0.8 | 0.8 | tau_F, G_min, G'_min,2 |
| excursion_end | fold_4 | 6 | 100 | 0.8 | 0.8 | G_min, G'_min,2 |
| excursion_end | all_participants | 5 | 105 | 0.8 | 0.8 | G'_min,2 |
| tp_lockout | fold_0 | 4 | 100 | 0.8 | 0.8 | tau_F, G_min, G'_min,2 |
| tp_lockout | fold_1 | 4 | 100 | 0.8 | 0.8 | tau_F, G_min, G'_min,2 |
| tp_lockout | fold_2 | 4 | 100 | 0.8 | 0.8 | tau_F, G_min, G'_min,2 |
| tp_lockout | fold_3 | 4 | 100 | 0.8 | 0.8 | tau_F, G_min, G'_min,2 |
| tp_lockout | fold_4 | 4 | 100 | 0.8 | 0.8 | tau_F, G_min, G'_min,2 |
| tp_lockout | all_participants | 4 | 100 | 0.8 | 0.8 | tau_F, G_min, G'_min,2 |
| refractory | fold_0 | 5 | 100 | 0.8 | 0.8 | G_min, G'_min,2 |
| refractory | fold_1 | 7 | 105 | 0.8 | 0.8 | G'_min,2 |
| refractory | fold_2 | 5 | 100 | 0.8 | 0.8 | G_min, G'_min,2 |
| refractory | fold_3 | 6 | 100 | 0.8 | 0.8 | G_min, G'_min,2 |
| refractory | fold_4 | 6 | 100 | 0.8 | 0.8 | G_min, G'_min,2 |
| refractory | all_participants | 5 | 100 | 0.8 | 0.8 | G_min, G'_min,2 |
| meal_window_max_peak | fold_0 | 4 | 105 | 0.8 | 1.3 | tau_F, G'_min,3 |
| meal_window_max_peak | fold_1 | 7 | 105 | 0.8 | 0.8 | G'_min,2 |
| meal_window_max_peak | fold_2 | 5 | 105 | 0.8 | 0.8 | G'_min,2 |
| meal_window_max_peak | fold_3 | 5 | 105 | 0.8 | 0.8 | G'_min,2 |
| meal_window_max_peak | fold_4 | 5 | 105 | 0.8 | 0.8 | G'_min,2 |
| meal_window_max_peak | all_participants | 5 | 105 | 0.8 | 0.8 | G'_min,2 |

Route A: one set per participant (n = 42). Mean +/- SD, and the number of participants with a forced edge.

| Rule | tau_F | G_min | G'_min,3 | G'_min,2 |
|---|---|---|---|---|
| excursion_end | 4.71 +/- 1.20 (16) | 105.71 +/- 10.45 (8) | 0.88 +/- 0.16 (4) | 1.04 +/- 0.30 (16) |
| tp_lockout | 4.52 +/- 0.99 (19) | 104.40 +/- 10.49 (12) | 0.86 +/- 0.15 (4) | 0.95 +/- 0.24 (20) |
| refractory | 4.62 +/- 1.15 (20) | 105.36 +/- 11.17 (10) | 0.86 +/- 0.16 (6) | 0.98 +/- 0.25 (18) |
| meal_window_max_peak | 4.69 +/- 1.20 (15) | 103.93 +/- 10.51 (10) | 0.88 +/- 0.18 (6) | 1.09 +/- 0.35 (15) |

### Step 0 findings (provisional recovery rule)

- Recovery time is measured from the peak to the end.
- The return rule had no tolerance: glucose <= baseline.
- iAUC runs from the anchor to the end, above baseline.
- Peak time is measured from the anchor.
- The baseline was the mean of [a - 30, a). The peak was the max over the full 180 min.

### Two fixes made after seeing results (2026-10-01)

Neither adds a parameter. Details: `common/docs/deviations.md` (X1, X6) and `methods/harvey/docs/deviations.md`.

1. Rise gate. The first specification had no rise requirement. 62 % of reference excursions (Route B) ended within 5 min of the meal start, before the rise. The gate reuses abs_tol.
2. Fall requirement. With the gate alone, a rise just over 10 mg/dL and a 1 mg/dL dip counted as a return. 6.6 % of reference excursions that rose still ended within 15 min (Route B). After the fix: 2.4 %. It reuses trough_drop.

### Files

| File | Content |
|---|---|
| `comparison.csv`, `comparison.md` | All four rules, Route A and B, all strata, 95 % CI (tables a to h) |
| `detection_counts.csv` | Raw, removed by the rule, ignored by the TP lockout, kept and scored |
| `end_type_by_group.csv` | End type % by rule, route, anchor and group (TP pairs) |
| `recovery_time_by_end_type.csv` | Recovery time median and IQR by rule, route, anchor, group, end type |
| `recovery_icc_no_rise_excluded.csv` | Pairs left out of the recovery-time ICC |
| `merge_by_group.csv` | excursion_end merging by group |
| `<rule>/summary*.csv`, `params/`, `recovery_agreement.csv`, `plots/` | Per-rule outputs (new definition) |
| `excursion_end/recovery_agreement_provisional.csv` | Provisional agreement for excursion_end detections |
| `<rule>/detections.csv`, `meals.csv`, `recovery_features.csv` | Row-level, not committed |

### Run

From `replication/`:

```
python methods/harvey/src/run_harvey_excursion_v2.py
python methods/harvey/src/run_harvey_excursion_v2.py --docs-only
```

The first runs the pipeline (about 3 min, deterministic). It reads `reference_tp_lockout/` and `peak_rules/` and never writes to them. The second rebuilds `comparison.md` and this README from the saved outputs.
