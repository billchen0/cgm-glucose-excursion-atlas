# Faccioli STMD, night gain rule: standard protocol (protocol_v1_nightgain)

## Summary

- Faccioli STMD, night gain rule on CGMacros (Dexcom, 42 participants). Standard protocol (protocol_v1_nightgain), run on 2026-10-05.
- Main adjacent rule: refractory. Route B only. Matching window -30 to +120 min around the logged meal start. Why refractory: common/docs/deviations.md Z1.
- Main result, Route B: Sens 20.3 [16.2, 24.4] %, Prec 88.7 [79.2, 96.7] %, F2 0.240 [0.193, 0.285], FP/day 0.05 [0.01, 0.10], delay median 34 [28, 37] min.
- Recovery-time ICC(A,1), main rule: 0.77 (n = 133 TP pairs; excursion segmentation).
- tp_lockout (comparison only, uses meal labels): Sens 20.4 [16.3, 24.6] %, Prec 88.2 [79.0, 96.4] %, FP/day 0.05 [0.02, 0.11].
- Locked all_participants set, main rule: Th_Res 1, Th_Der 0.2. Forced grid edges: Th_Res, Th_Der.

## Method, sampling and parameters

- Source: Faccioli S, Sala-Mira I, Diez JL, Facchinetti A, Sparacino G, Del Favero S, Bondia J. Super-twisting-based meal detector for type 1 diabetes management: improvement and assessment in a real-life scenario. Comput Methods Programs Biomed 2022;219:106736. https://doi.org/10.1016/j.cmpb.2022.106736
- Implementation: Hochsmann 2026 review rule (Supplementary Table 1 Eq. 7, 3-point median filter, gain per day). Observer, Kalman filter and gain rule from Faccioli 2022. CGM only: the observer has no insulin term.
- A causal 3-point median filter removes single-sample CGM spikes.
- A super-twisting observer (implicit discretisation) tracks glucose. Its residual Res rises when the glucose disturbance exceeds the bound L.
- This run: L is set each day from that day's night (00:00 to 07:00), as the largest disturbance estimate there (Faccioli's first-night rule, per day; deviations F5a). Superseded by the grid gain (protocol_v1).
- A Kalman filter (three-state, Faccioli's noise settings) gives the glucose derivative dG.
- A meal flag is raised when Res > Th_Res and dG > Th_Der (Eq. 7). A detection is the first sample of each run of flags (rising edge).
- Sampling: 5-min CGM input (native Dexcom readings for 5 min; see common/docs/deviations.md E1).
- Fixed settings (not tuned): sampling_min = 5, median_points = 3, gain_rule = night, night_end_h = 7, l_floor = 0.02, l_provisional = 1e+06, kalman_sigma_w2 = 0.01, kalman_sigma_v2 = 4, kalman_p0_rate_sd = 5, kalman_p0_acc_sd = 2.5, kalman_warmup_samples = 2.
- Tuned parameters: Th_Res (mg/dL), Th_Der (mg/dL/min).
- Tuning: F2 (beta = 2). Ties: higher F2, then lower FP/day, then shorter mean delay, then grid order.
- Route B: 5 participant folds stratified by group. Each fold is tuned on the other 4 and scored on its held-out participants. An all_participants set is also tuned once on everyone.

## Grid

Source: Hochsmann 2026 Supplementary Table 1, Equation 7: Th_Res in {1.0, 1.1, ..., 4.0} mg/dL, Th_Der in {0.2, 0.3, 0.4, 0.5} mg/dL/min. 124 grid points. Edge hits count the 6 Route B sets (5 folds and all_participants) on the lower or upper grid bound.

| Parameter | Values | n | Edge hits, refractory (main) | Edge hits, tp_lockout (comparison only) |
|---|---|---|---|---|
| Th_Res (mg/dL) | 1 to 4, step 0.1 | 31 | low 6/6, high 0/6 | low 6/6, high 0/6 |
| Th_Der (mg/dL/min) | 0.2 to 0.5, step 0.1 | 4 | low 5/6, high 0/6 | low 5/6, high 0/6 |

A parameter on a grid bound may mean the best value lies outside the grid. Forced edges (shared by every tied grid point) are listed with the locked parameters.

## Detection

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. 95 % participant-bootstrap CI in brackets.

| Rule | Sens % | Prec % | F2 | FP/day | Delay median (min) |
|---|---|---|---|---|---|
| refractory, ours (main) | 20.3 [16.2, 24.4] | 88.7 [79.2, 96.7] | 0.240 [0.193, 0.285] | 0.05 [0.01, 0.10] | 34 [28, 37] |
| tp_lockout, ours (comparison only) | 20.4 [16.3, 24.6] | 88.2 [79.0, 96.4] | 0.242 [0.195, 0.287] | 0.05 [0.02, 0.11] | 34 [28, 37] |
| tp_lockout, review (comparison only) | 20.0 [15.8, 24.0] | 85.7 [75.3, 94.5] | 0.236 [0.189, 0.281] | 0.07 [0.02, 0.13] | 34 [30, 38] |

Rules:

- refractory (main): 120-min refractory after every kept detection, applied before scoring. Label-free.
- tp_lockout (comparison only): 120-min lockout after each TP, applied at scoring (Hochsmann 2026). Uses meal labels.
- Matching rules: ours = -30 to +120 min; review = 0 to +120 min (Hochsmann 2026).

## By group

#### Sensitivity (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 12.2 [6.4, 18.1] | 20.2 [13.7, 26.2] | 29.1 [23.6, 34.7] | 16.8 |
| tp_lockout, ours (comparison only) | 12.2 [6.4, 18.1] | 20.2 [13.7, 26.2] | 29.5 [23.9, 35.1] | 17.3 |
| tp_lockout, review (comparison only) | 11.8 [6.1, 17.8] | 19.7 [12.8, 26.1] | 29.1 [23.6, 34.5] | 17.3 |

#### Precision (%) by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (pp).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 74.4 [48.6, 100.0] | 97.6 [93.5, 100.0] | 91.4 [84.2, 97.3] | 23.3 |
| tp_lockout, ours (comparison only) | 74.4 [48.6, 100.0] | 97.6 [93.5, 100.0] | 90.3 [82.1, 97.1] | 23.3 |
| tp_lockout, review (comparison only) | 71.8 [42.9, 100.0] | 93.0 [83.7, 100.0] | 88.9 [81.1, 95.9] | 21.2 |

#### FP/day by group

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. Groups: healthy 15, prediabetes 13, T2D 14 participants. Range = max minus min (per day).

| Rule | Healthy | Prediabetes | T2D | Range |
|---|---|---|---|---|
| refractory, ours (main) | 0.08 [0.00, 0.23] | 0.01 [0.00, 0.03] | 0.05 [0.02, 0.10] | 0.07 |
| tp_lockout, ours (comparison only) | 0.08 [0.00, 0.23] | 0.01 [0.00, 0.03] | 0.06 [0.02, 0.12] | 0.07 |
| tp_lockout, review (comparison only) | 0.09 [0.00, 0.25] | 0.03 [0.00, 0.08] | 0.07 [0.03, 0.13] | 0.06 |

## By meal

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. FP cannot be assigned to a meal, so only Sens and delay.

| Rule | Sens % breakfast | Delay median breakfast | Sens % lunch | Delay median lunch |
|---|---|---|---|---|
| refractory, ours (main) | 25.6 [19.4, 32.2] | 28 [25, 36] | 15.1 [10.9, 19.2] | 39 [34, 48] |
| tp_lockout, ours (comparison only) | 25.9 [19.6, 32.8] | 28 [25, 35] | 15.1 [10.9, 19.2] | 39 [34, 48] |
| tp_lockout, review (comparison only) | 25.9 [19.6, 32.8] | 28 [25, 35] | 14.2 [10.2, 18.3] | 43 [36, 51] |

## Recovery agreement

Segmentation: excursion (frozen definition, common/docs/deviations.md section X). Detector anchor = detection time; reference anchor = logged meal start.

#### ICC(A,1) by feature

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs with complete data; recovery time leaves out pairs with no_rise at either anchor.

| Rule | n pairs | n (recovery time) | Recovery time | Peak height | iAUC | Peak time |
|---|---|---|---|---|---|---|
| refractory, ours (main) | 134 | 133 | 0.77 | 0.89 | 0.93 | 0.54 |
| tp_lockout, ours (comparison only) | 135 | 134 | 0.77 | 0.89 | 0.93 | 0.54 |
| tp_lockout, review (comparison only) | 132 | 131 | 0.76 | 0.89 | 0.93 | 0.53 |

#### Recovery time by stratum, refractory (main)

Route B, test data (5 held-out folds pooled), 42 participants, 332 scored days. n = TP pairs used. Bias = detector minus reference (min).

| Stratum | n | ICC | Bias (min) | 95 % LoA (min) |
|---|---|---|---|---|
| overall | 133 | 0.77 | 12 | -36 to 59 |
| healthy | 29 | 0.79 | 6 | -53 to 66 |
| prediabetes | 41 | 0.87 | 9 | -28 to 47 |
| T2D | 63 | 0.68 | 16 | -30 to 63 |
| breakfast | 84 | 0.87 | 7 | -25 to 40 |
| lunch | 49 | 0.68 | 20 | -44 to 83 |

## Locked parameters (all_participants)

Route B, tuned once on all 42 participants. Candidate lock for AI-READI. No held-out score.

| Rule | Th_Res | Th_Der | Forced grid edges |
|---|---|---|---|
| refractory, ours (main) | 1 | 0.2 | Th_Res, Th_Der |
| tp_lockout, ours (comparison only) | 1 | 0.2 | Th_Res, Th_Der |
| tp_lockout, review (comparison only) | 1 | 0.2 | Th_Res, Th_Der |

Fold sets: `<rule>/params/chosen_params_routeB_<matching rule>.json`.

Hochsmann 2026 Table 1 (tuned per participant, mean +/- SD; their cohort): Th_Der 0.23 +/- 0.11, Th_Res 1.25 +/- 0.54, f2 0.82 +/- 0.09.

## Comparison with Hochsmann 2026 Table 2 (not like-for-like)

Hochsmann 2026 cohort: 16 healthy young adults, Libre 2 (resampled to 5 min), 3 meals/day, afternoon detections suppressed, per-participant tuning. Ours: CGMacros, Route B, test data. Delay is the mean, as in Table 2.

| Data | Rule | Sens % | FP/day | Delay mean (min) |
|---|---|---|---|---|
| Hochsmann 2026 Table 2 | tp_lockout, review | 64.4 | 1.39 | 39.6 |
| CGMacros, Route B | tp_lockout, review (comparison only) | 20.0 [15.8, 24.0] | 0.07 [0.02, 0.13] | 41.5 [35.8, 47.8] |
| CGMacros, Route B | tp_lockout, ours (comparison only) | 20.4 [16.3, 24.6] | 0.05 [0.02, 0.11] | 39.7 [33.9, 46.2] |
| CGMacros, Route B | refractory, ours (main) | 20.3 [16.2, 24.4] | 0.05 [0.01, 0.10] | 39.8 [33.9, 46.3] |

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
