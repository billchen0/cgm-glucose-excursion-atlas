# Dassau 3-of-4: standard protocol (protocol_v1)

## Summary

- Dassau 3-of-4 on CGMacros (Dexcom, 42 participants). Standard protocol (protocol_v1), run on 2026-10-05.
- Main adjacent rule: refractory. Route B only. Matching window -30 to +120 min around the logged meal start. Why refractory: common/docs/deviations.md Z1.
- Main result, Route B: Sens 71.7 [67.5, 75.5] %, Prec 82.7 [78.1, 87.3] %, F2 0.736 [0.701, 0.770], FP/day 0.30 [0.21, 0.40], delay median 24 [21, 27] min.
- Recovery-time ICC(A,1), main rule: 0.70 (n = 466 TP pairs; excursion segmentation).
- tp_lockout (comparison only, uses meal labels): Sens 76.2 [72.0, 79.9] %, Prec 78.7 [72.7, 84.7] %, FP/day 0.41 [0.28, 0.57].
- Locked all_participants set, main rule: Threshold_Glucose 100, Threshold_maxROC 4, Threshold_ROC 1, Threshold_Acceleration 0.3. Forced grid edges: Threshold_Glucose, Threshold_ROC.

## Method, sampling and parameters

- Source: Dassau E, Bequette BW, Buckingham BA, Doyle FJ III. Detection of a meal using continuous glucose monitoring: implications for an artificial beta-cell. Diabetes Care 2008;31(2):295-300. https://doi.org/10.2337/dc07-1293 (not available to us; abstract only).
- Implementation: As specified in the Hochsmann 2026 review (Supplementary Methods, Supplementary Table 1 Eqs. 1-4, 6). The review equations are the only spec.
- Four indicators at each 1-min sample: BD and BDK (3-point backward-difference ROC of raw and Kalman-filtered glucose > Threshold_ROC), KF (Kalman ROC between Threshold_ROC and Threshold_maxROC, and Kalman glucose > Threshold_Glucose) and ACC (Kalman acceleration > Threshold_Acceleration).
- A meal flag at sample i needs at least three of the four indicators at every sample i, ..., i+4 (Eq. 6).
- A detection is the first sample of each run of flags (rising edge), at time t(i).
- The Kalman filter is a constant-acceleration model with default noise settings (deviations D6).
- Sampling: 1-min CGM input (QC'd 1-min series, plan 2.2; Dexcom readings linearly interpolated to 1 min).
- Fixed settings (not tuned): kalman_meas_sd_mg_dl = 3, kalman_jerk_psd = 0.0002, kalman_p0_rate_sd = 1, kalman_p0_acc_sd = 0.1, kalman_warmup_min = 10, window_samples = 5, sampling_min = 1.
- Tuned parameters: Threshold_Glucose (mg/dL), Threshold_maxROC (mg/dL/min), Threshold_ROC (mg/dL/min), Threshold_Acceleration (mg/dL/min^2).
- Tuning: F2 (beta = 2). Ties: higher F2, then lower FP/day, then shorter mean delay, then grid order.
- Route B: 5 participant folds stratified by group. Each fold is tuned on the other 4 and scored on its held-out participants. An all_participants set is also tuned once on everyone.

## Grid

Source: Hochsmann 2026 Supplementary Table 1, Equations 1-4. 6,468 grid points. Edge hits count the 6 Route B sets (5 folds and all_participants) on the lower or upper grid bound.

| Parameter | Values | n | Edge hits, refractory (main) | Edge hits, tp_lockout (comparison only) |
|---|---|---|---|---|
| Threshold_Glucose (mg/dL) | 100 to 200, step 10 | 11 | low 6/6, high 0/6 | low 6/6, high 0/6 |
| Threshold_maxROC (mg/dL/min) | 2 to 5, step 1 | 4 | low 0/6, high 1/6 | low 0/6, high 5/6 |
| Threshold_ROC (mg/dL/min) | 1 to 3, step 0.1 | 21 | low 6/6, high 0/6 | low 6/6, high 0/6 |
| Threshold_Acceleration (mg/dL/min^2) | 0.2 to 0.8, step 0.1 | 7 | low 0/6, high 0/6 | low 6/6, high 0/6 |

A parameter on a grid bound may mean the best value lies outside the grid. Forced edges (shared by every tied grid point) are listed with the locked parameters.

## Detection

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. 95 % participant-bootstrap CI in brackets.

| Rule | Sens % | Prec % | F2 | FP/day | Delay median (min) |
|---|---|---|---|---|---|
| refractory, ours (main) | 71.7 [67.5, 75.5] | 82.7 [78.1, 87.3] | 0.736 [0.701, 0.770] | 0.30 [0.21, 0.40] | 24 [21, 27] |
| tp_lockout, ours (comparison only) | 76.2 [72.0, 79.9] | 78.7 [72.7, 84.7] | 0.767 [0.732, 0.800] | 0.41 [0.28, 0.57] | 23 [20, 25] |
| tp_lockout, review (comparison only) | 73.9 [69.8, 77.8] | 75.9 [69.3, 82.3] | 0.743 [0.706, 0.778] | 0.47 [0.32, 0.64] | 24 [21, 27] |

Rules:

- refractory (main): 120-min refractory after every kept detection, applied before scoring. Label-free.
- tp_lockout (comparison only): 120-min lockout after each TP, applied at scoring (Hochsmann 2026). Uses meal labels.
- Matching rules: ours = -30 to +120 min; review = 0 to +120 min (Hochsmann 2026).

## By group

#### Sensitivity (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 67.5 [60.4, 74.5] | 71.4 [62.3, 78.8] | 76.4 [71.8, 80.9] | 8.8 |
| tp_lockout, ours (comparison only) | 73.8 [67.0, 80.7] | 74.4 [65.0, 81.8] | 80.5 [76.8, 84.7] | 6.6 |
| tp_lockout, review (comparison only) | 70.9 [63.6, 77.9] | 72.4 [63.4, 79.9] | 78.6 [74.6, 82.9] | 7.8 |

#### Precision (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 82.5 [72.1, 91.5] | 87.9 [83.4, 92.5] | 78.9 [72.0, 85.7] | 9.0 |
| tp_lockout, ours (comparison only) | 77.1 [64.8, 88.3] | 86.8 [82.0, 91.8] | 74.4 [66.1, 82.5] | 12.4 |
| tp_lockout, review (comparison only) | 73.7 [60.1, 87.2] | 83.0 [78.2, 88.4] | 72.7 [64.3, 81.4] | 10.4 |

#### FP/day by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (per day).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 0.29 [0.13, 0.49] | 0.19 [0.12, 0.27] | 0.41 [0.26, 0.58] | 0.21 |
| tp_lockout, ours (comparison only) | 0.44 [0.19, 0.80] | 0.22 [0.13, 0.33] | 0.55 [0.35, 0.80] | 0.33 |
| tp_lockout, review (comparison only) | 0.50 [0.21, 0.93] | 0.29 [0.18, 0.41] | 0.59 [0.36, 0.85] | 0.30 |

## By meal

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. FP cannot be assigned to a meal, so only Sens and delay.

| Rule | Sens % breakfast | Delay median breakfast | Sens % lunch | Delay median lunch |
|---|---|---|---|---|
| refractory, ours (main) | 79.0 [71.3, 85.8] | 19 [17, 21] | 64.5 [59.3, 69.4] | 31 [28, 33] |
| tp_lockout, ours (comparison only) | 84.5 [77.1, 90.9] | 18 [16, 20] | 68.1 [62.8, 72.9] | 29 [27, 31] |
| tp_lockout, review (comparison only) | 83.5 [76.2, 90.2] | 18 [17, 21] | 64.5 [59.3, 69.5] | 31 [29, 33] |

## Recovery agreement

Segmentation: excursion (frozen definition, common/docs/deviations.md section X). Detector anchor = detection time; reference anchor = logged meal start.

#### ICC(A,1) by feature

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs with complete data; recovery time leaves out pairs with no_rise at either anchor.

| Rule | n pairs | n (recovery time) | Recovery time | Peak height | iAUC | Peak time |
|---|---|---|---|---|---|---|
| refractory, ours (main) | 473 | 466 | 0.70 | 0.89 | 0.92 | 0.55 |
| tp_lockout, ours (comparison only) | 503 | 496 | 0.75 | 0.91 | 0.94 | 0.58 |
| tp_lockout, review (comparison only) | 488 | 482 | 0.74 | 0.89 | 0.93 | 0.58 |

#### Recovery time by stratum, refractory (main)

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs used. Bias = detector minus reference (min).

| Stratum | n | ICC | Bias (min) | 95 % LoA (min) |
|---|---|---|---|---|
| overall | 466 | 0.70 | 11 | -42 to 64 |
| healthy | 159 | 0.76 | 6 | -43 to 56 |
| prediabetes | 143 | 0.76 | 13 | -35 to 61 |
| T2D | 164 | 0.55 | 13 | -46 to 72 |
| breakfast | 259 | 0.86 | 3 | -28 to 35 |
| lunch | 207 | 0.59 | 20 | -47 to 87 |

## Locked parameters (all_participants)

Route B, tuned once on all 42 participants. Candidate lock for AI-READI. No held-out score.

| Rule | Threshold_Glucose | Threshold_maxROC | Threshold_ROC | Threshold_Acceleration | Forced grid edges |
|---|---|---|---|---|---|
| refractory, ours (main) | 100 | 4 | 1 | 0.3 | Threshold_Glucose, Threshold_ROC |
| tp_lockout, ours (comparison only) | 100 | 5 | 1 | 0.2 | Threshold_Glucose, Threshold_maxROC, Threshold_ROC, Threshold_Acceleration |
| tp_lockout, review (comparison only) | 100 | 5 | 1 | 0.2 | Threshold_Glucose, Threshold_maxROC, Threshold_ROC, Threshold_Acceleration |

Fold sets: `<rule>/params/chosen_params_routeB_<matching rule>.json`.

## Comparison with Hochsmann 2026 Table 2 (not like-for-like)

Hochsmann 2026 cohort: 16 healthy young adults, Libre 2 (1-min), 3 meals/day, afternoon detections suppressed, per-participant tuning. Ours: CGMacros, Route B, test data. Delay is the mean, as in Table 2.

| Data | Rule | Sens % | FP/day | Delay mean (min) |
|---|---|---|---|---|
| Hochsmann 2026 Table 2 | tp_lockout, review | 49.1 | 0.12 | 36.8 |
| CGMacros, Route B | tp_lockout, review (comparison only) | 73.9 [69.8, 77.8] | 0.47 [0.32, 0.64] | 31.6 [27.2, 37.0] |
| CGMacros, Route B | tp_lockout, ours (comparison only) | 76.2 [72.0, 79.9] | 0.41 [0.28, 0.57] | 27.9 [23.6, 33.3] |
| CGMacros, Route B | refractory, ours (main) | 71.7 [67.5, 75.5] | 0.30 [0.21, 0.40] | 30.8 [26.2, 36.4] |

The closest row is tp_lockout with the review matching rule. Differences remain: cohort, sensor, meals scored (breakfast and lunch here), scoring window (07:00 to lunch + 180 min here) and tuning (per participant in the review; one global set in Route B).

## Deviations

- Method: `methods/dassau/docs/deviations.md`.
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
python common/run_protocol.py dassau_3of4
python common/run_protocol.py dassau_3of4 --docs-only
```

The first runs the full protocol and also rewrites `results/method_comparison.md`. The second rebuilds this README and the comparison from the saved outputs.
