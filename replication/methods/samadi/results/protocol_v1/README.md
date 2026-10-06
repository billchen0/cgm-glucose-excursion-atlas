# Samadi IGT: standard protocol (protocol_v1)

## Summary

- Samadi IGT on CGMacros (Dexcom, 42 participants). Standard protocol (protocol_v1), run on 2026-10-05.
- Main adjacent rule: refractory. Route B only. Matching window -30 to +120 min around the logged meal start. Why refractory: common/docs/deviations.md Z1.
- Main result, Route B: Sens 87.4 [84.0, 90.8] %, Prec 55.9 [53.3, 58.7] %, F2 0.786 [0.756, 0.815], FP/day 1.37 [1.24, 1.49], delay median 25 [22, 28] min.
- Recovery-time ICC(A,1), main rule: 0.66 (n = 537 TP pairs; excursion segmentation).
- tp_lockout (comparison only, uses meal labels): Sens 90.5 [87.2, 93.4] %, Prec 52.1 [48.0, 56.6] %, FP/day 1.65 [1.38, 1.95].
- Locked all_participants set, main rule: gamma1 1, Threshold_act 2.2. Forced grid edges: gamma1.

## Method, sampling and parameters

- Source: Samadi S, Rashid M, Turksoy K, et al. Automatic detection and estimation of unannounced meals for multivariable artificial pancreas system. Diabetes Technol Ther 2018;20(3):235-246. https://doi.org/10.1089/dia.2017.0364
- Implementation: Simplified rule as in the Hochsmann 2026 review (Supplementary Methods, Supplementary Table 1 Eqs. 14-15). Shapes and weights from Samadi 2018 Fig. 2. Membership functions are defaults (Samadi 2017, where they are defined, is not available).
- At each 5-min sample, a quadratic is fitted to the four most recent glucose points. Its first and second derivatives at the newest point are d1G and d2G.
- Each derivative gets fuzzy memberships for negative, zero and positive. The d1G sets have centres -gamma1, 0, +gamma1; the d2G sets use gamma1 / 15 min.
- Seven shapes (B, F, C, G, A, E, D; Samadi 2018 Fig. 2) get the product of the two sign memberships. IGT is their weighted average with weights -3 to +3 (Eq. 14), so IGT lies in [-3, 3].
- A meal flag is raised when IGT > Threshold_act (Eq. 15). The original activation, pause and deactivation logic is omitted, as in the review.
- A detection is the first sample of each run of flags (rising edge).
- Sampling: 5-min CGM input (native Dexcom readings for 5 min; see common/docs/deviations.md E1).
- Fixed settings (not tuned): fit_points = 4, d2_scale_min = 15, sampling_min = 5.
- Tuned parameters: gamma1 (mg/dL/min), Threshold_act (IGT).
- Tuning: F2 (beta = 2). Ties: higher F2, then lower FP/day, then shorter mean delay, then grid order.
- Route B: 5 participant folds stratified by group. Each fold is tuned on the other 4 and scored on its held-out participants. An all_participants set is also tuned once on everyone.

## Grid

Source: Hochsmann 2026 Supplementary Methods (lines 132-133): gamma1 in {1.00, 1.50, ..., 4.00}, Threshold_act in {1.0, 1.1, ..., 3.0}. 147 grid points. Edge hits count the 6 Route B sets (5 folds and all_participants) on the lower or upper grid bound.

| Parameter | Values | n | Edge hits, refractory (main) | Edge hits, tp_lockout (comparison only) |
|---|---|---|---|---|
| gamma1 (mg/dL/min) | 1 to 4, step 0.5 | 7 | low 6/6, high 0/6 | low 0/6, high 0/6 |
| Threshold_act (IGT) | 1 to 3, step 0.1 | 21 | low 0/6, high 0/6 | low 0/6, high 0/6 |

A parameter on a grid bound may mean the best value lies outside the grid. Forced edges (shared by every tied grid point) are listed with the locked parameters.

## Detection

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. 95 % participant-bootstrap CI in brackets.

| Rule | Sens % | Prec % | F2 | FP/day | Delay median (min) |
|---|---|---|---|---|---|
| refractory, ours (main) | 87.4 [84.0, 90.8] | 55.9 [53.3, 58.7] | 0.786 [0.756, 0.815] | 1.37 [1.24, 1.49] | 25 [22, 28] |
| tp_lockout, ours (comparison only) | 90.5 [87.2, 93.4] | 52.1 [48.0, 56.6] | 0.788 [0.762, 0.817] | 1.65 [1.38, 1.95] | 19 [16, 21] |
| tp_lockout, review (comparison only) | 89.8 [86.6, 92.8] | 49.3 [45.3, 53.6] | 0.771 [0.747, 0.798] | 1.84 [1.54, 2.16] | 22 [20, 24] |

Rules:

- refractory (main): 120-min refractory after every kept detection, applied before scoring. Label-free.
- tp_lockout (comparison only): 120-min lockout after each TP, applied at scoring (Hochsmann 2026). Uses meal labels.
- Matching rules: ours = -30 to +120 min; review = 0 to +120 min (Hochsmann 2026).

## By group

#### Sensitivity (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 87.3 [83.0, 91.2] | 84.2 [75.6, 91.2] | 90.5 [85.5, 95.0] | 6.2 |
| tp_lockout, ours (comparison only) | 89.5 [83.0, 94.9] | 88.7 [81.8, 94.6] | 93.2 [90.1, 96.0] | 4.5 |
| tp_lockout, review (comparison only) | 89.0 [83.3, 94.0] | 88.7 [81.3, 94.7] | 91.8 [88.1, 95.1] | 3.1 |

#### Precision (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 52.3 [49.8, 54.9] | 57.2 [51.1, 62.7] | 59.1 [54.1, 64.8] | 6.8 |
| tp_lockout, ours (comparison only) | 49.4 [42.9, 56.7] | 54.9 [47.6, 63.5] | 52.7 [46.1, 59.7] | 5.5 |
| tp_lockout, review (comparison only) | 46.7 [40.7, 53.9] | 52.6 [45.8, 61.3] | 49.4 [43.2, 56.2] | 5.9 |

#### FP/day by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (per day).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 1.59 [1.44, 1.74] | 1.24 [1.06, 1.43] | 1.25 [1.01, 1.48] | 0.35 |
| tp_lockout, ours (comparison only) | 1.82 [1.34, 2.38] | 1.44 [1.02, 1.86] | 1.67 [1.24, 2.20] | 0.39 |
| tp_lockout, review (comparison only) | 2.03 [1.49, 2.63] | 1.57 [1.10, 2.04] | 1.88 [1.42, 2.42] | 0.45 |

## By meal

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. FP cannot be assigned to a meal, so only Sens and delay.

| Rule | Sens % breakfast | Delay median breakfast | Sens % lunch | Delay median lunch |
|---|---|---|---|---|
| refractory, ours (main) | 84.2 [77.5, 90.0] | 22 [18, 27] | 90.7 [87.2, 93.7] | 27 [24, 30] |
| tp_lockout, ours (comparison only) | 93.6 [88.6, 97.6] | 15 [14, 18] | 87.4 [82.9, 91.3] | 24 [22, 26] |
| tp_lockout, review (comparison only) | 93.9 [89.0, 97.9] | 18 [16, 19] | 85.8 [81.3, 89.8] | 28 [25, 30] |

## Recovery agreement

Segmentation: excursion (frozen definition, common/docs/deviations.md section X). Detector anchor = detection time; reference anchor = logged meal start.

#### ICC(A,1) by feature

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs with complete data; recovery time leaves out pairs with no_rise at either anchor.

| Rule | n pairs | n (recovery time) | Recovery time | Peak height | iAUC | Peak time |
|---|---|---|---|---|---|---|
| refractory, ours (main) | 577 | 537 | 0.66 | 0.83 | 0.82 | 0.49 |
| tp_lockout, ours (comparison only) | 597 | 576 | 0.78 | 0.92 | 0.93 | 0.57 |
| tp_lockout, review (comparison only) | 593 | 572 | 0.76 | 0.92 | 0.94 | 0.59 |

#### Recovery time by stratum, refractory (main)

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs used. Bias = detector minus reference (min).

| Stratum | n | ICC | Bias (min) | 95 % LoA (min) |
|---|---|---|---|---|
| overall | 537 | 0.66 | 5 | -54 to 63 |
| healthy | 195 | 0.68 | -0 | -56 to 56 |
| prediabetes | 161 | 0.70 | 4 | -55 to 62 |
| T2D | 181 | 0.59 | 10 | -50 to 70 |
| breakfast | 270 | 0.68 | 3 | -49 to 56 |
| lunch | 267 | 0.65 | 6 | -59 to 70 |

## Locked parameters (all_participants)

Route B, tuned once on all 42 participants. Candidate lock for AI-READI. No held-out score.

| Rule | gamma1 | Threshold_act | Forced grid edges |
|---|---|---|---|
| refractory, ours (main) | 1 | 2.2 | gamma1 |
| tp_lockout, ours (comparison only) | 1.5 | 2.3 | none |
| tp_lockout, review (comparison only) | 1.5 | 2.3 | none |

Fold sets: `<rule>/params/chosen_params_routeB_<matching rule>.json`.

Hochsmann 2026 Table 1 (tuned per participant, mean +/- SD; their cohort): gamma1 1 +/- 1, Threshold_act 1.33 +/- 0.49, f2 0.86 +/- 0.04.

## Comparison with Hochsmann 2026 Table 2 (not like-for-like)

Hochsmann 2026 cohort: 16 healthy young adults, Libre 2 (resampled to 5 min), 3 meals/day, afternoon detections suppressed, per-participant tuning. Ours: CGMacros, Route B, test data. Delay is the mean, as in Table 2.

| Data | Rule | Sens % | FP/day | Delay mean (min) |
|---|---|---|---|---|
| Hochsmann 2026 Table 2 | tp_lockout, review | 89.8 | 2.42 | 58.5 |
| CGMacros, Route B | tp_lockout, review (comparison only) | 89.8 [86.6, 92.8] | 1.84 [1.54, 2.16] | 29.5 [25.9, 33.7] |
| CGMacros, Route B | tp_lockout, ours (comparison only) | 90.5 [87.2, 93.4] | 1.65 [1.38, 1.95] | 20.1 [16.2, 24.1] |
| CGMacros, Route B | refractory, ours (main) | 87.4 [84.0, 90.8] | 1.37 [1.24, 1.49] | 35.7 [32.6, 39.0] |

The closest row is tp_lockout with the review matching rule. Differences remain: cohort, sensor, meals scored (breakfast and lunch here), scoring window (07:00 to lunch + 180 min here) and tuning (per participant in the review; one global set in Route B).

## Deviations

- Method: `methods/samadi/docs/deviations.md`.
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
python common/run_protocol.py samadi
python common/run_protocol.py samadi --docs-only
```

The first runs the full protocol and also rewrites `results/method_comparison.md`. The second rebuilds this README and the comparison from the saved outputs.
