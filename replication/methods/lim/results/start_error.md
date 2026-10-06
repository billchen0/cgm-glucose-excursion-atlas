# Lim: start-time error and out-of-window meals

## Meals logged outside their window (10 mg/dL run)

Route B, scored breakfast and lunch meals (refractory, our matching rule). Breakfast window 06:00-11:45, lunch 12:00-16:00 (meal start time).

| Meal | Scored meals | Outside window | % | FN among them | All FN |
|---|---|---|---|---|---|
| all | 660 | 115 | 17.4 | 79 | 212 |
| breakfast | 328 | 20 | 6.1 | 19 | 65 |
| lunch | 332 | 95 | 28.6 | 60 | 147 |

## Start-time error, 10 mg/dL (main run)

Median [IQR] absolute error (min) between PPGR start and logged meal start. TP: TP detections (match within -30 to +120 min). Lim-style: every scored meal logged inside its window, paired with the PPGR of that window on the same day (any status). Lim 2026 on CGMacros (Dexcom): breakfast 14 [6, 29], lunch 36 [19, 63]; Hall breakfast 10 [4, 19].

| Meal | Group | TP error | TP n | Lim-style error | Lim-style n | % with a PPGR |
|---|---|---|---|---|---|---|
| breakfast | all | 16 [7, 31] | 263 | 18 [8, 37] | 301 | 97.7 |
| breakfast | healthy | 13 [6, 23] | 93 | 13 [6, 25] | 102 | 93.6 |
| breakfast | prediabetes | 18 [7, 47] | 74 | 22 [8, 58] | 89 | 100.0 |
| breakfast | T2D | 19 [8, 35] | 96 | 22 [8, 38] | 110 | 100.0 |
| lunch | all | 40 [26, 62] | 185 | 44 [26, 77] | 178 | 75.1 |
| lunch | healthy | 30 [19, 46] | 68 | 33 [20, 72] | 75 | 71.4 |
| lunch | prediabetes | 43 [28, 66] | 65 | 52 [29, 93] | 53 | 85.5 |
| lunch | T2D | 48 [40, 62] | 52 | 55 [40, 82] | 50 | 71.4 |
| all | all | 25 [10, 47] | 448 | 26 [11, 55] | 479 | 87.9 |
| all | healthy | 20 [8, 36] | 161 | 21 [9, 40] | 177 | 82.7 |
| all | prediabetes | 30 [12, 60] | 139 | 30 [12, 70] | 142 | 94.0 |
| all | T2D | 30 [12, 48] | 148 | 30 [12, 54] | 160 | 88.9 |

## Start-time error by threshold (all groups)

Same definitions. Lim reports no Sens or FP/day; its sensitivity analysis compared PPGR parameters.

| Min height | Meal | TP error | TP n | Lim-style error | Lim-style n | % with a PPGR |
|---|---|---|---|---|---|---|
| 10 | breakfast | 16 [7, 31] | 263 | 18 [8, 37] | 301 | 97.7 |
| 10 | lunch | 40 [26, 62] | 185 | 44 [26, 77] | 178 | 75.1 |
| 10 | all | 25 [10, 47] | 448 | 26 [11, 55] | 479 | 87.9 |
| 20 | breakfast | 16 [6, 29] | 255 | 17 [7, 34] | 289 | 93.8 |
| 20 | lunch | 39 [24, 54] | 151 | 40 [23, 68] | 143 | 60.3 |
| 20 | all | 23 [9, 41] | 406 | 23 [9, 46] | 432 | 79.3 |
| 30 | breakfast | 15 [6, 30] | 233 | 16 [7, 34] | 262 | 85.1 |
| 30 | lunch | 38 [23, 48] | 123 | 40 [23, 61] | 117 | 49.4 |
| 30 | all | 22 [8, 40] | 356 | 22 [9, 43] | 379 | 69.5 |
