# Harvey (GRID) on CGMacros: results

Run: `python methods/harvey/src/run_harvey.py` (about 25 s, deterministic, seed 20260929).
Rules: docs/evaluation_plan_v3.md and `common/configs/cgmacros_eval.toml`.
Deviations and defaults: `common/docs/deviations.md` (framework) and `methods/harvey/docs/deviations.md` (Harvey).

**Cohort:** Dexcom only, 42 participants (15 healthy, 13 prediabetes, 14 T2D) with at least
7 valid days: 333 days and 666 breakfast/lunch meals.
- 660 meals are scored. 6 are not:
  - 4 breakfasts logged 04:23 to 04:57 (E3);
  - both meals of CGMacros-043 on 2025-10-22, whose only "lunch" is logged at 02:17 (breakfast 08:03), so the day has no scoring window (E16).
- 332 days have a scoring window.
- Route A: 165 validation and 168 test days. Route B: 5 folds over the participants.

**Rules:** "ours" scores a detection as TP from 30 min before to 120 min after the logged start. "review" uses 0 to 120 min after. Everything else is identical, including the tuning.

**`Harvey2014_fixed`:** Harvey 2014's published population parameters (tau_F 6, G_min 130, G'_min,3 1.5, G'_min,2 1.6), untuned, on all days. It is shown for reference only.

## Files

| File | Content |
|---|---|
| `summary.csv`, `summary_routeA.csv`, `summary_routeB.csv` | Detection metrics with 95 % participant-bootstrap CI. Strata: overall, group, meal. Both rules. |
| `params/chosen_params_route{A,B}_{ours,review}.json` | Locked parameters. Route A per participant, Route B per fold plus `all_participants`. Also validation F2/FP/day/delay, the number of tied grid points, `grid_edges`, and `grid_edges_forced` (edges shared by every tied grid point). |
| `recovery_agreement.csv` | ICC(A,1) and Bland-Altman bias / 95 % LoA per feature and stratum. |
| `plots/bland_altman_route{A,B}_{rule}.png` | Bland-Altman plots, 4 features. |
| `sample_sizes.csv`, `splits.csv` | Counts, Route A day split, Route B folds. |
| `detections.csv`, `meals.csv`, `recovery_features.csv` | Row-level tables (not committed, regenerate with the command above). Per detection: participant, day, time, status (TP / FP / lockout / not_scored), matched meal, delay, FP near a logged snack or dinner. Per meal: status and delay. Per TP pair: detector and reference features. |

## Detection (test data; 95 % CI)

Route A = per-participant test days (half of each participant's days).
Route B = all days of each held-out fold, pooled over 5 folds.
FP/day uses scored days.

| Route | Rule | Stratum | n (pp/days) | TP | FP | FN | Sens % | Prec % | F2 | FP/day | FP/h | Delay median | Delay mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | ours | overall | 42/167 | 253 | 67 | 80 | 76.0 [70.7, 81.3] | 79.1 [75.3, 83.1] | 0.766 [0.721, 0.812] | 0.40 [0.31, 0.49] | 0.046 [0.035, 0.056] | 27 [25, 30] | 32.6 [27.5, 38.3] |
| A | ours | healthy | 15/60 | 84 | 23 | 36 | 70.0 [60.0, 80.0] | 78.5 [73.2, 84.4] | 0.716 [0.626, 0.799] | 0.38 [0.25, 0.52] | 0.042 [0.027, 0.058] | 25 [23, 29] | 29.4 [24.8, 34.5] |
| A | ours | prediabetes | 13/51 | 80 | 21 | 21 | 79.2 [69.9, 86.5] | 79.2 [71.4, 87.9] | 0.792 [0.719, 0.855] | 0.41 [0.22, 0.63] | 0.049 [0.026, 0.074] | 28 [24, 38] | 34.8 [23.9, 48.7] |
| A | ours | T2D | 14/56 | 89 | 23 | 23 | 79.5 [73.2, 85.7] | 79.5 [73.3, 86.8] | 0.795 [0.736, 0.854] | 0.41 [0.25, 0.55] | 0.047 [0.028, 0.065] | 28 [24, 33] | 33.6 [25.8, 43.4] |
| A | review | overall | 42/167 | 249 | 75 | 84 | 74.8 [69.3, 80.2] | 76.8 [72.4, 81.8] | 0.752 [0.706, 0.798] | 0.45 [0.33, 0.57] | 0.051 [0.037, 0.065] | 28 [26, 32] | 35.9 [31.0, 41.8] |
| A | review | healthy | 15/60 | 83 | 30 | 37 | 69.2 [59.2, 80.0] | 73.5 [65.9, 81.5] | 0.700 [0.611, 0.789] | 0.50 [0.32, 0.70] | 0.055 [0.034, 0.079] | 26 [25, 31] | 32.7 [28.9, 37.2] |
| A | review | prediabetes | 13/51 | 78 | 23 | 23 | 77.2 [68.3, 84.7] | 77.2 [68.3, 88.1] | 0.772 [0.702, 0.835] | 0.45 [0.20, 0.73] | 0.054 [0.024, 0.085] | 30 [26, 43] | 39.2 [28.3, 54.4] |
| A | review | T2D | 14/56 | 88 | 22 | 24 | 78.6 [72.3, 84.8] | 80.0 [73.4, 87.4] | 0.788 [0.727, 0.850] | 0.39 [0.23, 0.55] | 0.045 [0.026, 0.065] | 29 [24, 33] | 36.1 [28.5, 45.8] |
| B | ours | overall | 42/332 | 542 | 182 | 118 | 82.1 [78.6, 85.3] | 74.9 [69.2, 80.4] | 0.806 [0.775, 0.836] | 0.55 [0.40, 0.72] | 0.063 [0.045, 0.083] | 27 [24, 29] | 31.0 [26.8, 35.9] |
| B | ours | healthy | 15/119 | 194 | 69 | 43 | 81.9 [75.8, 87.9] | 73.8 [61.9, 84.5] | 0.801 [0.741, 0.858] | 0.58 [0.30, 0.97] | 0.063 [0.033, 0.107] | 25 [23, 27] | 27.2 [22.7, 31.2] |
| B | ours | prediabetes | 13/103 | 160 | 37 | 43 | 78.8 [70.3, 84.7] | 81.2 [75.0, 88.0] | 0.793 [0.721, 0.845] | 0.36 [0.21, 0.51] | 0.043 [0.026, 0.062] | 29 [24, 38] | 34.4 [25.0, 47.2] |
| B | ours | T2D | 14/110 | 188 | 76 | 32 | 85.5 [82.4, 88.3] | 71.2 [62.7, 80.0] | 0.822 [0.792, 0.849] | 0.69 [0.42, 1.02] | 0.079 [0.048, 0.116] | 27 [21, 31] | 32.1 [25.2, 41.1] |
| B | review | overall | 42/332 | 532 | 214 | 128 | 80.6 [76.9, 83.9] | 71.3 [65.5, 77.0] | 0.786 [0.754, 0.817] | 0.64 [0.48, 0.84] | 0.074 [0.054, 0.096] | 28 [26, 30] | 35.7 [31.4, 40.9] |
| B | review | healthy | 15/119 | 190 | 83 | 47 | 80.2 [74.3, 86.4] | 69.6 [57.4, 81.5] | 0.778 [0.717, 0.839] | 0.70 [0.37, 1.15] | 0.076 [0.040, 0.126] | 26 [25, 28] | 31.6 [28.9, 34.4] |
| B | review | prediabetes | 13/103 | 158 | 46 | 45 | 77.8 [69.3, 84.0] | 77.5 [70.8, 84.9] | 0.778 [0.706, 0.829] | 0.45 [0.27, 0.63] | 0.054 [0.033, 0.076] | 30 [27, 41] | 39.6 [30.2, 52.8] |
| B | review | T2D | 14/110 | 184 | 85 | 36 | 83.6 [80.3, 86.9] | 68.4 [59.8, 77.5] | 0.801 [0.762, 0.834] | 0.77 [0.48, 1.12] | 0.088 [0.055, 0.128] | 28 [22, 34] | 36.7 [29.3, 46.7] |
| Harvey2014_fixed | ours | overall | 42/332 | 329 | 37 | 331 | 49.9 [42.8, 56.5] | 89.9 [85.1, 94.3] | 0.547 [0.477, 0.611] | 0.11 [0.06, 0.17] | 0.013 [0.007, 0.019] | 33 [31, 37] | 38.0 [33.2, 44.0] |
| Harvey2014_fixed | review | overall | 42/332 | 323 | 46 | 337 | 48.9 [42.0, 55.3] | 87.5 [82.7, 92.0] | 0.537 [0.468, 0.597] | 0.14 [0.08, 0.20] | 0.016 [0.009, 0.023] | 34 [31, 38] | 39.4 [34.8, 45.1] |

By meal (FP cannot be assigned to a meal, E11):

| Route | Rule | Meal | TP | FN | Sens % | Delay median |
|---|---|---|---|---|---|---|
| A | ours | breakfast | 143 | 23 | 86.1 [79.2, 92.8] | 23 [22, 25] |
| A | ours | lunch | 110 | 57 | 65.9 [58.7, 73.0] | 35 [33, 39] |
| A | review | breakfast | 143 | 23 | 86.1 [79.2, 92.8] | 24 [23, 26] |
| A | review | lunch | 106 | 61 | 63.5 [56.0, 71.1] | 36 [33, 40] |
| B | ours | breakfast | 294 | 34 | 89.6 [82.8, 95.5] | 23 [20, 24] |
| B | ours | lunch | 248 | 84 | 74.7 [70.5, 79.2] | 33 [30, 36] |
| B | review | breakfast | 294 | 34 | 89.6 [82.8, 95.5] | 23 [21, 25] |
| B | review | lunch | 238 | 94 | 71.7 [66.8, 76.6] | 35 [33, 38] |

**For comparison, the review's Harvey test set** (Hochsmann 2026 Table 2; 16 healthy young adults, Libre 2, 3 meals/day, afternoon suppression): sensitivity 70.4 %, FP/day 0.26, delta t 37.3 min (mean). This is not a like-for-like comparison: different cohort, sensor, meals and scoring window.

## Parameters

| Route / rule | tau_F | G_min | G'_min,3 | G'_min,2 | Validation F2 |
|---|---|---|---|---|---|
| Review, per participant (Table 1) | 4.5 +/- 1.2 | 103.1 +/- 5.1 | 0.8 +/- 0.1 | 1.1 +/- 0.1 | 0.84 +/- 0.13 |
| A, ours (mean +/- SD over 42) | 4.52 +/- 0.99 | 104.4 +/- 10.5 | 0.86 +/- 0.15 | 0.95 +/- 0.24 | 0.85 +/- 0.11 |
| A, review | 4.52 +/- 0.86 | 106.1 +/- 12.6 | 0.87 +/- 0.16 | 0.96 +/- 0.24 | 0.83 +/- 0.11 |
| B, ours and review (all 5 folds and all-data) | 4 | 100 | 0.8 | 0.8 | 0.78 to 0.82 |

**Grid edges**
- **Route B:** every fold, and the all-data set, lands on the permissive corner of the review grid. tau_F, G_min and G'_min,2 are forced edges: every tied point shares them. G'_min,3 is not identifiable there. When G'_min,2 <= G'_min,3, the 3-ROC branch is implied by the 2-ROC branch, so all 11 values of G'_min,3 tie, and grid order picks 0.8 (H11).
- **Route A:** all 42 participants have at least one parameter on an edge. Most of these come from the tie-break, because 3 to 4 validation days leave a median of 28 tied grid points and grid order picks the lowest values.
  - Forced edges ("ours"): G'_min,2 20/42, tau_F 19/42, G_min 12/42, G'_min,3 4/42 (30 participants with at least one).
  - Forced edges ("review"): 18, 16, 10 and 2 (26 participants).
  - Upper edges are rare (tau_F 2, G_min 2 for "ours").

## Recovery features (PROVISIONAL segmentation, E9), TP pairs, overall

| Route | Rule | Feature | n | ICC(A,1) | BA bias (det - ref) | 95 % LoA |
|---|---|---|---|---|---|---|
| A | ours | peak time (min) | 253 | 0.54 | -27.8 | -92.4 to 36.8 |
| A | ours | peak height (mg/dL) | 253 | 0.95 | 0.6 | -30.2 to 31.5 |
| A | ours | iAUC (mg/dL*min) | 253 | 0.95 | 290 | -3598 to 4178 |
| A | ours | recovery time (min) | 253 | 0.60 | 13.8 | -59.5 to 87.2 |
| B | ours | peak time (min) | 542 | 0.59 | -26.2 | -90.8 to 38.4 |
| B | ours | peak height (mg/dL) | 542 | 0.94 | 1.4 | -30.5 to 33.2 |
| B | ours | iAUC (mg/dL*min) | 542 | 0.94 | 353 | -3640 to 4346 |
| B | ours | recovery time (min) | 542 | 0.64 | 12.0 | -57.3 to 81.2 |

Review-rule rows and the group/meal strata are in `recovery_agreement.csv`. Reading notes:
- Peak time is measured from each anchor, so its bias is about minus the detection delay by construction.
- Glucose does not return to the pre-anchor baseline within 180 min for about 52 % of reference windows and about 40 % of detector windows. Recovery time is often cap-censored.
- All TP pairs had complete data and were featurised.

## Other observations

- The -30 min early tolerance ("ours") adds few TPs: +4 in Route A, +10 in Route B. 14 (A) and 45 (B) TPs fire before the logged start. Lower FP comes mainly from those detections no longer counting as FP.
- Lunch is harder than breakfast in every route: about 20 pp lower sensitivity and about 12 min longer delay.
- Repeated detections after a TP are frequent: 125 (A) and 300 (B) detections were ignored under the 120-min lockout. Without the lockout they would be FPs.
- 6 to 9 % of FPs lie within [-60, +120] min of a logged snack or dinner (not masked, E5).
