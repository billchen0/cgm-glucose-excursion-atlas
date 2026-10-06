# Harvey GRID: standard protocol (protocol_v1)

## Summary

- Harvey GRID on CGMacros (Dexcom, 42 participants). Standard protocol (protocol_v1), run on 2026-10-05.
- Main adjacent rule: refractory. Route B only. Matching window -30 to +120 min around the logged meal start. Why refractory: common/docs/deviations.md Z1.
- Main result, Route B: Sens 73.6 [69.7, 77.3] %, Prec 80.5 [76.2, 84.9] %, F2 0.749 [0.714, 0.782], FP/day 0.36 [0.27, 0.45], delay median 29 [27, 32] min.
- Recovery-time ICC(A,1), main rule: 0.72 (n = 478 TP pairs; excursion segmentation).
- tp_lockout (comparison only, uses meal labels): Sens 82.1 [78.6, 85.3] %, Prec 74.9 [69.2, 80.4] %, FP/day 0.55 [0.40, 0.72].
- Locked all_participants set, main rule: tau_F 5, G_min 100, G'_min,3 0.8, G'_min,2 0.8. Forced grid edges: G_min, G'_min,2.

## Method, sampling and parameters

- Source: Harvey RA et al. Design of the glucose rate increase detector. J Diabetes Sci Technol 2014;8(2):307-320. https://doi.org/10.1177/1932296814523881
- Implementation: As implemented in the Hochsmann 2026 review (Supplementary Methods, Supplementary Table 1 Eq. 8).
- A noise-spike filter and a low-pass filter smooth the CGM signal.
- The rate of change (ROC) comes from a 3-point Lagrange derivative.
- A sample is GRID+ when filtered glucose > G_min and the last 3 ROC > G'_min,3 or the last 2 ROC > G'_min,2.
- A detection is the first sample of each run of GRID+ (rising edge).
- Sampling: 5-min CGM input (native Dexcom readings for 5 min; see common/docs/deviations.md E1).
- Fixed settings (not tuned): spike_max_roc_mg_dl_per_min = 3.
- Tuned parameters: tau_F (min), G_min (mg/dL), G'_min,3 (mg/dL/min), G'_min,2 (mg/dL/min).
- Tuning: F2 (beta = 2). Ties: higher F2, then lower FP/day, then shorter mean delay, then grid order.
- Route B: 5 participant folds stratified by group. Each fold is tuned on the other 4 and scored on its held-out participants. An all_participants set is also tuned once on everyone.

## Grid

Source: Hochsmann 2026 Supplementary Table 1, Equation 8. 5,445 grid points. Edge hits count the 6 Route B sets (5 folds and all_participants) on the lower or upper grid bound.

| Parameter | Values | n | Edge hits, refractory (main) | Edge hits, tp_lockout (comparison only) |
|---|---|---|---|---|
| tau_F (min) | 4 to 8, step 1 | 5 | low 0/6, high 0/6 | low 6/6, high 0/6 |
| G_min (mg/dL) | 100 to 140, step 5 | 9 | low 5/6, high 0/6 | low 6/6, high 0/6 |
| G'_min,3 (mg/dL/min) | 0.8 to 1.8, step 0.1 | 11 | low 6/6, high 0/6 | low 6/6, high 0/6 |
| G'_min,2 (mg/dL/min) | 0.8 to 1.8, step 0.1 | 11 | low 6/6, high 0/6 | low 6/6, high 0/6 |

A parameter on a grid bound may mean the best value lies outside the grid. Forced edges (shared by every tied grid point) are listed with the locked parameters.

## Detection

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. 95 % participant-bootstrap CI in brackets.

| Rule | Sens % | Prec % | F2 | FP/day | Delay median (min) |
|---|---|---|---|---|---|
| refractory, ours (main) | 73.6 [69.7, 77.3] | 80.5 [76.2, 84.9] | 0.749 [0.714, 0.782] | 0.36 [0.27, 0.45] | 29 [27, 32] |
| tp_lockout, ours (comparison only) | 82.1 [78.6, 85.3] | 74.9 [69.2, 80.4] | 0.806 [0.775, 0.836] | 0.55 [0.40, 0.72] | 27 [24, 29] |
| tp_lockout, review (comparison only) | 80.6 [76.9, 83.9] | 71.3 [65.5, 77.0] | 0.786 [0.754, 0.817] | 0.64 [0.48, 0.84] | 28 [26, 30] |

Rules:

- refractory (main): 120-min refractory after every kept detection, applied before scoring. Label-free.
- tp_lockout (comparison only): 120-min lockout after each TP, applied at scoring (Hochsmann 2026). Uses meal labels.
- Matching rules: ours = -30 to +120 min; review = 0 to +120 min (Hochsmann 2026).

## By group

#### Sensitivity (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 70.0 [63.7, 76.7] | 73.9 [64.4, 81.2] | 77.3 [73.0, 80.9] | 7.2 |
| tp_lockout, ours (comparison only) | 81.9 [75.8, 87.9] | 78.8 [70.3, 84.7] | 85.5 [82.4, 88.3] | 6.6 |
| tp_lockout, review (comparison only) | 80.2 [74.3, 86.4] | 77.8 [69.3, 84.0] | 83.6 [80.3, 86.9] | 5.8 |

#### Precision (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 80.2 [71.4, 88.8] | 84.8 [79.1, 90.5] | 77.3 [70.8, 84.3] | 7.5 |
| tp_lockout, ours (comparison only) | 73.8 [61.9, 84.5] | 81.2 [75.0, 88.0] | 71.2 [62.7, 80.0] | 10.0 |
| tp_lockout, review (comparison only) | 69.6 [57.4, 81.5] | 77.5 [70.8, 84.9] | 68.4 [59.8, 77.5] | 9.0 |

#### FP/day by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (per day).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 0.34 [0.18, 0.54] | 0.26 [0.16, 0.38] | 0.45 [0.28, 0.64] | 0.19 |
| tp_lockout, ours (comparison only) | 0.58 [0.30, 0.97] | 0.36 [0.21, 0.51] | 0.69 [0.42, 1.02] | 0.33 |
| tp_lockout, review (comparison only) | 0.70 [0.37, 1.15] | 0.45 [0.27, 0.63] | 0.77 [0.48, 1.12] | 0.33 |

## By meal

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. FP cannot be assigned to a meal, so only Sens and delay.

| Rule | Sens % breakfast | Delay median breakfast | Sens % lunch | Delay median lunch |
|---|---|---|---|---|
| refractory, ours (main) | 80.2 [72.8, 86.8] | 24 [22, 26] | 67.2 [62.5, 71.8] | 36 [34, 39] |
| tp_lockout, ours (comparison only) | 89.6 [82.8, 95.5] | 23 [20, 24] | 74.7 [70.5, 79.2] | 33 [30, 36] |
| tp_lockout, review (comparison only) | 89.6 [82.8, 95.5] | 23 [21, 25] | 71.7 [66.8, 76.6] | 35 [33, 38] |

## Recovery agreement

Segmentation: excursion (frozen definition, common/docs/deviations.md section X). Detector anchor = detection time; reference anchor = logged meal start.

#### ICC(A,1) by feature

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs with complete data; recovery time leaves out pairs with no_rise at either anchor.

| Rule | n pairs | n (recovery time) | Recovery time | Peak height | iAUC | Peak time |
|---|---|---|---|---|---|---|
| refractory, ours (main) | 486 | 478 | 0.72 | 0.90 | 0.92 | 0.52 |
| tp_lockout, ours (comparison only) | 542 | 532 | 0.75 | 0.91 | 0.93 | 0.54 |
| tp_lockout, review (comparison only) | 532 | 522 | 0.73 | 0.90 | 0.92 | 0.55 |

#### Recovery time by stratum, refractory (main)

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs used. Bias = detector minus reference (min).

| Stratum | n | ICC | Bias (min) | 95 % LoA (min) |
|---|---|---|---|---|
| overall | 478 | 0.72 | 12 | -40 to 63 |
| healthy | 165 | 0.77 | 6 | -43 to 56 |
| prediabetes | 148 | 0.76 | 13 | -34 to 61 |
| T2D | 165 | 0.61 | 15 | -41 to 71 |
| breakfast | 263 | 0.85 | 4 | -29 to 38 |
| lunch | 215 | 0.62 | 20 | -43 to 84 |

## Locked parameters (all_participants)

Route B, tuned once on all 42 participants. Candidate lock for AI-READI. No held-out score.

| Rule | tau_F | G_min | G'_min,3 | G'_min,2 | Forced grid edges |
|---|---|---|---|---|---|
| refractory, ours (main) | 5 | 100 | 0.8 | 0.8 | G_min, G'_min,2 |
| tp_lockout, ours (comparison only) | 4 | 100 | 0.8 | 0.8 | tau_F, G_min, G'_min,2 |
| tp_lockout, review (comparison only) | 4 | 100 | 0.8 | 0.8 | tau_F, G_min, G'_min,2 |

Fold sets: `<rule>/params/chosen_params_routeB_<matching rule>.json`.

## Comparison with Hochsmann 2026 Table 2 (not like-for-like)

Hochsmann 2026 cohort: 16 healthy young adults, Libre 2 (1-min resampled to 5 min), 3 meals/day, afternoon detections suppressed. Ours: CGMacros, Route B, test data. Delay is the mean, as in Table 2.

| Data | Rule | Sens % | FP/day | Delay mean (min) |
|---|---|---|---|---|
| Hochsmann 2026 Table 2 | tp_lockout, review | 70.4 | 0.26 | 37.3 |
| CGMacros, Route B | tp_lockout, review (comparison only) | 80.6 [76.9, 83.9] | 0.64 [0.48, 0.84] | 35.7 [31.4, 40.9] |
| CGMacros, Route B | tp_lockout, ours (comparison only) | 82.1 [78.6, 85.3] | 0.55 [0.40, 0.72] | 31.0 [26.8, 35.9] |
| CGMacros, Route B | refractory, ours (main) | 73.6 [69.7, 77.3] | 0.36 [0.27, 0.45] | 35.7 [31.3, 40.9] |

The closest row is tp_lockout with the review matching rule. Differences remain: cohort, sensor, meals scored (breakfast and lunch here), scoring window (07:00 to lunch + 180 min here) and tuning (per participant in the review; one global set in Route B).

## Deviations

- Method: `methods/harvey/docs/deviations.md`.
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
python common/run_protocol.py harvey
python common/run_protocol.py harvey --docs-only
```

The first runs the full protocol and also rewrites `results/method_comparison.md`. The second rebuilds this README and the comparison from the saved outputs.
