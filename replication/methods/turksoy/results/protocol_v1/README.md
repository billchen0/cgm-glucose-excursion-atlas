# Turksoy UKF: standard protocol (protocol_v1)

## Summary

- Turksoy UKF on CGMacros (Dexcom, 42 participants). Standard protocol (protocol_v1), run on 2026-10-05.
- Main adjacent rule: refractory. Route B only. Matching window -30 to +120 min around the logged meal start. Why refractory: common/docs/deviations.md Z1.
- Main result, Route B: Sens 53.5 [49.4, 57.4] %, Prec 89.1 [84.3, 93.6] %, F2 0.581 [0.541, 0.620], FP/day 0.13 [0.07, 0.19], delay median 38 [35, 41] min.
- Recovery-time ICC(A,1), main rule: 0.70 (n = 353 TP pairs; excursion segmentation).
- tp_lockout (comparison only, uses meal labels): Sens 56.7 [52.1, 61.0] %, Prec 88.2 [83.0, 93.2] %, FP/day 0.15 [0.08, 0.23].
- Locked all_participants set, main rule: Threshold_Ra 1.5. Forced grid edges: Threshold_Ra.

## Method, sampling and parameters

- Source: Turksoy K, Samadi S, Feng J, Littlejohn E, Quinn L, Cinar A. Meal detection in patients with type 1 diabetes: a new module for the multivariable adaptive artificial pancreas control system. IEEE J Biomed Health Inform 2016;20(1):47-54. https://doi.org/10.1109/JBHI.2015.2446413
- Implementation: Hochsmann 2026 review rule (Supplementary Table 1 Eq. 16), no post-detection threshold raising. Model and UKF settings from Turksoy 2016. CGM only: the model has no insulin input (Eq. 7 sets plasma insulin to zero).
- A modified Bergman minimal model with a two-compartment meal subsystem is run at 1-min sampling.
- An unscented Kalman filter estimates eight states: effective insulin, glucose, the current and previous rate of glucose appearance R_a, and the parameters p1, p2, p4 and tau.
- The model has no insulin input and no meal input. Meals enter through the process noise on R_a.
- A meal flag is raised when the estimated R_a > Threshold_Ra and CGM > 100 mg/dL (Eq. 16). A detection is the first sample of each run of flags (rising edge).
- Turksoy's noise settings and initial state are used. The parameter bounds for sigma-point trimming are defaults (deviations T7).
- Sampling: 1-min CGM input (QC'd 1-min series, plan 2.2; Dexcom readings linearly interpolated to 1 min).
- Fixed settings (not tuned): sampling_min = 1, glucose_min = 100, gb_window_min = 30, gb_default = 100, ukf_alpha = 1, ukf_beta = 2, ukf_kappa = 0, ukf_x0 = (0.0, 0.0, 0.0, 0.0, 0.068, 0.037, 1.3, 20.0), ukf_qp = (1e-06, 1e-06, 0.001, 0.001, 0.01, 0.1, 0.01, 0.1), ukf_p0 = 1, ukf_qm = 100, ukf_lo = (0.0, 20.0, 0.0, 0.0, 0.0068, 0.0037, 0.13, 2.0), ukf_hi = (1.0, 600.0, 20.0, 20.0, 0.68, 0.37, 13.0, 200.0), ukf_eig_floor = 1e-09, ukf_warmup_min = 120.
- Tuned parameters: Threshold_Ra (mg/dL/min).
- Tuning: F2 (beta = 2). Ties: higher F2, then lower FP/day, then shorter mean delay, then grid order.
- Route B: 5 participant folds stratified by group. Each fold is tuned on the other 4 and scored on its held-out participants. An all_participants set is also tuned once on everyone.

## Grid

Source: Hochsmann 2026 Supplementary Methods line 144: Threshold_Ra over 1.5 to 2.5 mg/dL/min; step 0.1 is a default (not stated). 11 grid points. Edge hits count the 6 Route B sets (5 folds and all_participants) on the lower or upper grid bound.

| Parameter | Values | n | Edge hits, refractory (main) | Edge hits, tp_lockout (comparison only) |
|---|---|---|---|---|
| Threshold_Ra (mg/dL/min) | 1.5 to 2.5, step 0.1 | 11 | low 6/6, high 0/6 | low 6/6, high 0/6 |

A parameter on a grid bound may mean the best value lies outside the grid. Forced edges (shared by every tied grid point) are listed with the locked parameters.

## Detection

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. 95 % participant-bootstrap CI in brackets.

| Rule | Sens % | Prec % | F2 | FP/day | Delay median (min) |
|---|---|---|---|---|---|
| refractory, ours (main) | 53.5 [49.4, 57.4] | 89.1 [84.3, 93.6] | 0.581 [0.541, 0.620] | 0.13 [0.07, 0.19] | 38 [35, 41] |
| tp_lockout, ours (comparison only) | 56.7 [52.1, 61.0] | 88.2 [83.0, 93.2] | 0.610 [0.567, 0.651] | 0.15 [0.08, 0.23] | 37 [34, 40] |
| tp_lockout, review (comparison only) | 55.1 [50.6, 59.6] | 85.2 [79.7, 90.8] | 0.593 [0.549, 0.637] | 0.19 [0.11, 0.27] | 37 [34, 40] |

Rules:

- refractory (main): 120-min refractory after every kept detection, applied before scoring. Label-free.
- tp_lockout (comparison only): 120-min lockout after each TP, applied at scoring (Hochsmann 2026). Uses meal labels.
- Matching rules: ours = -30 to +120 min; review = 0 to +120 min (Hochsmann 2026).

## By group

#### Sensitivity (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 48.5 [43.3, 53.4] | 57.1 [50.5, 64.0] | 55.5 [46.9, 63.4] | 8.6 |
| tp_lockout, ours (comparison only) | 50.2 [44.3, 56.1] | 59.6 [52.2, 66.7] | 60.9 [51.3, 69.1] | 10.7 |
| tp_lockout, review (comparison only) | 49.4 [43.5, 55.4] | 58.6 [50.5, 66.2] | 58.2 [48.6, 66.5] | 9.3 |

#### Precision (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 87.1 [77.9, 96.2] | 89.2 [81.2, 96.7] | 91.0 [83.9, 97.0] | 3.9 |
| tp_lockout, ours (comparison only) | 86.2 [76.4, 95.9] | 87.7 [78.2, 96.7] | 90.5 [82.7, 96.9] | 4.3 |
| tp_lockout, review (comparison only) | 83.0 [73.0, 92.8] | 86.2 [76.4, 95.9] | 86.5 [77.6, 94.9] | 3.5 |

#### FP/day by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (per day).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 0.14 [0.04, 0.27] | 0.14 [0.04, 0.25] | 0.11 [0.04, 0.19] | 0.03 |
| tp_lockout, ours (comparison only) | 0.16 [0.04, 0.31] | 0.17 [0.04, 0.34] | 0.13 [0.04, 0.23] | 0.04 |
| tp_lockout, review (comparison only) | 0.20 [0.08, 0.36] | 0.18 [0.05, 0.36] | 0.18 [0.07, 0.31] | 0.02 |

## By meal

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. FP cannot be assigned to a meal, so only Sens and delay.

| Rule | Sens % breakfast | Delay median breakfast | Sens % lunch | Delay median lunch |
|---|---|---|---|---|
| refractory, ours (main) | 62.5 [54.9, 70.0] | 33 [30, 36] | 44.6 [38.5, 49.9] | 43 [41, 48] |
| tp_lockout, ours (comparison only) | 68.6 [60.1, 76.1] | 32 [29, 35] | 44.9 [38.9, 50.1] | 43 [41, 48] |
| tp_lockout, review (comparison only) | 67.4 [59.1, 74.9] | 32 [30, 36] | 43.1 [37.5, 48.2] | 44 [42, 48] |

## Recovery agreement

Segmentation: excursion (frozen definition, common/docs/deviations.md section X). Detector anchor = detection time; reference anchor = logged meal start.

#### ICC(A,1) by feature

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs with complete data; recovery time leaves out pairs with no_rise at either anchor.

| Rule | n pairs | n (recovery time) | Recovery time | Peak height | iAUC | Peak time |
|---|---|---|---|---|---|---|
| refractory, ours (main) | 353 | 353 | 0.70 | 0.88 | 0.90 | 0.42 |
| tp_lockout, ours (comparison only) | 374 | 374 | 0.71 | 0.92 | 0.94 | 0.45 |
| tp_lockout, review (comparison only) | 364 | 364 | 0.70 | 0.92 | 0.94 | 0.44 |

#### Recovery time by stratum, refractory (main)

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs used. Bias = detector minus reference (min).

| Stratum | n | ICC | Bias (min) | 95 % LoA (min) |
|---|---|---|---|---|
| overall | 353 | 0.70 | 11 | -44 to 66 |
| healthy | 115 | 0.75 | 5 | -48 to 58 |
| prediabetes | 116 | 0.71 | 12 | -44 to 68 |
| T2D | 122 | 0.62 | 16 | -40 to 71 |
| breakfast | 205 | 0.86 | 3 | -31 to 38 |
| lunch | 148 | 0.55 | 22 | -49 to 92 |

## Locked parameters (all_participants)

Route B, tuned once on all 42 participants. Candidate lock for AI-READI. No held-out score.

| Rule | Threshold_Ra | Forced grid edges |
|---|---|---|
| refractory, ours (main) | 1.5 | Threshold_Ra |
| tp_lockout, ours (comparison only) | 1.5 | Threshold_Ra |
| tp_lockout, review (comparison only) | 1.5 | Threshold_Ra |

Fold sets: `<rule>/params/chosen_params_routeB_<matching rule>.json`.

Hochsmann 2026 Table 1 (tuned per participant, mean +/- SD; their cohort): Threshold_Ra 1.56 +/- 0.09, f2 0.84 +/- 0.12.

## Comparison with Hochsmann 2026 Table 2 (not like-for-like)

Hochsmann 2026 cohort: 16 healthy young adults, Libre 2 (1-min), 3 meals/day, afternoon detections suppressed, per-participant tuning. Ours: CGMacros, Route B, test data. Delay is the mean, as in Table 2.

| Data | Rule | Sens % | FP/day | Delay mean (min) |
|---|---|---|---|---|
| Hochsmann 2026 Table 2 | tp_lockout, review | 76.9 | 0.22 | 40.7 |
| CGMacros, Route B | tp_lockout, review (comparison only) | 55.1 [50.6, 59.6] | 0.19 [0.11, 0.27] | 42.1 [37.8, 47.2] |
| CGMacros, Route B | tp_lockout, ours (comparison only) | 56.7 [52.1, 61.0] | 0.15 [0.08, 0.23] | 40.0 [35.7, 45.2] |
| CGMacros, Route B | refractory, ours (main) | 53.5 [49.4, 57.4] | 0.13 [0.07, 0.19] | 41.6 [37.2, 46.7] |

The closest row is tp_lockout with the review matching rule. Differences remain: cohort, sensor, meals scored (breakfast and lunch here), scoring window (07:00 to lunch + 180 min here) and tuning (per participant in the review; one global set in Route B).

Original paper (Hochsmann 2026 Supplementary Table 2, metrics from Kolle et al.; T1D, TP window -30 to 120 min, not like-for-like): sensitivity pct 97 / 64, fp per day 1.28, delay min 32.7.

## Deviations

- Method: `methods/turksoy/docs/deviations.md`.
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
python common/run_protocol.py turksoy
python common/run_protocol.py turksoy --docs-only
```

The first runs the full protocol and also rewrites `results/method_comparison.md`. The second rebuilds this README and the comparison from the saved outputs.
