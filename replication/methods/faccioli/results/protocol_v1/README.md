# Faccioli STMD: standard protocol (protocol_v1)

## Summary

- Faccioli STMD on CGMacros (Dexcom, 42 participants). Standard protocol (protocol_v1), run on 2026-10-05.
- Main adjacent rule: refractory. Route B only. Matching window -30 to +120 min around the logged meal start. Why refractory: common/docs/deviations.md Z1.
- Main result, Route B: Sens 77.7 [73.6, 81.9] %, Prec 69.1 [64.8, 73.6] %, F2 0.758 [0.721, 0.798], FP/day 0.69 [0.57, 0.82], delay median 30 [28, 33] min.
- Recovery-time ICC(A,1), main rule: 0.71 (n = 496 TP pairs; excursion segmentation).
- tp_lockout (comparison only, uses meal labels): Sens 90.9 [88.0, 93.7] %, Prec 66.1 [61.7, 70.5] %, FP/day 0.92 [0.76, 1.11].
- Locked all_participants set, main rule: Th_Res 1, Th_Der 0.5, L 0.0325. Forced grid edges: Th_Res, Th_Der.

## Method, sampling and parameters

- Source: Faccioli S, Sala-Mira I, Diez JL, Facchinetti A, Sparacino G, Del Favero S, Bondia J. Super-twisting-based meal detector for type 1 diabetes management: improvement and assessment in a real-life scenario. Comput Methods Programs Biomed 2022;219:106736. https://doi.org/10.1016/j.cmpb.2022.106736
- Implementation: Hochsmann 2026 review rule (Supplementary Table 1 Eq. 7, 3-point median filter, gain per day). Observer, Kalman filter and gain rule from Faccioli 2022. CGM only: the observer has no insulin term.
- A causal 3-point median filter removes single-sample CGM spikes.
- A super-twisting observer (implicit discretisation) tracks glucose. Its residual Res rises when the glucose disturbance exceeds the bound L.
- The observer bound L is one global value, tuned on Route B with the two thresholds (deviations F5b). It was added after the first run: Faccioli's first-night gain rule, applied per day, gave Sens of about 20 % (results/protocol_v1_nightgain/).
- A Kalman filter (three-state, Faccioli's noise settings) gives the glucose derivative dG.
- A meal flag is raised when Res > Th_Res and dG > Th_Der (Eq. 7). A detection is the first sample of each run of flags (rising edge).
- Sampling: 5-min CGM input (native Dexcom readings for 5 min; see common/docs/deviations.md E1).
- Fixed settings (not tuned): sampling_min = 5, median_points = 3, gain_rule = grid, night_end_h = 7, l_floor = 0.02, l_provisional = 1e+06, kalman_sigma_w2 = 0.01, kalman_sigma_v2 = 4, kalman_p0_rate_sd = 5, kalman_p0_acc_sd = 2.5, kalman_warmup_samples = 2.
- Tuned parameters: Th_Res (mg/dL), Th_Der (mg/dL/min), L (mg/dL/min^2).
- Tuning: F2 (beta = 2). Ties: higher F2, then lower FP/day, then shorter mean delay, then grid order.
- Route B: 5 participant folds stratified by group. Each fold is tuned on the other 4 and scored on its held-out participants. An all_participants set is also tuned once on everyone.

## Grid

Source: Hochsmann 2026 Supplementary Table 1, Equation 7: Th_Res in {1.0, 1.1, ..., 4.0} mg/dL, Th_Der in {0.2, 0.3, 0.4, 0.5} mg/dL/min. L: 8 log-spaced values 0.02 to 0.6 plus 0.28 mg/dL/min^2, set after the first run to cover its night-rule values (deviations F5b). 1,116 grid points. Edge hits count the 6 Route B sets (5 folds and all_participants) on the lower or upper grid bound.

| Parameter | Values | n | Edge hits, refractory (main) | Edge hits, tp_lockout (comparison only) |
|---|---|---|---|---|
| Th_Res (mg/dL) | 1 to 4, step 0.1 | 31 | low 5/6, high 0/6 | low 6/6, high 0/6 |
| Th_Der (mg/dL/min) | 0.2 to 0.5, step 0.1 | 4 | low 0/6, high 5/6 | low 0/6, high 6/6 |
| L (mg/dL/min^2) | 0.02, 0.0325, 0.0529, 0.0859, 0.14, 0.227, 0.28, 0.369, 0.6 | 9 | low 1/6, high 0/6 | low 6/6, high 0/6 |

A parameter on a grid bound may mean the best value lies outside the grid. Forced edges (shared by every tied grid point) are listed with the locked parameters.

## Detection

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. 95 % participant-bootstrap CI in brackets.

| Rule | Sens % | Prec % | F2 | FP/day | Delay median (min) |
|---|---|---|---|---|---|
| refractory, ours (main) | 77.7 [73.6, 81.9] | 69.1 [64.8, 73.6] | 0.758 [0.721, 0.798] | 0.69 [0.57, 0.82] | 30 [28, 33] |
| tp_lockout, ours (comparison only) | 90.9 [88.0, 93.7] | 66.1 [61.7, 70.5] | 0.846 [0.817, 0.873] | 0.92 [0.76, 1.11] | 28 [27, 30] |
| tp_lockout, review (comparison only) | 88.0 [84.7, 91.1] | 62.1 [57.8, 66.3] | 0.812 [0.781, 0.842] | 1.07 [0.90, 1.27] | 30 [28, 33] |

Rules:

- refractory (main): 120-min refractory after every kept detection, applied before scoring. Label-free.
- tp_lockout (comparison only): 120-min lockout after each TP, applied at scoring (Hochsmann 2026). Uses meal labels.
- Matching rules: ours = -30 to +120 min; review = 0 to +120 min (Hochsmann 2026).

## By group

#### Sensitivity (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 74.3 [67.1, 81.7] | 78.3 [70.0, 85.9] | 80.9 [74.1, 87.0] | 6.7 |
| tp_lockout, ours (comparison only) | 89.9 [86.2, 93.6] | 90.1 [82.8, 96.1] | 92.7 [88.5, 96.4] | 2.9 |
| tp_lockout, review (comparison only) | 86.1 [80.5, 90.8] | 87.7 [79.8, 94.1] | 90.5 [86.6, 94.1] | 4.4 |

#### Precision (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 65.4 [55.8, 73.8] | 72.6 [65.9, 79.4] | 70.1 [64.4, 76.4] | 7.2 |
| tp_lockout, ours (comparison only) | 62.8 [54.0, 70.8] | 69.1 [62.3, 76.3] | 67.3 [61.4, 73.4] | 6.2 |
| tp_lockout, review (comparison only) | 59.5 [50.7, 67.7] | 63.8 [57.1, 70.8] | 63.4 [57.9, 69.3] | 4.3 |

#### FP/day by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (per day).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 0.78 [0.55, 1.07] | 0.58 [0.42, 0.75] | 0.69 [0.52, 0.87] | 0.20 |
| tp_lockout, ours (comparison only) | 1.06 [0.75, 1.48] | 0.80 [0.57, 1.04] | 0.90 [0.67, 1.16] | 0.26 |
| tp_lockout, review (comparison only) | 1.17 [0.82, 1.62] | 0.98 [0.74, 1.24] | 1.05 [0.80, 1.31] | 0.19 |

## By meal

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. FP cannot be assigned to a meal, so only Sens and delay.

| Rule | Sens % breakfast | Delay median breakfast | Sens % lunch | Delay median lunch |
|---|---|---|---|---|
| refractory, ours (main) | 81.7 [75.0, 88.2] | 26 [24, 28] | 73.8 [69.0, 78.6] | 37 [35, 39] |
| tp_lockout, ours (comparison only) | 92.1 [86.3, 96.7] | 24 [23, 27] | 89.8 [86.1, 93.3] | 34 [32, 36] |
| tp_lockout, review (comparison only) | 90.8 [84.9, 95.8] | 26 [24, 27] | 85.2 [81.7, 88.8] | 36 [34, 39] |

## Recovery agreement

Segmentation: excursion (frozen definition, common/docs/deviations.md section X). Detector anchor = detection time; reference anchor = logged meal start.

#### ICC(A,1) by feature

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs with complete data; recovery time leaves out pairs with no_rise at either anchor.

| Rule | n pairs | n (recovery time) | Recovery time | Peak height | iAUC | Peak time |
|---|---|---|---|---|---|---|
| refractory, ours (main) | 513 | 496 | 0.71 | 0.88 | 0.90 | 0.52 |
| tp_lockout, ours (comparison only) | 600 | 577 | 0.73 | 0.89 | 0.92 | 0.57 |
| tp_lockout, review (comparison only) | 581 | 558 | 0.73 | 0.90 | 0.93 | 0.54 |

#### Recovery time by stratum, refractory (main)

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs used. Bias = detector minus reference (min).

| Stratum | n | ICC | Bias (min) | 95 % LoA (min) |
|---|---|---|---|---|
| overall | 496 | 0.71 | 10 | -43 to 63 |
| healthy | 172 | 0.74 | 3 | -47 to 54 |
| prediabetes | 153 | 0.73 | 14 | -39 to 67 |
| T2D | 171 | 0.64 | 12 | -42 to 66 |
| breakfast | 268 | 0.84 | 3 | -33 to 38 |
| lunch | 228 | 0.62 | 18 | -47 to 82 |

## Locked parameters (all_participants)

Route B, tuned once on all 42 participants. Candidate lock for AI-READI. No held-out score.

| Rule | Th_Res | Th_Der | L | Forced grid edges |
|---|---|---|---|---|
| refractory, ours (main) | 1 | 0.5 | 0.0325 | Th_Res, Th_Der |
| tp_lockout, ours (comparison only) | 1 | 0.5 | 0.02 | Th_Res, Th_Der, L |
| tp_lockout, review (comparison only) | 1 | 0.5 | 0.02 | Th_Res, Th_Der, L |

Fold sets: `<rule>/params/chosen_params_routeB_<matching rule>.json`.

Hochsmann 2026 Table 1 (tuned per participant, mean +/- SD; their cohort): Th_Der 0.23 +/- 0.11, Th_Res 1.25 +/- 0.54, f2 0.82 +/- 0.09.

## Comparison with Hochsmann 2026 Table 2 (not like-for-like)

Hochsmann 2026 cohort: 16 healthy young adults, Libre 2 (resampled to 5 min), 3 meals/day, afternoon detections suppressed, per-participant tuning. Ours: CGMacros, Route B, test data. Delay is the mean, as in Table 2.

| Data | Rule | Sens % | FP/day | Delay mean (min) |
|---|---|---|---|---|
| Hochsmann 2026 Table 2 | tp_lockout, review | 64.4 | 1.39 | 39.6 |
| CGMacros, Route B | tp_lockout, review (comparison only) | 88.0 [84.7, 91.1] | 1.07 [0.90, 1.27] | 36.0 [32.6, 40.2] |
| CGMacros, Route B | tp_lockout, ours (comparison only) | 90.9 [88.0, 93.7] | 0.92 [0.76, 1.11] | 29.3 [26.0, 32.9] |
| CGMacros, Route B | refractory, ours (main) | 77.7 [73.6, 81.9] | 0.69 [0.57, 0.82] | 35.0 [31.1, 39.1] |

The closest row is tp_lockout with the review matching rule. Differences remain: cohort, sensor, meals scored (breakfast and lunch here), scoring window (07:00 to lunch + 180 min here) and tuning (per participant in the review; one global set in Route B).

Original paper (Faccioli 2022 Table 2: median [IQR] over 30 T1D adults, free-living, 180-min TP window, not like-for-like): recall pct 70 [13], precision pct 73 [26], fp per day 1.4 [1.4], detection time min 45 [45].

## Deviations

- Method: `methods/faccioli/docs/deviations.md`.
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
python common/run_protocol.py faccioli
python common/run_protocol.py faccioli --docs-only
```

The first runs the full protocol and also rewrites `results/method_comparison.md`. The second rebuilds this README and the comparison from the saved outputs.
