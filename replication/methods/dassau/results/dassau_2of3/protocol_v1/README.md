# Dassau 2-of-3: standard protocol (protocol_v1)

## Summary

- Dassau 2-of-3 on CGMacros (Dexcom, 42 participants). Standard protocol (protocol_v1), run on 2026-10-05.
- Main adjacent rule: refractory. Route B only. Matching window -30 to +120 min around the logged meal start. Why refractory: common/docs/deviations.md Z1.
- Main result, Route B: Sens 74.4 [69.5, 78.9] %, Prec 72.4 [68.3, 76.5] %, F2 0.740 [0.700, 0.778], FP/day 0.56 [0.46, 0.68], delay median 20 [18, 23] min.
- Recovery-time ICC(A,1), main rule: 0.70 (n = 479 TP pairs; excursion segmentation).
- tp_lockout (comparison only, uses meal labels): Sens 83.8 [79.5, 87.4] %, Prec 68.0 [62.9, 73.3] %, FP/day 0.78 [0.60, 0.99].
- Locked all_participants set, main rule: Threshold_ROC 1, Threshold_Acceleration 0.2. Forced grid edges: Threshold_ROC, Threshold_Acceleration.

## Method, sampling and parameters

- Source: Dassau E, Bequette BW, Buckingham BA, Doyle FJ III. Detection of a meal using continuous glucose monitoring: implications for an artificial beta-cell. Diabetes Care 2008;31(2):295-300. https://doi.org/10.2337/dc07-1293 (not available to us; abstract only).
- Implementation: As specified in the Hochsmann 2026 review (Supplementary Methods, Supplementary Table 1 Eqs. 1, 2, 4, 5). The review equations are the only spec.
- Three indicators at each 1-min sample: BD (3-point backward-difference ROC of raw glucose > Threshold_ROC), BDK (the same on Kalman-filtered glucose) and ACC (Kalman acceleration > Threshold_Acceleration).
- A meal flag at sample i needs at least two of the three indicators at every sample i, ..., i+4 (Eq. 5).
- A detection is the first sample of each run of flags (rising edge), at time t(i).
- The Kalman filter is a constant-acceleration model with default noise settings (deviations D6).
- Sampling: 1-min CGM input (QC'd 1-min series, plan 2.2; Dexcom readings linearly interpolated to 1 min).
- Fixed settings (not tuned): kalman_meas_sd_mg_dl = 3, kalman_jerk_psd = 0.0002, kalman_p0_rate_sd = 1, kalman_p0_acc_sd = 0.1, kalman_warmup_min = 10, window_samples = 5, sampling_min = 1.
- Tuned parameters: Threshold_ROC (mg/dL/min), Threshold_Acceleration (mg/dL/min^2).
- Tuning: F2 (beta = 2). Ties: higher F2, then lower FP/day, then shorter mean delay, then grid order.
- Route B: 5 participant folds stratified by group. Each fold is tuned on the other 4 and scored on its held-out participants. An all_participants set is also tuned once on everyone.

## Grid

Source: Hochsmann 2026 Supplementary Table 1, Equations 1, 2 and 4 (Threshold_ROC and Threshold_Acceleration; the only thresholds Eq. 5 uses, see deviations D2). 147 grid points. Edge hits count the 6 Route B sets (5 folds and all_participants) on the lower or upper grid bound.

| Parameter | Values | n | Edge hits, refractory (main) | Edge hits, tp_lockout (comparison only) |
|---|---|---|---|---|
| Threshold_ROC (mg/dL/min) | 1 to 3, step 0.1 | 21 | low 5/6, high 0/6 | low 6/6, high 0/6 |
| Threshold_Acceleration (mg/dL/min^2) | 0.2 to 0.8, step 0.1 | 7 | low 4/6, high 0/6 | low 1/6, high 0/6 |

A parameter on a grid bound may mean the best value lies outside the grid. Forced edges (shared by every tied grid point) are listed with the locked parameters.

## Detection

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. 95 % participant-bootstrap CI in brackets.

| Rule | Sens % | Prec % | F2 | FP/day | Delay median (min) |
|---|---|---|---|---|---|
| refractory, ours (main) | 74.4 [69.5, 78.9] | 72.4 [68.3, 76.5] | 0.740 [0.700, 0.778] | 0.56 [0.46, 0.68] | 20 [18, 23] |
| tp_lockout, ours (comparison only) | 83.8 [79.5, 87.4] | 68.0 [62.9, 73.3] | 0.801 [0.769, 0.830] | 0.78 [0.60, 0.99] | 19 [16, 21] |
| tp_lockout, review (comparison only) | 81.4 [77.1, 85.2] | 64.2 [58.8, 69.7] | 0.772 [0.739, 0.804] | 0.90 [0.70, 1.14] | 21 [18, 23] |

Rules:

- refractory (main): 120-min refractory after every kept detection, applied before scoring. Label-free.
- tp_lockout (comparison only): 120-min lockout after each TP, applied at scoring (Hochsmann 2026). Uses meal labels.
- Matching rules: ours = -30 to +120 min; review = 0 to +120 min (Hochsmann 2026).

## By group

#### Sensitivity (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 71.7 [63.7, 80.4] | 74.4 [64.6, 83.0] | 77.3 [71.6, 82.3] | 5.5 |
| tp_lockout, ours (comparison only) | 82.3 [74.9, 89.4] | 81.8 [71.8, 89.4] | 87.3 [84.1, 90.2] | 5.5 |
| tp_lockout, review (comparison only) | 79.8 [73.3, 86.2] | 80.3 [70.2, 88.7] | 84.1 [80.8, 87.8] | 4.3 |

#### Precision (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 70.8 [62.3, 78.5] | 78.2 [73.3, 83.9] | 69.4 [63.1, 76.5] | 8.9 |
| tp_lockout, ours (comparison only) | 64.6 [54.4, 75.8] | 74.4 [68.6, 81.9] | 66.7 [59.0, 74.7] | 9.9 |
| tp_lockout, review (comparison only) | 61.0 [50.9, 72.9] | 71.2 [64.4, 79.2] | 62.1 [54.0, 70.5] | 10.2 |

#### FP/day by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (per day).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 0.59 [0.39, 0.84] | 0.41 [0.28, 0.53] | 0.68 [0.48, 0.90] | 0.27 |
| tp_lockout, ours (comparison only) | 0.90 [0.51, 1.40] | 0.55 [0.35, 0.76] | 0.87 [0.58, 1.22] | 0.35 |
| tp_lockout, review (comparison only) | 1.02 [0.58, 1.55] | 0.64 [0.40, 0.87] | 1.03 [0.71, 1.41] | 0.39 |

## By meal

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. FP cannot be assigned to a meal, so only Sens and delay.

| Rule | Sens % breakfast | Delay median breakfast | Sens % lunch | Delay median lunch |
|---|---|---|---|---|
| refractory, ours (main) | 77.4 [69.8, 84.6] | 15 [14, 17] | 71.4 [65.9, 77.0] | 26 [24, 30] |
| tp_lockout, ours (comparison only) | 89.6 [83.3, 95.1] | 15 [13, 16] | 78.0 [72.4, 82.9] | 25 [22, 28] |
| tp_lockout, review (comparison only) | 89.0 [82.8, 94.5] | 15 [14, 17] | 73.8 [68.1, 79.2] | 27 [25, 30] |

## Recovery agreement

Segmentation: excursion (frozen definition, common/docs/deviations.md section X). Detector anchor = detection time; reference anchor = logged meal start.

#### ICC(A,1) by feature

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs with complete data; recovery time leaves out pairs with no_rise at either anchor.

| Rule | n pairs | n (recovery time) | Recovery time | Peak height | iAUC | Peak time |
|---|---|---|---|---|---|---|
| refractory, ours (main) | 491 | 479 | 0.70 | 0.88 | 0.91 | 0.55 |
| tp_lockout, ours (comparison only) | 553 | 541 | 0.73 | 0.89 | 0.92 | 0.59 |
| tp_lockout, review (comparison only) | 537 | 526 | 0.74 | 0.89 | 0.92 | 0.60 |

#### Recovery time by stratum, refractory (main)

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs used. Bias = detector minus reference (min).

| Stratum | n | ICC | Bias (min) | 95 % LoA (min) |
|---|---|---|---|---|
| overall | 479 | 0.70 | 10 | -44 to 64 |
| healthy | 166 | 0.78 | 6 | -41 to 53 |
| prediabetes | 148 | 0.72 | 12 | -43 to 66 |
| T2D | 165 | 0.58 | 13 | -46 to 72 |
| breakfast | 253 | 0.82 | 2 | -36 to 40 |
| lunch | 226 | 0.62 | 19 | -44 to 82 |

## Locked parameters (all_participants)

Route B, tuned once on all 42 participants. Candidate lock for AI-READI. No held-out score.

| Rule | Threshold_ROC | Threshold_Acceleration | Forced grid edges |
|---|---|---|---|
| refractory, ours (main) | 1 | 0.2 | Threshold_ROC, Threshold_Acceleration |
| tp_lockout, ours (comparison only) | 1 | 0.4 | Threshold_ROC |
| tp_lockout, review (comparison only) | 1 | 0.4 | Threshold_ROC |

Fold sets: `<rule>/params/chosen_params_routeB_<matching rule>.json`.

## Comparison with Hochsmann 2026 Table 2 (not like-for-like)

Hochsmann 2026 cohort: 16 healthy young adults, Libre 2 (1-min), 3 meals/day, afternoon detections suppressed, per-participant tuning. Ours: CGMacros, Route B, test data. Delay is the mean, as in Table 2.

| Data | Rule | Sens % | FP/day | Delay mean (min) |
|---|---|---|---|---|
| Hochsmann 2026 Table 2 | tp_lockout, review | 72.2 | 0.60 | 37.6 |
| CGMacros, Route B | tp_lockout, review (comparison only) | 81.4 [77.1, 85.2] | 0.90 [0.70, 1.14] | 29.2 [24.7, 34.3] |
| CGMacros, Route B | tp_lockout, ours (comparison only) | 83.8 [79.5, 87.4] | 0.78 [0.60, 0.99] | 24.0 [20.0, 28.7] |
| CGMacros, Route B | refractory, ours (main) | 74.4 [69.5, 78.9] | 0.56 [0.46, 0.68] | 27.7 [23.4, 32.6] |

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
python common/run_protocol.py dassau_2of3
python common/run_protocol.py dassau_2of3 --docs-only
```

The first runs the full protocol and also rewrites `results/method_comparison.md`. The second rebuilds this README and the comparison from the saved outputs.
