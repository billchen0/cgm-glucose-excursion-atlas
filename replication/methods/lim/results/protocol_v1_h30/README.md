# Lim wavelet PPGR, 30 mg/dL: standard protocol (protocol_v1_h30)

## Summary

- Lim wavelet PPGR, 30 mg/dL on CGMacros (Dexcom, 42 participants). Standard protocol (protocol_v1_h30), run on 2026-10-06.
- Main adjacent rule: refractory. Route B only. Matching window -30 to +120 min around the logged meal start. Why refractory: common/docs/deviations.md Z1.
- Main result, Route B: Sens 53.9 [48.6, 59.0] %, Prec 90.8 [86.8, 94.1] %, F2 0.587 [0.534, 0.637], FP/day 0.11 [0.07, 0.16], delay median 22 [17, 26] min.
- Recovery-time ICC(A,1), main rule: 0.72 (n = 356 TP pairs; excursion segmentation).
- tp_lockout (comparison only, uses meal labels): Sens 53.9 [48.6, 59.0] %, Prec 90.8 [86.8, 94.1] %, FP/day 0.11 [0.07, 0.16].
- Locked all_participants set, main rule: Minimum height 30. No forced grid edge.

## Method, sampling and parameters

- Source: Lim et al. A wavelet AI algorithm to automatically identify postprandial glucose responses from continuous glucose monitoring profiles in people without diabetes. J Diabetes Sci Technol 2026;20(3):664-672. https://doi.org/10.1177/19322968261427499
- Implementation: As described in Lim 2026 (Methods, PPGR definition and the four-stage framework). Appendices A-C (Gaussian filter, wavelet details, tie-break) are not in the PDF; those details are defaults (deviations L2-L5). Breakfast and lunch windows only. Fixed parameters, not tuned.
- Each 24-h CGM profile is smoothed with a Gaussian filter and transformed with a Gaussian wavelet (PyWavelets).
- Each wavelet maximum inside a meal window and the next wavelet minimum form a candidate segment. Peak = highest glucose in it; PPGR start = lowest glucose before the peak.
- Segments with height (peak minus start) >= 10 mg/dL are kept; the highest one per window is chosen (ties: earlier start).
- One PPGR per window: breakfast 06:00-11:45 and lunch 12:00-16:00. Detection time = PPGR start.
- Window-limited: at most 2 detections per day, so the method cannot find excursions outside the windows.
- Sampling: 5-min CGM input (native Dexcom readings for 5 min; see common/docs/deviations.md E1).
- Fixed settings (not tuned): sampling_min = 5, gauss_sigma_samples = 2, wavelet = gaus1, wavelet_scale = 15, windows = (('breakfast', '06:00', '11:45'), ('lunch', '12:00', '16:00')).
- Tuned parameters: Minimum height (mg/dL).
- Tuning: F2 (beta = 2). Ties: higher F2, then lower FP/day, then shorter mean delay, then grid order.
- Route B: 5 participant folds stratified by group. Each fold is tuned on the other 4 and scored on its held-out participants. An all_participants set is also tuned once on everyone.

## Grid

Source: Sensitivity run (Lim 2026 sensitivity analysis): minimum height 30 mg/dL, fixed. 1 grid points. Edge hits count the 6 Route B sets (5 folds and all_participants) on the lower or upper grid bound.

| Parameter | Values | n | Edge hits, refractory (main) | Edge hits, tp_lockout (comparison only) |
|---|---|---|---|---|
| Minimum height (mg/dL) | 30 | 1 | fixed (not tuned) | fixed (not tuned) |

A parameter on a grid bound may mean the best value lies outside the grid. Forced edges (shared by every tied grid point) are listed with the locked parameters.

## Detection

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. 95 % participant-bootstrap CI in brackets.

| Rule | Sens % | Prec % | F2 | FP/day | Delay median (min) |
|---|---|---|---|---|---|
| refractory, ours (main) | 53.9 [48.6, 59.0] | 90.8 [86.8, 94.1] | 0.587 [0.534, 0.637] | 0.11 [0.07, 0.16] | 22 [17, 26] |
| tp_lockout, ours (comparison only) | 53.9 [48.6, 59.0] | 90.8 [86.8, 94.1] | 0.587 [0.534, 0.637] | 0.11 [0.07, 0.16] | 22 [17, 26] |
| tp_lockout, review (comparison only) | 48.3 [43.0, 53.7] | 81.4 [76.1, 86.0] | 0.526 [0.472, 0.580] | 0.22 [0.16, 0.28] | 25 [20, 30] |

Rules:

- refractory (main): 120-min refractory after every kept detection, applied before scoring. Label-free.
- tp_lockout (comparison only): 120-min lockout after each TP, applied at scoring (Hochsmann 2026). Uses meal labels.
- Matching rules: ours = -30 to +120 min; review = 0 to +120 min (Hochsmann 2026).

## By group

#### Sensitivity (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 48.9 [40.3, 58.4] | 53.2 [43.8, 61.6] | 60.0 [52.3, 67.6] | 11.0 |
| tp_lockout, ours (comparison only) | 48.9 [40.3, 58.4] | 53.2 [43.8, 61.6] | 60.0 [52.3, 67.6] | 11.0 |
| tp_lockout, review (comparison only) | 40.1 [31.6, 49.8] | 48.3 [39.5, 56.8] | 57.3 [50.0, 65.0] | 17.2 |

#### Precision (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 87.9 [79.9, 94.3] | 94.7 [91.8, 97.7] | 90.4 [82.5, 96.5] | 6.9 |
| tp_lockout, ours (comparison only) | 87.9 [79.9, 94.3] | 94.7 [91.8, 97.7] | 90.4 [82.5, 96.5] | 6.9 |
| tp_lockout, review (comparison only) | 72.0 [61.7, 82.1] | 86.0 [79.0, 92.5] | 86.3 [78.8, 92.6] | 14.3 |

#### FP/day by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (per day).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 0.13 [0.06, 0.22] | 0.06 [0.03, 0.10] | 0.13 [0.05, 0.23] | 0.08 |
| tp_lockout, ours (comparison only) | 0.13 [0.06, 0.22] | 0.06 [0.03, 0.10] | 0.13 [0.05, 0.23] | 0.08 |
| tp_lockout, review (comparison only) | 0.31 [0.19, 0.42] | 0.16 [0.08, 0.24] | 0.18 [0.10, 0.28] | 0.16 |

## By meal

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. FP cannot be assigned to a meal, so only Sens and delay.

| Rule | Sens % breakfast | Delay median breakfast | Sens % lunch | Delay median lunch |
|---|---|---|---|---|
| refractory, ours (main) | 71.0 [61.9, 79.6] | 14 [9, 21] | 37.0 [31.0, 43.0] | 38 [31, 41] |
| tp_lockout, ours (comparison only) | 71.0 [61.9, 79.6] | 14 [9, 21] | 37.0 [31.0, 43.0] | 38 [31, 41] |
| tp_lockout, review (comparison only) | 61.6 [52.7, 70.1] | 18 [12, 24] | 35.2 [29.3, 41.3] | 39 [33, 43] |

## Recovery agreement

Segmentation: excursion (frozen definition, common/docs/deviations.md section X). Detector anchor = detection time; reference anchor = logged meal start.

#### ICC(A,1) by feature

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs with complete data; recovery time leaves out pairs with no_rise at either anchor.

| Rule | n pairs | n (recovery time) | Recovery time | Peak height | iAUC | Peak time |
|---|---|---|---|---|---|---|
| refractory, ours (main) | 356 | 356 | 0.72 | 0.90 | 0.94 | 0.46 |
| tp_lockout, ours (comparison only) | 356 | 356 | 0.72 | 0.90 | 0.94 | 0.46 |
| tp_lockout, review (comparison only) | 319 | 319 | 0.70 | 0.89 | 0.93 | 0.46 |

#### Recovery time by stratum, refractory (main)

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs used. Bias = detector minus reference (min).

| Stratum | n | ICC | Bias (min) | 95 % LoA (min) |
|---|---|---|---|---|
| overall | 356 | 0.72 | 13 | -34 to 60 |
| healthy | 116 | 0.76 | 10 | -37 to 57 |
| prediabetes | 108 | 0.85 | 11 | -25 to 47 |
| T2D | 132 | 0.56 | 17 | -37 to 71 |
| breakfast | 233 | 0.85 | 7 | -26 to 39 |
| lunch | 123 | 0.53 | 25 | -35 to 85 |

## Locked parameters (all_participants)

Route B, tuned once on all 42 participants. Candidate lock for AI-READI. No held-out score.

| Rule | Minimum height | Forced grid edges |
|---|---|---|
| refractory, ours (main) | 30 | none |
| tp_lockout, ours (comparison only) | 30 | none |
| tp_lockout, review (comparison only) | 30 | none |

Fold sets: `<rule>/params/chosen_params_routeB_<matching rule>.json`.

## Comparison with Hochsmann 2026 Table 2 (not like-for-like)

Not reported for this method in Hochsmann 2026 Table 2.

Original paper (Lim 2026: median absolute PPGR start-time error [IQR], not Sens or FP/day; not like-for-like): hall breakfast min 10 [4, 19], cgmacros dexcom breakfast lunch dinner min 14 [6, 29], 36 [19, 63], 28 [11, 56], cgmacros libre breakfast lunch dinner min 15 [7, 27], 26 [14, 47], 18 [9, 39].

## Deviations

- Method: `methods/lim/docs/deviations.md`.
- Framework: `common/docs/deviations.md` (protocol decisions: section Z).

## Files

| File | Content |
|---|---|
| `comparison.csv` | All rules and matching rules, all strata, 95 % CI |
| `detection_counts.csv` | Raw detections, removed by the rule, ignored by the TP lockout, kept and scored |
| `<rule>/summary.csv`, `recovery_agreement.csv`, `params/`, `plots/` | Per-rule outputs |
| `<rule>/detections.csv`, `meals.csv`, `recovery_features.csv` | Row-level, not committed |
| `standard/<run>/` | Standard-format export for the dashboard, not committed |
| `protocol.json` | Protocol settings of this run |

## Run

From `replication/`:

```
python common/run_protocol.py lim
python common/run_protocol.py lim --docs-only
```

The first runs the full protocol and also rewrites `results/method_comparison.md`. The second rebuilds this README and the comparison from the saved outputs.
