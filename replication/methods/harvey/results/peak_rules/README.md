# Harvey (GRID) with label-free adjacent-detection rules

Run: `python methods/harvey/src/run_harvey_peak_rules.py` (about 65 s, deterministic).
The script reads `summary.csv`, `detections.csv`, `recovery_agreement.csv` and `params/` in
`methods/harvey/results/reference_tp_lockout/`. Regenerate them first with `methods/harvey/src/run_harvey.py`.
This script does not write to `reference_tp_lockout/`.

## Rule roles

- `tp_lockout`: reference only. It uses meal logs, so it cannot be deployed.
- `baseline_return`: candidate main rule, pending mentor confirmation.
- `refractory` and `meal_window_max_peak`: sensitivity analyses.

## Which rule each result uses

The setting is `[scoring] adjacent_rule` in `common/configs/cgmacros_eval.toml`.

| `adjacent_rule` | Where | What it does | TP lockout |
|---|---|---|---|
| `tp_lockout` (**reference only**) | `methods/harvey/results/reference_tp_lockout/` (unchanged) | No post-processing. Unmatched detections within 120 min after a TP are ignored when scoring (Hochsmann 2026). Uses meal labels. | yes |
| `meal_window_max_peak` (**sensitivity**) | `meal_window_max_peak/` | Before scoring: keep one detection per Lim 2026 clock window, the one with the highest peak. Detections outside every window are dropped. Label-free. | no |
| `refractory` (**sensitivity**) | `refractory/` | Before scoring: drop a detection that is <= 120 min after the previous kept one. Label-free. | no |
| `baseline_return` (**candidate main**) | `baseline_return/` | Before scoring, in time order on the QC'd 1-min glucose. The first detection opens an event (anchor d0). Baseline b = min glucose in [d0 - 60 min, d0]; if there is no valid data before d0 in that window, b = glucose at d0 and the event is flagged. Running peak P(t) = max glucose in (d0, t]. The event closes at the first t after the time of P(t) with glucose(t) <= b + max(10 mg/dL, 0.20 * (P(t) - b)). Not closed by d0 + 180 min: it closes there and is flagged censored. A QC gap never counts as a return. Detections before the close are merged into the anchor and removed; the anchor is kept. The first detection at or after the close opens a new event. Parameters (60, 10, 0.20, 180) are fixed and not tuned. Label-free. | no |

- **Meal windows** (Lim 2026, JDST 20(3):664-672, p. 666): breakfast 06:00-11:45, lunch 12:00-16:00, dinner 17:00-21:00.
- **meal_window_max_peak peak:** max of the QC'd 1-min glucose in (t, t + 180 min]. Ties go to the earlier detection.
- **Recovery features are unchanged and PROVISIONAL.** Their baseline is the mean 1-min glucose in [anchor - 30 min, anchor) (`common/evaluation/metrics.py`, `recovery_features`). This differs from the baseline_return baseline.
- **Unchanged:** QC, grid, Route A/B splits, F2 tuning and tie-breaks, and our matching window (-30 to +120 min). Only our matching rule is run.
- **Re-tuning:** each label-free rule is applied inside the grid search, so each rule has its own tuned parameters.
- **Processing unit:** the detector and the rules run per participant-day (00:00-23:55). An event's glucose is followed past midnight, but it does not merge detections of the next day (deviations, entry 2026-10-01).

## Files

| File | Content |
|---|---|
| `comparison.csv`, `comparison.md` | All four rules, Route A and B, all strata, 95 % participant-bootstrap CI; `comparison.md` holds tables a to g below. |
| `detection_counts.csv` | Per rule and route at the locked parameters: raw, removed by the rule (inside and outside the scoring window), ignored by the TP lockout, kept and scored. |
| `merge_by_group.csv` | baseline_return only: raw detections, % merged, events, % censored, % fallback baseline, per route and group. |
| `<rule>/summary*.csv` | Same format as `reference_tp_lockout/`, with an extra `adjacent_rule` column. |
| `<rule>/params/chosen_params_route{A,B}_ours.json` | Locked parameters with `grid_edges` and `grid_edges_forced`. |
| `<rule>/recovery_agreement.csv`, `<rule>/plots/` | Recovery-feature agreement and Bland-Altman plots. |
| `<rule>/splits.csv`, `<rule>/sample_sizes.csv` | Splits and counts (identical across rules). |
| `<rule>/detections.csv`, `meals.csv`, `recovery_features.csv` | Row-level tables, not committed. Removed detections have status `removed_in_window` or `removed_outside_window`. For baseline_return, `detections.csv` also has `event_anchor`, `event_baseline`, `event_close`, `event_censored`, `event_fallback`. |

## Results (test data, our matching rule, 95 % participant-bootstrap CI)

Route A tests each participant's test days with that participant's parameters.
Route B pools the five held-out folds. FP/day uses scored days.

### a) Overall detection

| Route | Rule | TP | FP | FN | Sens % | Prec % | F2 | FP/day | Delay median | Delay mean |
|---|---|---|---|---|---|---|---|---|---|---|
| A | tp_lockout | 253 | 67 | 80 | 76.0 [70.7, 81.3] | 79.1 [75.3, 83.1] | 0.766 [0.721, 0.812] | 0.40 [0.31, 0.49] | 27 [25, 30] | 32.6 [27.5, 38.3] |
| A | meal_window_max_peak | 221 | 36 | 112 | 66.4 [60.1, 72.8] | 86.0 [81.0, 91.2] | 0.695 [0.637, 0.756] | 0.22 [0.14, 0.29] | 28 [26, 31] | 33.0 [28.2, 38.5] |
| A | refractory | 232 | 58 | 101 | 69.7 [63.5, 75.5] | 80.0 [75.9, 84.5] | 0.715 [0.661, 0.768] | 0.35 [0.26, 0.43] | 28 [26, 31] | 33.5 [28.9, 38.9] |
| A | baseline_return | 241 | 74 | 92 | 72.4 [67.0, 77.7] | 76.5 [71.5, 81.8] | 0.732 [0.686, 0.777] | 0.44 [0.32, 0.58] | 27 [26, 30] | 33.0 [28.4, 38.5] |
| B | tp_lockout | 542 | 182 | 118 | 82.1 [78.6, 85.3] | 74.9 [69.2, 80.4] | 0.806 [0.775, 0.836] | 0.55 [0.40, 0.72] | 27 [24, 29] | 31.0 [26.8, 35.9] |
| B | meal_window_max_peak | 441 | 72 | 219 | 66.8 [62.1, 71.0] | 86.0 [81.8, 89.9] | 0.699 [0.656, 0.739] | 0.22 [0.15, 0.29] | 28 [26, 31] | 33.5 [28.9, 38.9] |
| B | refractory | 486 | 118 | 174 | 73.6 [69.7, 77.3] | 80.5 [76.2, 84.9] | 0.749 [0.714, 0.782] | 0.36 [0.27, 0.45] | 29 [27, 32] | 35.7 [31.3, 40.9] |
| B | baseline_return | 500 | 168 | 160 | 75.8 [72.1, 79.0] | 74.9 [69.6, 80.2] | 0.756 [0.724, 0.786] | 0.51 [0.37, 0.65] | 28 [26, 30] | 33.9 [29.6, 38.8] |

### b) By glycaemic group

| Route | Rule | Sens % healthy | Sens % prediabetes | Sens % T2D | Sens range (pp) | Prec % healthy | Prec % prediabetes | Prec % T2D | FP/day healthy | FP/day prediabetes | FP/day T2D |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | tp_lockout | 70.0 [60.0, 80.0] | 79.2 [69.9, 86.5] | 79.5 [73.2, 85.7] | 9.5 | 78.5 [73.2, 84.4] | 79.2 [71.4, 87.9] | 79.5 [73.3, 86.8] | 0.38 [0.25, 0.52] | 0.41 [0.22, 0.63] | 0.41 [0.25, 0.55] |
| A | meal_window_max_peak | 61.7 [49.2, 73.3] | 68.3 [58.4, 78.0] | 69.6 [60.7, 77.7] | 8.0 | 80.4 [70.3, 88.9] | 88.5 [79.0, 97.3] | 89.7 [82.2, 96.4] | 0.30 [0.17, 0.43] | 0.18 [0.04, 0.33] | 0.16 [0.05, 0.29] |
| A | refractory | 61.7 [50.0, 73.3] | 73.3 [62.7, 82.5] | 75.0 [67.9, 82.1] | 13.3 | 76.3 [67.7, 84.4] | 82.2 [76.0, 89.8] | 81.5 [74.1, 89.5] | 0.38 [0.25, 0.53] | 0.31 [0.16, 0.47] | 0.34 [0.18, 0.50] |
| A | baseline_return | 68.3 [59.2, 77.5] | 73.3 [62.1, 83.0] | 75.9 [68.8, 83.0] | 7.6 | 68.3 [61.6, 76.2] | 83.2 [74.0, 93.6] | 80.2 [71.6, 88.0] | 0.63 [0.40, 0.90] | 0.29 [0.10, 0.53] | 0.38 [0.21, 0.57] |
| B | tp_lockout | 81.9 [75.8, 87.9] | 78.8 [70.3, 84.7] | 85.5 [82.4, 88.3] | 6.6 | 73.8 [61.9, 84.5] | 81.2 [75.0, 88.0] | 71.2 [62.7, 80.0] | 0.58 [0.30, 0.97] | 0.36 [0.21, 0.51] | 0.69 [0.42, 1.02] |
| B | meal_window_max_peak | 66.2 [59.2, 73.7] | 67.5 [58.1, 75.0] | 66.8 [59.2, 74.1] | 1.3 | 84.9 [77.3, 91.8] | 90.1 [84.0, 95.4] | 83.5 [75.6, 90.6] | 0.24 [0.12, 0.37] | 0.15 [0.07, 0.24] | 0.26 [0.15, 0.41] |
| B | refractory | 70.0 [63.7, 76.7] | 73.9 [64.4, 81.2] | 77.3 [73.0, 80.9] | 7.2 | 80.2 [71.4, 88.8] | 84.8 [79.1, 90.5] | 77.3 [70.8, 84.3] | 0.34 [0.18, 0.54] | 0.26 [0.16, 0.38] | 0.45 [0.28, 0.64] |
| B | baseline_return | 73.0 [67.8, 78.7] | 76.8 [67.5, 83.7] | 77.7 [73.9, 81.2] | 4.7 | 68.9 [59.5, 79.1] | 79.2 [70.1, 88.3] | 77.7 [69.4, 85.3] | 0.66 [0.39, 1.00] | 0.40 [0.20, 0.65] | 0.45 [0.27, 0.67] |

### c) By meal

| Route | Rule | Sens % breakfast | Delay median breakfast | Sens % lunch | Delay median lunch |
|---|---|---|---|---|---|
| A | tp_lockout | 86.1 [79.2, 92.8] | 23 [22, 25] | 65.9 [58.7, 73.0] | 35 [33, 39] |
| A | meal_window_max_peak | 75.9 [68.1, 83.8] | 24 [22, 26] | 56.9 [48.8, 65.5] | 36 [32, 40] |
| A | refractory | 77.7 [70.1, 85.0] | 23 [22, 25] | 61.7 [53.6, 69.6] | 36 [34, 41] |
| A | baseline_return | 81.9 [75.4, 88.6] | 24 [22, 26] | 62.9 [55.1, 70.7] | 35 [33, 39] |
| B | tp_lockout | 89.6 [82.8, 95.5] | 23 [20, 24] | 74.7 [70.5, 79.2] | 33 [30, 36] |
| B | meal_window_max_peak | 76.2 [68.6, 83.1] | 24 [22, 26] | 57.5 [51.8, 63.1] | 35 [33, 39] |
| B | refractory | 80.2 [72.8, 86.8] | 24 [22, 26] | 67.2 [62.5, 71.8] | 36 [34, 39] |
| B | baseline_return | 82.9 [76.1, 88.9] | 23 [21, 25] | 68.7 [63.7, 73.5] | 35 [33, 38] |

### d) Recovery-feature agreement (TP pairs, overall; PROVISIONAL segmentation)

| Route | Rule | Feature | n | ICC(A,1) | BA bias | 95 % LoA |
|---|---|---|---|---|---|---|
| A | tp_lockout | recovery_time_min | 253 | 0.60 | 13.8 | -59.5 to 87.2 |
| A | meal_window_max_peak | recovery_time_min | 221 | 0.58 | 11.1 | -65.5 to 87.7 |
| A | refractory | recovery_time_min | 232 | 0.61 | 14.2 | -58.0 to 86.5 |
| A | baseline_return | recovery_time_min | 241 | 0.61 | 13.3 | -58.7 to 85.4 |
| A | tp_lockout | peak_height | 253 | 0.95 | 0.6 | -30.2 to 31.5 |
| A | meal_window_max_peak | peak_height | 221 | 0.96 | -1.4 | -30.1 to 27.3 |
| A | refractory | peak_height | 232 | 0.95 | 0.7 | -30.3 to 31.7 |
| A | baseline_return | peak_height | 241 | 0.95 | 0.6 | -29.3 to 30.4 |
| A | tp_lockout | iauc | 253 | 0.95 | 290.0 | -3597.9 to 4177.9 |
| A | meal_window_max_peak | iauc | 221 | 0.95 | 83.6 | -3807.9 to 3975.0 |
| A | refractory | iauc | 232 | 0.94 | 303.3 | -3582.4 to 4189.1 |
| A | baseline_return | iauc | 241 | 0.95 | 263.4 | -3399.2 to 3926.0 |
| A | tp_lockout | peak_time_min | 253 | 0.54 | -27.8 | -92.4 to 36.8 |
| A | meal_window_max_peak | peak_time_min | 221 | 0.55 | -29.0 | -92.2 to 34.3 |
| A | refractory | peak_time_min | 232 | 0.54 | -28.4 | -92.7 to 35.9 |
| A | baseline_return | peak_time_min | 241 | 0.54 | -28.2 | -92.7 to 36.2 |
| B | tp_lockout | recovery_time_min | 542 | 0.64 | 12.0 | -57.3 to 81.2 |
| B | meal_window_max_peak | recovery_time_min | 441 | 0.61 | 10.7 | -59.9 to 81.4 |
| B | refractory | recovery_time_min | 486 | 0.61 | 11.0 | -62.6 to 84.5 |
| B | baseline_return | recovery_time_min | 500 | 0.61 | 12.3 | -59.5 to 84.1 |
| B | tp_lockout | peak_height | 542 | 0.94 | 1.4 | -30.5 to 33.2 |
| B | meal_window_max_peak | peak_height | 441 | 0.95 | 0.0 | -28.7 to 28.8 |
| B | refractory | peak_height | 486 | 0.93 | -0.1 | -33.7 to 33.4 |
| B | baseline_return | peak_height | 500 | 0.94 | 1.1 | -28.1 to 30.3 |
| B | tp_lockout | iauc | 542 | 0.94 | 353.1 | -3639.8 to 4345.9 |
| B | meal_window_max_peak | iauc | 441 | 0.95 | 167.3 | -3258.8 to 3593.4 |
| B | refractory | iauc | 486 | 0.92 | 169.1 | -4147.0 to 4485.2 |
| B | baseline_return | iauc | 500 | 0.94 | 321.2 | -3380.0 to 4022.5 |
| B | tp_lockout | peak_time_min | 542 | 0.59 | -26.2 | -90.8 to 38.4 |
| B | meal_window_max_peak | peak_time_min | 441 | 0.55 | -27.2 | -93.5 to 39.1 |
| B | refractory | peak_time_min | 486 | 0.54 | -29.3 | -97.1 to 38.4 |
| B | baseline_return | peak_time_min | 500 | 0.57 | -27.7 | -93.6 to 38.1 |

### e) Detection counts at the locked parameters

| Route | Rule | Raw | Removed by rule | Removed inside scoring window | Ignored by TP lockout | Kept and scored (TP + FP) |
|---|---|---|---|---|---|---|
| A | tp_lockout | 1028 | 0 | 0 | 125 | 320 |
| A | meal_window_max_peak | 932 | 525 | 159 | 0 | 257 |
| A | refractory | 985 | 334 | 143 | 0 | 290 |
| A | baseline_return | 967 | 257 | 106 | 0 | 315 |
| B | tp_lockout | 2463 | 0 | 0 | 300 | 724 |
| B | meal_window_max_peak | 2097 | 1257 | 370 | 0 | 513 |
| B | refractory | 2181 | 784 | 309 | 0 | 604 |
| B | baseline_return | 2229 | 665 | 265 | 0 | 668 |

### f) Locked parameters and forced grid edges

| Rule | Route | Set | tau_F | G_min | G'_min,3 | G'_min,2 | Forced edges |
|---|---|---|---|---|---|---|---|
| tp_lockout | A | mean +/- SD (42) | 4.52 +/- 0.99 | 104.40 +/- 10.49 | 0.86 +/- 0.15 | 0.95 +/- 0.24 | Gp_min_2 20/42, tau_F 19/42, G_min 12/42, Gp_min_3 4/42 |
| tp_lockout | B | fold_0 | 4.0 | 100.0 | 0.8 | 0.8 | tau_F, G_min, Gp_min_2 |
| tp_lockout | B | fold_1 | 4.0 | 100.0 | 0.8 | 0.8 | tau_F, G_min, Gp_min_2 |
| tp_lockout | B | fold_2 | 4.0 | 100.0 | 0.8 | 0.8 | tau_F, G_min, Gp_min_2 |
| tp_lockout | B | fold_3 | 4.0 | 100.0 | 0.8 | 0.8 | tau_F, G_min, Gp_min_2 |
| tp_lockout | B | fold_4 | 4.0 | 100.0 | 0.8 | 0.8 | tau_F, G_min, Gp_min_2 |
| tp_lockout | B | all_participants | 4.0 | 100.0 | 0.8 | 0.8 | tau_F, G_min, Gp_min_2 |
| meal_window_max_peak | A | mean +/- SD (42) | 4.69 +/- 1.20 | 103.93 +/- 10.51 | 0.88 +/- 0.18 | 1.09 +/- 0.35 | Gp_min_2 15/42, tau_F 15/42, G_min 10/42, Gp_min_3 6/42 |
| meal_window_max_peak | B | fold_0 | 4.0 | 105.0 | 0.8 | 1.3 | tau_F, Gp_min_3 |
| meal_window_max_peak | B | fold_1 | 7.0 | 105.0 | 0.8 | 0.8 | Gp_min_2 |
| meal_window_max_peak | B | fold_2 | 5.0 | 105.0 | 0.8 | 0.8 | Gp_min_2 |
| meal_window_max_peak | B | fold_3 | 5.0 | 105.0 | 0.8 | 0.8 | Gp_min_2 |
| meal_window_max_peak | B | fold_4 | 5.0 | 105.0 | 0.8 | 0.8 | Gp_min_2 |
| meal_window_max_peak | B | all_participants | 5.0 | 105.0 | 0.8 | 0.8 | Gp_min_2 |
| refractory | A | mean +/- SD (42) | 4.62 +/- 1.15 | 105.36 +/- 11.17 | 0.86 +/- 0.16 | 0.98 +/- 0.25 | tau_F 20/42, Gp_min_2 18/42, G_min 10/42, Gp_min_3 6/42 |
| refractory | B | fold_0 | 5.0 | 100.0 | 0.8 | 0.8 | G_min, Gp_min_2 |
| refractory | B | fold_1 | 7.0 | 105.0 | 0.8 | 0.8 | Gp_min_2 |
| refractory | B | fold_2 | 5.0 | 100.0 | 0.8 | 0.8 | G_min, Gp_min_2 |
| refractory | B | fold_3 | 6.0 | 100.0 | 0.8 | 0.8 | G_min, Gp_min_2 |
| refractory | B | fold_4 | 6.0 | 100.0 | 0.8 | 0.8 | G_min, Gp_min_2 |
| refractory | B | all_participants | 5.0 | 100.0 | 0.8 | 0.8 | G_min, Gp_min_2 |
| baseline_return | A | mean +/- SD (42) | 4.55 +/- 1.11 | 106.79 +/- 12.14 | 0.87 +/- 0.16 | 1.00 +/- 0.27 | tau_F 16/42, Gp_min_2 12/42, G_min 10/42, Gp_min_3 5/42 |
| baseline_return | B | fold_0 | 5.0 | 100.0 | 0.8 | 0.8 | G_min, Gp_min_2 |
| baseline_return | B | fold_1 | 7.0 | 105.0 | 0.8 | 0.8 | Gp_min_2 |
| baseline_return | B | fold_2 | 5.0 | 105.0 | 0.8 | 0.8 | Gp_min_2 |
| baseline_return | B | fold_3 | 4.0 | 100.0 | 0.8 | 0.8 | tau_F, G_min, Gp_min_2 |
| baseline_return | B | fold_4 | 6.0 | 100.0 | 0.8 | 0.8 | G_min, Gp_min_2 |
| baseline_return | B | all_participants | 5.0 | 100.0 | 0.8 | 0.8 | G_min, Gp_min_2 |

### g) baseline_return: merging by group

| Route | Group | Raw detections | % merged | Events | % censored at 180 min | % fallback baseline |
|---|---|---|---|---|---|---|
| A | overall | 967 | 26.6 | 710 | 32.1 | 0.0 |
| A | healthy | 349 | 20.3 | 278 | 22.3 | 0.0 |
| A | prediabetes | 300 | 26.3 | 221 | 31.2 | 0.0 |
| A | T2D | 318 | 33.6 | 211 | 46.0 | 0.0 |
| B | overall | 2229 | 29.8 | 1564 | 32.8 | 0.0 |
| B | healthy | 760 | 23.4 | 582 | 23.9 | 0.0 |
| B | prediabetes | 692 | 27.7 | 500 | 31.6 | 0.0 |
| B | T2D | 777 | 38.0 | 482 | 44.8 | 0.0 |

## Reading notes

- Route B sensitivity: tp_lockout 82.1 %, baseline_return 75.8 %, refractory 73.6 %, meal_window_max_peak 66.8 %. FP/day: 0.55, 0.51, 0.36, 0.22.
- Recovery-time ICC is similar across rules: 0.58 to 0.61 in Route A and 0.61 to 0.64 in Route B.
- Route B sensitivity range across groups: 1.3 pp (meal_window_max_peak) to 7.2 pp (refractory); baseline_return 4.7 pp.
- baseline_return merges more in T2D than in healthy (Route B: 38.0 % vs 23.4 %) and censors more events (44.8 % vs 23.9 %).
- The fallback baseline was never used (0.0 % of events).
