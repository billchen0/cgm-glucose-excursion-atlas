# Popp SBE: standard protocol (protocol_v1)

## Summary

- Popp SBE on CGMacros (Dexcom, 42 participants). Standard protocol (protocol_v1), run on 2026-10-05.
- Main adjacent rule: refractory. Route B only. Matching window -30 to +120 min around the logged meal start. Why refractory: common/docs/deviations.md Z1.
- Main result, Route B: Sens 63.8 [57.1, 70.1] %, Prec 69.8 [64.3, 75.0] %, F2 0.649 [0.588, 0.706], FP/day 0.55 [0.43, 0.68], delay median 43 [39, 47] min.
- Recovery-time ICC(A,1), main rule: 0.61 (n = 415 TP pairs; excursion segmentation).
- tp_lockout (comparison only, uses meal labels): Sens 68.0 [61.0, 74.6] %, Prec 60.7 [53.7, 67.9] %, FP/day 0.88 [0.65, 1.15].
- Locked all_participants set, main rule: phi 10, tau 40, epsilon 18. Forced grid edges: phi, epsilon.

## Method, sampling and parameters

- Source: Popp CJ et al. Objective determination of eating occasion timing: combining self-report, wrist motion, and continuous glucose monitoring to detect eating occasions in adults with prediabetes and obesity. J Diabetes Sci Technol 2024;18(2):266-272. https://doi.org/10.1177/19322968231197205. SBE method: Zheng M, Ni B, Kleinberg S. JAMIA 2019;26(12):1592-1599. https://doi.org/10.1093/jamia/ocz159.
- Implementation: Hochsmann 2026 review rule (Supplementary Table 1 Eqs. 11-13). Glucose model: Dalla Man 2007 meal model, normal-subject population parameters (curated BioModels SBML BIOMD0000000379), endogenous insulin only. Anchoring of the simulation is a default (deviations P5).
- The Dalla Man 2007 model predicts glucose without a meal, starting from its basal steady state at the observed glucose of an anchor sample.
- Div is the mean relative error between observed and predicted glucose over 30 min (Eq. 11). A candidate is a sample with Div > phi.
- The meal start m_st is the earliest sample within tau min from which glucose stays above the prediction (back-search).
- Meals of 25, 50, 75 and 100 g, eaten over 90 min from m_st, are simulated. A meal flag is raised when the RMS fit error of any load over [m_st, i] is below epsilon (Eqs. 12-13).
- A detection is the first sample of each run of flags (rising edge), at time i. m_st is kept as the excursion start.
- Sampling: 1-min CGM input (QC'd 1-min series, plan 2.2; Dexcom readings linearly interpolated to 1 min).
- Fixed settings (not tuned): sampling_min = 1, zeta_min = 30, loads_g = (25, 50, 75, 100), meal_duration_min = 90.
- Tuned parameters: phi (%), tau (min), epsilon (mg/dL).
- Tuning: F2 (beta = 2). Ties: higher F2, then lower FP/day, then shorter mean delay, then grid order.
- Route B: 5 participant folds stratified by group. Each fold is tuned on the other 4 and scored on its held-out participants. An all_participants set is also tuned once on everyone.

## Grid

Source: Hochsmann 2026 Supplementary Methods line 117 (global): zeta = 30 min, phi in {10, 12}, tau in {20, 30, 40, 50, 60} min, epsilon in {14, 15, 16, 17, 18}. 50 grid points. Edge hits count the 6 Route B sets (5 folds and all_participants) on the lower or upper grid bound.

| Parameter | Values | n | Edge hits, refractory (main) | Edge hits, tp_lockout (comparison only) |
|---|---|---|---|---|
| phi (%) | 10 to 12, step 2 | 2 | low 6/6, high 0/6 | low 6/6, high 0/6 |
| tau (min) | 20 to 60, step 10 | 5 | low 0/6, high 0/6 | low 0/6, high 0/6 |
| epsilon (mg/dL) | 14 to 18, step 1 | 5 | low 0/6, high 6/6 | low 0/6, high 6/6 |

A parameter on a grid bound may mean the best value lies outside the grid. Forced edges (shared by every tied grid point) are listed with the locked parameters.

## Detection

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. 95 % participant-bootstrap CI in brackets.

| Rule | Sens % | Prec % | F2 | FP/day | Delay median (min) |
|---|---|---|---|---|---|
| refractory, ours (main) | 63.8 [57.1, 70.1] | 69.8 [64.3, 75.0] | 0.649 [0.588, 0.706] | 0.55 [0.43, 0.68] | 43 [39, 47] |
| tp_lockout, ours (comparison only) | 68.0 [61.0, 74.6] | 60.7 [53.7, 67.9] | 0.664 [0.604, 0.721] | 0.88 [0.65, 1.15] | 39 [36, 42] |
| tp_lockout, review (comparison only) | 65.5 [58.4, 71.9] | 56.6 [49.6, 63.9] | 0.635 [0.574, 0.692] | 1.00 [0.75, 1.29] | 43 [40, 46] |

Rules:

- refractory (main): 120-min refractory after every kept detection, applied before scoring. Label-free.
- tp_lockout (comparison only): 120-min lockout after each TP, applied at scoring (Hochsmann 2026). Uses meal labels.
- Matching rules: ours = -30 to +120 min; review = 0 to +120 min (Hochsmann 2026).

## By group

#### Sensitivity (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 76.8 [70.7, 83.0] | 69.5 [63.4, 75.7] | 44.5 [31.7, 56.3] | 32.2 |
| tp_lockout, ours (comparison only) | 83.5 [79.0, 88.3] | 73.4 [67.5, 79.1] | 46.4 [33.3, 58.2] | 37.2 |
| tp_lockout, review (comparison only) | 79.8 [74.8, 84.5] | 71.9 [66.2, 77.5] | 44.1 [30.6, 56.0] | 35.7 |

#### Precision (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 68.4 [60.1, 77.0] | 76.2 [68.3, 84.7] | 64.5 [52.0, 75.2] | 11.7 |
| tp_lockout, ours (comparison only) | 57.9 [45.6, 71.3] | 66.2 [57.8, 76.6] | 59.0 [45.7, 71.4] | 8.3 |
| tp_lockout, review (comparison only) | 53.7 [42.4, 66.0] | 62.4 [53.2, 74.2] | 54.8 [39.7, 69.6] | 8.7 |

#### FP/day by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (per day).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 0.71 [0.48, 0.95] | 0.43 [0.25, 0.62] | 0.49 [0.32, 0.73] | 0.28 |
| tp_lockout, ours (comparison only) | 1.21 [0.70, 1.89] | 0.74 [0.44, 1.05] | 0.65 [0.40, 1.00] | 0.56 |
| tp_lockout, review (comparison only) | 1.37 [0.87, 2.06] | 0.85 [0.50, 1.21] | 0.73 [0.44, 1.16] | 0.64 |

## By meal

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. FP cannot be assigned to a meal, so only Sens and delay.

| Rule | Sens % breakfast | Delay median breakfast | Sens % lunch | Delay median lunch |
|---|---|---|---|---|
| refractory, ours (main) | 58.2 [49.2, 67.3] | 39 [34, 44] | 69.3 [61.1, 76.4] | 45 [42, 50] |
| tp_lockout, ours (comparison only) | 61.6 [52.3, 70.9] | 35 [31, 41] | 74.4 [66.2, 81.7] | 42 [38, 46] |
| tp_lockout, review (comparison only) | 60.4 [50.9, 69.8] | 40 [35, 43] | 70.5 [62.4, 77.6] | 45 [42, 50] |

## Recovery agreement

Segmentation: excursion (frozen definition, common/docs/deviations.md section X). Detector anchor = detection time; reference anchor = logged meal start.

#### ICC(A,1) by feature

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs with complete data; recovery time leaves out pairs with no_rise at either anchor.

| Rule | n pairs | n (recovery time) | Recovery time | Peak height | iAUC | Peak time |
|---|---|---|---|---|---|---|
| refractory, ours (main) | 421 | 415 | 0.61 | 0.86 | 0.85 | 0.43 |
| tp_lockout, ours (comparison only) | 449 | 441 | 0.63 | 0.86 | 0.87 | 0.44 |
| tp_lockout, review (comparison only) | 432 | 426 | 0.63 | 0.88 | 0.87 | 0.40 |

#### Recovery time by stratum, refractory (main)

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs used. Bias = detector minus reference (min).

| Stratum | n | ICC | Bias (min) | 95 % LoA (min) |
|---|---|---|---|---|
| overall | 415 | 0.61 | 8 | -56 to 72 |
| healthy | 180 | 0.70 | 3 | -52 to 57 |
| prediabetes | 138 | 0.59 | 8 | -61 to 78 |
| T2D | 97 | 0.46 | 17 | -51 to 86 |
| breakfast | 191 | 0.72 | 0 | -45 to 45 |
| lunch | 224 | 0.55 | 15 | -60 to 89 |

## Locked parameters (all_participants)

Route B, tuned once on all 42 participants. Candidate lock for AI-READI. No held-out score.

| Rule | phi | tau | epsilon | Forced grid edges |
|---|---|---|---|---|
| refractory, ours (main) | 10 | 40 | 18 | phi, epsilon |
| tp_lockout, ours (comparison only) | 10 | 40 | 18 | phi, epsilon |
| tp_lockout, review (comparison only) | 10 | 40 | 18 | phi, epsilon |

Fold sets: `<rule>/params/chosen_params_routeB_<matching rule>.json`.

Hochsmann 2026 Table 1 (tuned per participant, mean +/- SD; their cohort): phi 10 (printed as 0.10), tau 20, epsilon 18, f2 0.81 (global, no SD).

## Comparison with Hochsmann 2026 Table 2 (not like-for-like)

Hochsmann 2026 cohort: 16 healthy young adults, Libre 2 (1-min), 3 meals/day, afternoon detections suppressed, global tuning. Ours: CGMacros, Route B, test data. Delay is the mean, as in Table 2.

| Data | Rule | Sens % | FP/day | Delay mean (min) |
|---|---|---|---|---|
| Hochsmann 2026 Table 2 | tp_lockout, review | 82.9 | 1.28 | 60.5 |
| CGMacros, Route B | tp_lockout, review (comparison only) | 65.5 [58.4, 71.9] | 1.00 [0.75, 1.29] | 49.9 [45.9, 54.4] |
| CGMacros, Route B | tp_lockout, ours (comparison only) | 68.0 [61.0, 74.6] | 0.88 [0.65, 1.15] | 40.7 [36.5, 45.5] |
| CGMacros, Route B | refractory, ours (main) | 63.8 [57.1, 70.1] | 0.55 [0.43, 0.68] | 47.0 [42.7, 51.7] |

The closest row is tp_lockout with the review matching rule. Differences remain: cohort, sensor, meals scored (breakfast and lunch here), scoring window (07:00 to lunch + 180 min here) and tuning (per participant in the review; one global set in Route B).

Original paper (Popp 2024 compared eating-occasion timing across methods; it did not report sensitivity, FP/day or delay): reported not reported.

## Deviations

- Method: `methods/popp/docs/deviations.md`.
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
python common/run_protocol.py popp
python common/run_protocol.py popp --docs-only
```

The first runs the full protocol and also rewrites `results/method_comparison.md`. The second rebuilds this README and the comparison from the saved outputs.
