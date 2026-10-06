## a) Overall detection

| Route | Rule | TP | FP | FN | Sens % | Prec % | F2 | FP/day | Delay median | Delay mean |
|---|---|---|---|---|---|---|---|---|---|---|
| A | tp_lockout | 253 | 67 | 80 | 76.0 [70.7, 81.3] | 79.1 [75.3, 83.1] | 0.766 [0.721, 0.812] | 0.40 [0.31, 0.49] | 27 [25, 30] | 32.6 [27.5, 38.3] |
| A | meal_window_max_peak | 221 | 36 | 112 | 66.4 [60.1, 72.8] | 86.0 [81.0, 91.2] | 0.695 [0.637, 0.756] | 0.22 [0.14, 0.29] | 28 [26, 31] | 33.0 [28.2, 38.5] |
| A | refractory | 232 | 58 | 101 | 69.7 [63.5, 75.5] | 80.0 [75.9, 84.5] | 0.715 [0.661, 0.768] | 0.35 [0.26, 0.43] | 28 [26, 31] | 33.5 [28.9, 38.9] |
| A | excursion_end | 241 | 77 | 92 | 72.4 [67.3, 77.7] | 75.8 [70.4, 81.1] | 0.730 [0.685, 0.775] | 0.46 [0.33, 0.61] | 28 [26, 31] | 33.4 [28.8, 39.0] |
| B | tp_lockout | 542 | 182 | 118 | 82.1 [78.6, 85.3] | 74.9 [69.2, 80.4] | 0.806 [0.775, 0.836] | 0.55 [0.40, 0.72] | 27 [24, 29] | 31.0 [26.8, 35.9] |
| B | meal_window_max_peak | 441 | 72 | 219 | 66.8 [62.1, 71.0] | 86.0 [81.8, 89.9] | 0.699 [0.656, 0.739] | 0.22 [0.15, 0.29] | 28 [26, 31] | 33.5 [28.9, 38.9] |
| B | refractory | 486 | 118 | 174 | 73.6 [69.7, 77.3] | 80.5 [76.2, 84.9] | 0.749 [0.714, 0.782] | 0.36 [0.27, 0.45] | 29 [27, 32] | 35.7 [31.3, 40.9] |
| B | excursion_end | 511 | 204 | 149 | 77.4 [73.6, 80.7] | 71.5 [66.0, 77.2] | 0.761 [0.729, 0.792] | 0.61 [0.46, 0.79] | 28 [26, 30] | 33.7 [29.4, 38.7] |

## b) By glycaemic group

| Route | Rule | Sens % healthy | Sens % prediabetes | Sens % T2D | Sens range (pp) | Prec % healthy | Prec % prediabetes | Prec % T2D | FP/day healthy | FP/day prediabetes | FP/day T2D |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | tp_lockout | 70.0 [60.0, 80.0] | 79.2 [69.9, 86.5] | 79.5 [73.2, 85.7] | 9.5 | 78.5 [73.2, 84.4] | 79.2 [71.4, 87.9] | 79.5 [73.3, 86.8] | 0.38 [0.25, 0.52] | 0.41 [0.22, 0.63] | 0.41 [0.25, 0.55] |
| A | meal_window_max_peak | 61.7 [49.2, 73.3] | 68.3 [58.4, 78.0] | 69.6 [60.7, 77.7] | 8.0 | 80.4 [70.3, 88.9] | 88.5 [79.0, 97.3] | 89.7 [82.2, 96.4] | 0.30 [0.17, 0.43] | 0.18 [0.04, 0.33] | 0.16 [0.05, 0.29] |
| A | refractory | 61.7 [50.0, 73.3] | 73.3 [62.7, 82.5] | 75.0 [67.9, 82.1] | 13.3 | 76.3 [67.7, 84.4] | 82.2 [76.0, 89.8] | 81.5 [74.1, 89.5] | 0.38 [0.25, 0.53] | 0.31 [0.16, 0.47] | 0.34 [0.18, 0.50] |
| A | excursion_end | 68.3 [59.2, 77.5] | 73.3 [62.1, 83.0] | 75.9 [69.6, 82.1] | 7.6 | 68.9 [61.3, 78.0] | 82.2 [71.2, 94.0] | 78.0 [69.2, 86.0] | 0.62 [0.37, 0.88] | 0.31 [0.08, 0.60] | 0.43 [0.25, 0.64] |
| B | tp_lockout | 81.9 [75.8, 87.9] | 78.8 [70.3, 84.7] | 85.5 [82.4, 88.3] | 6.6 | 73.8 [61.9, 84.5] | 81.2 [75.0, 88.0] | 71.2 [62.7, 80.0] | 0.58 [0.30, 0.97] | 0.36 [0.21, 0.51] | 0.69 [0.42, 1.02] |
| B | meal_window_max_peak | 66.2 [59.2, 73.7] | 67.5 [58.1, 75.0] | 66.8 [59.2, 74.1] | 1.3 | 84.9 [77.3, 91.8] | 90.1 [84.0, 95.4] | 83.5 [75.6, 90.6] | 0.24 [0.12, 0.37] | 0.15 [0.07, 0.24] | 0.26 [0.15, 0.41] |
| B | refractory | 70.0 [63.7, 76.7] | 73.9 [64.4, 81.2] | 77.3 [73.0, 80.9] | 7.2 | 80.2 [71.4, 88.8] | 84.8 [79.1, 90.5] | 77.3 [70.8, 84.3] | 0.34 [0.18, 0.54] | 0.26 [0.16, 0.38] | 0.45 [0.28, 0.64] |
| B | excursion_end | 74.3 [69.1, 79.8] | 77.3 [67.8, 84.2] | 80.9 [77.5, 84.1] | 6.7 | 64.9 [54.7, 76.1] | 77.0 [68.9, 85.4] | 74.2 [66.3, 82.3] | 0.80 [0.47, 1.23] | 0.46 [0.26, 0.70] | 0.56 [0.35, 0.82] |

## c) By meal

| Route | Rule | Sens % breakfast | Delay median breakfast | Sens % lunch | Delay median lunch |
|---|---|---|---|---|---|
| A | tp_lockout | 86.1 [79.2, 92.8] | 23 [22, 25] | 65.9 [58.7, 73.0] | 35 [33, 39] |
| A | meal_window_max_peak | 75.9 [68.1, 83.8] | 24 [22, 26] | 56.9 [48.8, 65.5] | 36 [32, 40] |
| A | refractory | 77.7 [70.1, 85.0] | 23 [22, 25] | 61.7 [53.6, 69.6] | 36 [34, 41] |
| A | excursion_end | 83.1 [76.2, 89.8] | 24 [23, 27] | 61.7 [54.2, 69.5] | 35 [33, 39] |
| B | tp_lockout | 89.6 [82.8, 95.5] | 23 [20, 24] | 74.7 [70.5, 79.2] | 33 [30, 36] |
| B | meal_window_max_peak | 76.2 [68.6, 83.1] | 24 [22, 26] | 57.5 [51.8, 63.1] | 35 [33, 39] |
| B | refractory | 80.2 [72.8, 86.8] | 24 [22, 26] | 67.2 [62.5, 71.8] | 36 [34, 39] |
| B | excursion_end | 84.8 [77.6, 90.9] | 24 [22, 25] | 70.2 [65.6, 74.6] | 35 [33, 38] |

## d) Recovery-feature agreement, new excursion definition vs provisional (TP pairs, overall)

Recovery time (new) leaves out pairs where either anchor is no_rise; see the exclusion table below.

| Route | Rule | Feature | n new | ICC new | Bias new | 95 % LoA new | n provisional | ICC provisional | Bias provisional | 95 % LoA provisional |
|---|---|---|---|---|---|---|---|---|---|---|
| A | tp_lockout | recovery_time_min | 248 | 0.77 | 11.7 | -32.4 to 55.8 | 253 | 0.60 | 13.8 | -59.5 to 87.2 |
| A | meal_window_max_peak | recovery_time_min | 219 | 0.78 | 10.8 | -33.7 to 55.4 | 221 | 0.58 | 11.1 | -65.5 to 87.7 |
| A | refractory | recovery_time_min | 227 | 0.78 | 12.0 | -31.3 to 55.4 | 232 | 0.61 | 14.2 | -58.0 to 86.5 |
| A | excursion_end | recovery_time_min | 237 | 0.79 | 11.0 | -32.2 to 54.1 | 241 | 0.61 | 12.0 | -60.3 to 84.4 |
| A | tp_lockout | peak_height | 253 | 0.93 | 5.0 | -31.4 to 41.4 | 253 | 0.95 | 0.6 | -30.2 to 31.5 |
| A | meal_window_max_peak | peak_height | 221 | 0.93 | 5.0 | -30.8 to 40.8 | 221 | 0.96 | -1.4 | -30.1 to 27.3 |
| A | refractory | peak_height | 232 | 0.92 | 6.2 | -31.9 to 44.3 | 232 | 0.95 | 0.7 | -30.3 to 31.7 |
| A | excursion_end | peak_height | 241 | 0.93 | 4.9 | -31.3 to 41.0 | 241 | 0.95 | -0.1 | -30.1 to 29.9 |
| A | tp_lockout | iauc | 253 | 0.95 | 654.4 | -3449.7 to 4758.5 | 253 | 0.95 | 290.0 | -3597.9 to 4177.9 |
| A | meal_window_max_peak | iauc | 221 | 0.95 | 644.5 | -3271.4 to 4560.4 | 221 | 0.95 | 83.6 | -3807.9 to 3975.0 |
| A | refractory | iauc | 232 | 0.94 | 785.8 | -3264.5 to 4836.1 | 232 | 0.94 | 303.3 | -3582.4 to 4189.1 |
| A | excursion_end | iauc | 241 | 0.95 | 617.1 | -3314.0 to 4548.1 | 241 | 0.95 | 204.5 | -3578.5 to 3987.6 |
| A | tp_lockout | peak_time_min | 253 | 0.56 | -24.7 | -79.7 to 30.2 | 253 | 0.54 | -27.8 | -92.4 to 36.8 |
| A | meal_window_max_peak | peak_time_min | 221 | 0.56 | -26.1 | -79.9 to 27.8 | 221 | 0.55 | -29.0 | -92.2 to 34.3 |
| A | refractory | peak_time_min | 232 | 0.55 | -24.5 | -80.3 to 31.4 | 232 | 0.54 | -28.4 | -92.7 to 35.9 |
| A | excursion_end | peak_time_min | 241 | 0.58 | -25.9 | -76.0 to 24.1 | 241 | 0.55 | -28.2 | -91.2 to 34.8 |
| B | tp_lockout | recovery_time_min | 532 | 0.75 | 10.9 | -37.4 to 59.3 | 542 | 0.64 | 12.0 | -57.3 to 81.2 |
| B | meal_window_max_peak | recovery_time_min | 436 | 0.75 | 10.8 | -37.6 to 59.3 | 441 | 0.61 | 10.7 | -59.9 to 81.4 |
| B | refractory | recovery_time_min | 478 | 0.72 | 11.5 | -40.2 to 63.3 | 486 | 0.61 | 11.0 | -62.6 to 84.5 |
| B | excursion_end | recovery_time_min | 503 | 0.74 | 11.5 | -37.6 to 60.6 | 511 | 0.63 | 11.9 | -58.1 to 81.9 |
| B | tp_lockout | peak_height | 542 | 0.91 | 5.0 | -32.9 to 42.8 | 542 | 0.94 | 1.4 | -30.5 to 33.2 |
| B | meal_window_max_peak | peak_height | 441 | 0.92 | 5.2 | -31.3 to 41.7 | 441 | 0.95 | 0.0 | -28.7 to 28.8 |
| B | refractory | peak_height | 486 | 0.90 | 5.1 | -34.5 to 44.6 | 486 | 0.93 | -0.1 | -33.7 to 33.4 |
| B | excursion_end | peak_height | 511 | 0.91 | 5.2 | -32.0 to 42.4 | 511 | 0.94 | 0.9 | -28.2 to 30.0 |
| B | tp_lockout | iauc | 542 | 0.93 | 527.4 | -3884.8 to 4939.5 | 542 | 0.94 | 353.1 | -3639.8 to 4345.9 |
| B | meal_window_max_peak | iauc | 441 | 0.95 | 547.4 | -3203.9 to 4298.6 | 441 | 0.95 | 167.3 | -3258.8 to 3593.4 |
| B | refractory | iauc | 486 | 0.92 | 527.7 | -4068.9 to 5124.2 | 486 | 0.92 | 169.1 | -4147.0 to 4485.2 |
| B | excursion_end | iauc | 511 | 0.94 | 592.1 | -3436.8 to 4621.0 | 511 | 0.94 | 292.2 | -3397.2 to 3981.6 |
| B | tp_lockout | peak_time_min | 542 | 0.54 | -25.1 | -83.6 to 33.5 | 542 | 0.59 | -26.2 | -90.8 to 38.4 |
| B | meal_window_max_peak | peak_time_min | 441 | 0.55 | -26.0 | -81.6 to 29.6 | 441 | 0.55 | -27.2 | -93.5 to 39.1 |
| B | refractory | peak_time_min | 486 | 0.52 | -26.9 | -87.2 to 33.3 | 486 | 0.54 | -29.3 | -97.1 to 38.4 |
| B | excursion_end | peak_time_min | 511 | 0.54 | -25.7 | -83.6 to 32.3 | 511 | 0.58 | -27.9 | -91.9 to 36.2 |

Pairs left out of the new recovery-time ICC (no_rise at either anchor):

| Route | Rule | TP pairs | no_rise det | no_rise ref | Excluded (either) | Used |
|---|---|---|---|---|---|---|
| A | tp_lockout | 253 | 0 | 5 | 5 | 248 |
| A | meal_window_max_peak | 221 | 0 | 2 | 2 | 219 |
| A | refractory | 232 | 0 | 5 | 5 | 227 |
| A | excursion_end | 241 | 0 | 4 | 4 | 237 |
| B | tp_lockout | 542 | 0 | 10 | 10 | 532 |
| B | meal_window_max_peak | 441 | 0 | 5 | 5 | 436 |
| B | refractory | 486 | 0 | 8 | 8 | 478 |
| B | excursion_end | 511 | 0 | 8 | 8 | 503 |

## e) End type by group (TP pairs; det = detector anchor, ref = logged meal start)

| Route | Rule | Anchor | Group | n | % returned | % trough | % trough_interrupted | % censored | % no_rise |
|---|---|---|---|---|---|---|---|---|---|
| A | tp_lockout | det | overall | 253 | 62.1 | 13.0 | 5.1 | 19.8 | 0.0 |
| A | tp_lockout | det | healthy | 84 | 73.8 | 14.3 | 4.8 | 7.1 | 0.0 |
| A | tp_lockout | det | prediabetes | 80 | 58.8 | 11.2 | 8.8 | 21.2 | 0.0 |
| A | tp_lockout | det | T2D | 89 | 53.9 | 13.5 | 2.2 | 30.3 | 0.0 |
| A | tp_lockout | ref | overall | 253 | 55.3 | 13.4 | 0.4 | 28.9 | 2.0 |
| A | tp_lockout | ref | healthy | 84 | 66.7 | 19.0 | 1.2 | 11.9 | 1.2 |
| A | tp_lockout | ref | prediabetes | 80 | 52.5 | 10.0 | 0.0 | 36.2 | 1.2 |
| A | tp_lockout | ref | T2D | 89 | 47.2 | 11.2 | 0.0 | 38.2 | 3.4 |
| A | meal_window_max_peak | det | overall | 221 | 62.9 | 13.6 | 3.6 | 19.9 | 0.0 |
| A | meal_window_max_peak | det | healthy | 74 | 75.7 | 10.8 | 4.1 | 9.5 | 0.0 |
| A | meal_window_max_peak | det | prediabetes | 69 | 59.4 | 17.4 | 4.3 | 18.8 | 0.0 |
| A | meal_window_max_peak | det | T2D | 78 | 53.8 | 12.8 | 2.6 | 30.8 | 0.0 |
| A | meal_window_max_peak | ref | overall | 221 | 55.7 | 13.1 | 0.5 | 29.9 | 0.9 |
| A | meal_window_max_peak | ref | healthy | 74 | 68.9 | 16.2 | 1.4 | 13.5 | 0.0 |
| A | meal_window_max_peak | ref | prediabetes | 69 | 52.2 | 11.6 | 0.0 | 36.2 | 0.0 |
| A | meal_window_max_peak | ref | T2D | 78 | 46.2 | 11.5 | 0.0 | 39.7 | 2.6 |
| A | refractory | det | overall | 232 | 62.1 | 13.4 | 5.2 | 19.4 | 0.0 |
| A | refractory | det | healthy | 74 | 75.7 | 13.5 | 4.1 | 6.8 | 0.0 |
| A | refractory | det | prediabetes | 74 | 59.5 | 12.2 | 9.5 | 18.9 | 0.0 |
| A | refractory | det | T2D | 84 | 52.4 | 14.3 | 2.4 | 31.0 | 0.0 |
| A | refractory | ref | overall | 232 | 55.6 | 12.9 | 0.4 | 28.9 | 2.2 |
| A | refractory | ref | healthy | 74 | 68.9 | 17.6 | 1.4 | 10.8 | 1.4 |
| A | refractory | ref | prediabetes | 74 | 51.4 | 10.8 | 0.0 | 36.5 | 1.4 |
| A | refractory | ref | T2D | 84 | 47.6 | 10.7 | 0.0 | 38.1 | 3.6 |
| A | excursion_end | det | overall | 241 | 62.2 | 15.4 | 3.7 | 18.7 | 0.0 |
| A | excursion_end | det | healthy | 82 | 74.4 | 15.9 | 2.4 | 7.3 | 0.0 |
| A | excursion_end | det | prediabetes | 74 | 59.5 | 16.2 | 6.8 | 17.6 | 0.0 |
| A | excursion_end | det | T2D | 85 | 52.9 | 14.1 | 2.4 | 30.6 | 0.0 |
| A | excursion_end | ref | overall | 241 | 55.2 | 13.7 | 0.8 | 28.6 | 1.7 |
| A | excursion_end | ref | healthy | 82 | 67.1 | 19.5 | 1.2 | 11.0 | 1.2 |
| A | excursion_end | ref | prediabetes | 74 | 51.4 | 9.5 | 1.4 | 36.5 | 1.4 |
| A | excursion_end | ref | T2D | 85 | 47.1 | 11.8 | 0.0 | 38.8 | 2.4 |
| B | tp_lockout | det | overall | 542 | 62.4 | 10.5 | 8.3 | 18.8 | 0.0 |
| B | tp_lockout | det | healthy | 194 | 72.7 | 10.3 | 7.7 | 9.3 | 0.0 |
| B | tp_lockout | det | prediabetes | 160 | 60.6 | 11.2 | 8.8 | 19.4 | 0.0 |
| B | tp_lockout | det | T2D | 188 | 53.2 | 10.1 | 8.5 | 28.2 | 0.0 |
| B | tp_lockout | ref | overall | 542 | 55.5 | 13.7 | 0.7 | 28.2 | 1.8 |
| B | tp_lockout | ref | healthy | 194 | 66.0 | 16.0 | 0.5 | 16.5 | 1.0 |
| B | tp_lockout | ref | prediabetes | 160 | 52.5 | 11.9 | 0.6 | 33.8 | 1.2 |
| B | tp_lockout | ref | T2D | 188 | 47.3 | 12.8 | 1.1 | 35.6 | 3.2 |
| B | meal_window_max_peak | det | overall | 441 | 61.0 | 13.6 | 6.3 | 19.0 | 0.0 |
| B | meal_window_max_peak | det | healthy | 157 | 70.1 | 12.7 | 6.4 | 10.8 | 0.0 |
| B | meal_window_max_peak | det | prediabetes | 137 | 61.3 | 13.9 | 6.6 | 18.2 | 0.0 |
| B | meal_window_max_peak | det | T2D | 147 | 51.0 | 14.3 | 6.1 | 28.6 | 0.0 |
| B | meal_window_max_peak | ref | overall | 441 | 54.9 | 13.6 | 0.7 | 29.7 | 1.1 |
| B | meal_window_max_peak | ref | healthy | 157 | 66.2 | 15.9 | 0.6 | 17.2 | 0.0 |
| B | meal_window_max_peak | ref | prediabetes | 137 | 51.1 | 11.7 | 0.0 | 36.5 | 0.7 |
| B | meal_window_max_peak | ref | T2D | 147 | 46.3 | 12.9 | 1.4 | 36.7 | 2.7 |
| B | refractory | det | overall | 486 | 61.3 | 13.8 | 6.6 | 18.3 | 0.0 |
| B | refractory | det | healthy | 166 | 72.3 | 12.7 | 7.2 | 7.8 | 0.0 |
| B | refractory | det | prediabetes | 150 | 61.3 | 13.3 | 6.0 | 19.3 | 0.0 |
| B | refractory | det | T2D | 170 | 50.6 | 15.3 | 6.5 | 27.6 | 0.0 |
| B | refractory | ref | overall | 486 | 54.5 | 14.0 | 0.8 | 29.0 | 1.6 |
| B | refractory | ref | healthy | 166 | 65.1 | 16.9 | 0.6 | 16.9 | 0.6 |
| B | refractory | ref | prediabetes | 150 | 52.7 | 12.0 | 0.7 | 33.3 | 1.3 |
| B | refractory | ref | T2D | 170 | 45.9 | 12.9 | 1.2 | 37.1 | 2.9 |
| B | excursion_end | det | overall | 511 | 62.4 | 12.9 | 6.3 | 18.4 | 0.0 |
| B | excursion_end | det | healthy | 176 | 72.7 | 13.1 | 5.7 | 8.5 | 0.0 |
| B | excursion_end | det | prediabetes | 157 | 61.1 | 12.1 | 7.6 | 19.1 | 0.0 |
| B | excursion_end | det | T2D | 178 | 53.4 | 13.5 | 5.6 | 27.5 | 0.0 |
| B | excursion_end | ref | overall | 511 | 55.4 | 14.1 | 0.8 | 28.2 | 1.6 |
| B | excursion_end | ref | healthy | 176 | 67.0 | 16.5 | 0.6 | 15.3 | 0.6 |
| B | excursion_end | ref | prediabetes | 157 | 52.2 | 12.1 | 0.6 | 33.8 | 1.3 |
| B | excursion_end | ref | T2D | 178 | 46.6 | 13.5 | 1.1 | 36.0 | 2.8 |

## f) Recovery time (min) by group and end type, excursion_end (median [IQR], n)

| Route | Anchor | Group | returned | trough | trough_interrupted | censored | no_rise |
|---|---|---|---|---|---|---|---|
| A | det | overall | 52 [25, 84], 150 | 45 [35, 65], 37 | 55 [55, 85], 9 | 100 [75, 125], 45 |  |
| A | det | healthy | 29 [18, 55], 61 | 44 [30, 65], 13 | 92 [74, 111], 2 | 102 [76, 129], 6 |  |
| A | det | prediabetes | 77 [38, 111], 44 | 40 [34, 56], 12 | 60 [55, 85], 5 | 115 [90, 135], 13 |  |
| A | det | T2D | 61 [37, 81], 45 | 55 [45, 76], 12 | 50 [48, 52], 2 | 100 [65, 115], 26 |  |
| A | ref | overall | 37 [20, 63], 133 | 45 [35, 60], 33 | 68 [54, 81], 2 | 86 [53, 100], 69 | 147 [118, 171], 4 |
| A | ref | healthy | 28 [17, 46], 55 | 45 [30, 65], 16 | 95 [95, 95], 1 | 92 [45, 117], 9 | 179 [179, 179], 1 |
| A | ref | prediabetes | 54 [21, 84], 38 | 35 [32, 58], 7 | 40 [40, 40], 1 | 91 [60, 102], 27 | 95 [95, 95], 1 |
| A | ref | T2D | 43 [28, 65], 40 | 50 [45, 55], 10 |  | 79 [50, 88], 33 | 147 [136, 158], 2 |
| B | det | overall | 49 [25, 79], 319 | 45 [35, 69], 66 | 55 [40, 78], 32 | 105 [75, 125], 94 |  |
| B | det | healthy | 37 [20, 62], 128 | 45 [32, 68], 23 | 50 [36, 68], 10 | 125 [78, 138], 15 |  |
| B | det | prediabetes | 61 [27, 104], 96 | 45 [35, 52], 19 | 60 [51, 88], 12 | 112 [79, 134], 30 |  |
| B | det | T2D | 58 [32, 80], 95 | 55 [40, 76], 24 | 48 [41, 70], 10 | 100 [65, 115], 49 |  |
| B | ref | overall | 36 [19, 61], 283 | 45 [33, 60], 72 | 58 [36, 80], 4 | 82 [52, 99], 144 | 174 [126, 179], 8 |
| B | ref | healthy | 29 [17, 50], 118 | 40 [30, 65], 29 | 95 [95, 95], 1 | 94 [68, 108], 27 | 179 [179, 179], 1 |
| B | ref | prediabetes | 42 [20, 76], 82 | 45 [32, 62], 19 | 40 [40, 40], 1 | 90 [52, 102], 53 | 137 [116, 158], 2 |
| B | ref | T2D | 43 [22, 63], 83 | 45 [35, 55], 24 | 50 [38, 62], 2 | 74 [49, 88], 64 | 168 [126, 179], 5 |

## g) excursion_end: merging by group

| Route | Group | Raw detections | % merged | Events |
|---|---|---|---|---|
| A | overall | 937 | 20.5 | 745 |
| A | healthy | 335 | 12.2 | 294 |
| A | prediabetes | 289 | 19.0 | 234 |
| A | T2D | 313 | 30.7 | 217 |
| B | overall | 2224 | 23.9 | 1693 |
| B | healthy | 755 | 16.3 | 632 |
| B | prediabetes | 692 | 21.7 | 542 |
| B | T2D | 777 | 33.2 | 519 |

## h) Detection counts and locked parameters

| Route | Rule | Raw | Removed by rule | Removed inside scoring window | Ignored by TP lockout | Kept and scored (TP + FP) |
|---|---|---|---|---|---|---|
| A | tp_lockout | 1028 | 0 | 0 | 125 | 320 |
| A | meal_window_max_peak | 932 | 525 | 159 | 0 | 257 |
| A | refractory | 985 | 334 | 143 | 0 | 290 |
| A | excursion_end | 937 | 192 | 91 | 0 | 318 |
| B | tp_lockout | 2463 | 0 | 0 | 300 | 724 |
| B | meal_window_max_peak | 2097 | 1257 | 370 | 0 | 513 |
| B | refractory | 2181 | 784 | 309 | 0 | 604 |
| B | excursion_end | 2224 | 531 | 217 | 0 | 715 |

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
| excursion_end | A | mean +/- SD (42) | 4.71 +/- 1.20 | 105.71 +/- 10.45 | 0.88 +/- 0.16 | 1.04 +/- 0.30 | tau_F 16/42, Gp_min_2 16/42, G_min 8/42, Gp_min_3 4/42 |
| excursion_end | B | fold_0 | 5.0 | 105.0 | 0.8 | 0.8 | Gp_min_2 |
| excursion_end | B | fold_1 | 7.0 | 105.0 | 0.8 | 0.8 | Gp_min_2 |
| excursion_end | B | fold_2 | 5.0 | 105.0 | 0.8 | 0.8 | Gp_min_2 |
| excursion_end | B | fold_3 | 4.0 | 100.0 | 0.8 | 0.8 | tau_F, G_min, Gp_min_2 |
| excursion_end | B | fold_4 | 6.0 | 100.0 | 0.8 | 0.8 | G_min, Gp_min_2 |
| excursion_end | B | all_participants | 5.0 | 105.0 | 0.8 | 0.8 | Gp_min_2 |
