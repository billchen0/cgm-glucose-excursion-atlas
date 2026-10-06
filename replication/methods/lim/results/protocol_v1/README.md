# Lim wavelet PPGR: standard protocol (protocol_v1)

## Summary

- Lim wavelet PPGR on CGMacros (Dexcom, 42 participants). Standard protocol (protocol_v1), run on 2026-10-06.
- Main adjacent rule: refractory. Route B only. Matching window -30 to +120 min around the logged meal start. Why refractory: common/docs/deviations.md Z1.
- Main result, Route B: Sens 67.9 [62.8, 72.8] %, Prec 89.2 [85.3, 92.6] %, F2 0.713 [0.664, 0.759], FP/day 0.16 [0.11, 0.22], delay median 25 [20, 30] min.
- Recovery-time ICC(A,1), main rule: 0.67 (n = 447 TP pairs; excursion segmentation).
- tp_lockout (comparison only, uses meal labels): Sens 67.9 [62.8, 72.8] %, Prec 89.2 [85.3, 92.6] %, FP/day 0.16 [0.11, 0.22].
- Locked all_participants set, main rule: Minimum height 10. No forced grid edge.

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

Source: Lim 2026 p. 666: fixed minimum height 10 mg/dL (not tuned); 20 and 30 mg/dL as sensitivity runs. 1 grid points. Edge hits count the 6 Route B sets (5 folds and all_participants) on the lower or upper grid bound.

| Parameter | Values | n | Edge hits, refractory (main) | Edge hits, tp_lockout (comparison only) |
|---|---|---|---|---|
| Minimum height (mg/dL) | 10 | 1 | fixed (not tuned) | fixed (not tuned) |

A parameter on a grid bound may mean the best value lies outside the grid. Forced edges (shared by every tied grid point) are listed with the locked parameters.

## Detection

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. 95 % participant-bootstrap CI in brackets.

| Rule | Sens % | Prec % | F2 | FP/day | Delay median (min) |
|---|---|---|---|---|---|
| refractory, ours (main) | 67.9 [62.8, 72.8] | 89.2 [85.3, 92.6] | 0.713 [0.664, 0.759] | 0.16 [0.11, 0.22] | 25 [20, 30] |
| tp_lockout, ours (comparison only) | 67.9 [62.8, 72.8] | 89.2 [85.3, 92.6] | 0.713 [0.664, 0.759] | 0.16 [0.11, 0.22] | 25 [20, 30] |
| tp_lockout, review (comparison only) | 61.2 [55.9, 66.5] | 80.5 [75.6, 84.7] | 0.643 [0.591, 0.693] | 0.30 [0.23, 0.37] | 28 [24, 35] |

Rules:

- refractory (main): 120-min refractory after every kept detection, applied before scoring. Label-free.
- tp_lockout (comparison only): 120-min lockout after each TP, applied at scoring (Hochsmann 2026). Uses meal labels.
- Matching rules: ours = -30 to +120 min; review = 0 to +120 min (Hochsmann 2026).

## By group

#### Sensitivity (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 67.9 [58.9, 75.8] | 68.5 [57.7, 77.9] | 67.3 [59.2, 75.0] | 1.2 |
| tp_lockout, ours (comparison only) | 67.9 [58.9, 75.8] | 68.5 [57.7, 77.9] | 67.3 [59.2, 75.0] | 1.2 |
| tp_lockout, review (comparison only) | 56.5 [47.0, 66.1] | 63.0 [52.0, 73.5] | 64.5 [56.5, 72.3] | 8.0 |

#### Precision (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 87.5 [80.0, 93.8] | 92.0 [87.4, 96.2] | 88.6 [80.0, 95.0] | 4.5 |
| tp_lockout, ours (comparison only) | 87.5 [80.0, 93.8] | 92.0 [87.4, 96.2] | 88.6 [80.0, 95.0] | 4.5 |
| tp_lockout, review (comparison only) | 72.8 [63.7, 81.8] | 84.8 [77.9, 91.0] | 85.0 [77.0, 91.4] | 12.2 |

#### FP/day by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (per day).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 0.19 [0.10, 0.30] | 0.12 [0.06, 0.18] | 0.17 [0.07, 0.31] | 0.08 |
| tp_lockout, ours (comparison only) | 0.19 [0.10, 0.30] | 0.12 [0.06, 0.18] | 0.17 [0.07, 0.31] | 0.08 |
| tp_lockout, review (comparison only) | 0.42 [0.29, 0.54] | 0.22 [0.13, 0.32] | 0.23 [0.13, 0.35] | 0.20 |

## By meal

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. FP cannot be assigned to a meal, so only Sens and delay.

| Rule | Sens % breakfast | Delay median breakfast | Sens % lunch | Delay median lunch |
|---|---|---|---|---|
| refractory, ours (main) | 80.2 [72.0, 87.6] | 15 [9, 21] | 55.7 [49.4, 62.1] | 40 [34, 46] |
| tp_lockout, ours (comparison only) | 80.2 [72.0, 87.6] | 15 [9, 21] | 55.7 [49.4, 62.1] | 40 [34, 46] |
| tp_lockout, review (comparison only) | 69.2 [61.0, 77.0] | 19 [13, 24] | 53.3 [46.9, 59.9] | 41 [38, 47] |

## Recovery agreement

Segmentation: excursion (frozen definition, common/docs/deviations.md section X). Detector anchor = detection time; reference anchor = logged meal start.

#### ICC(A,1) by feature

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs with complete data; recovery time leaves out pairs with no_rise at either anchor.

| Rule | n pairs | n (recovery time) | Recovery time | Peak height | iAUC | Peak time |
|---|---|---|---|---|---|---|
| refractory, ours (main) | 448 | 447 | 0.67 | 0.92 | 0.94 | 0.37 |
| tp_lockout, ours (comparison only) | 448 | 447 | 0.67 | 0.92 | 0.94 | 0.37 |
| tp_lockout, review (comparison only) | 404 | 403 | 0.65 | 0.91 | 0.93 | 0.38 |

#### Recovery time by stratum, refractory (main)

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs used. Bias = detector minus reference (min).

| Stratum | n | ICC | Bias (min) | 95 % LoA (min) |
|---|---|---|---|---|
| overall | 447 | 0.67 | 15 | -38 to 69 |
| healthy | 160 | 0.77 | 10 | -37 to 57 |
| prediabetes | 139 | 0.68 | 17 | -38 to 72 |
| T2D | 148 | 0.53 | 19 | -39 to 77 |
| breakfast | 263 | 0.84 | 7 | -26 to 40 |
| lunch | 184 | 0.51 | 27 | -40 to 94 |

## Locked parameters (all_participants)

Route B, tuned once on all 42 participants. Candidate lock for AI-READI. No held-out score.

| Rule | Minimum height | Forced grid edges |
|---|---|---|
| refractory, ours (main) | 10 | none |
| tp_lockout, ours (comparison only) | 10 | none |
| tp_lockout, review (comparison only) | 10 | none |

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
