# Results summary

All methods under the standard protocol on CGMacros: 42 participants, 332 scored days, breakfast and lunch as ground truth. Route B (5 participant folds, test data pooled). 95 % participant-bootstrap CIs in brackets. Built by `common/make_results_summary.py` from the saved outputs; the per-method READMEs have the details.

## Main results

Main adjacent rule (refractory), our matching rule (-30 to +120 min). Sorted by F2. Sens range = max minus min across healthy, prediabetes and T2D. Recovery-time ICC = ICC(A,1), detector vs logged-meal anchor. Lim is window-limited (at most 2 detections per day), so its FP/day is not comparable with the all-day detectors.

| Method | Sens % | Prec % | F2 | FP/day | Delay median (min) | Sens range (pp) | Recovery-time ICC |
|---|---|---|---|---|---|---|---|
| [Samadi IGT](../methods/samadi/results/protocol_v1/README.md) | 87.4 [84.0, 90.8] | 55.9 [53.3, 58.7] | 0.786 [0.756, 0.815] | 1.37 [1.24, 1.49] | 25 [22, 28] | 6.2 | 0.66 |
| [Faccioli STMD](../methods/faccioli/results/protocol_v1/README.md) | 77.7 [73.6, 81.9] | 69.1 [64.8, 73.6] | 0.758 [0.721, 0.798] | 0.69 [0.57, 0.82] | 30 [28, 33] | 6.7 | 0.71 |
| [Harvey GRID](../methods/harvey/results/protocol_v1/README.md) | 73.6 [69.7, 77.3] | 80.5 [76.2, 84.9] | 0.749 [0.714, 0.782] | 0.36 [0.27, 0.45] | 29 [27, 32] | 7.2 | 0.72 |
| [Dassau 2-of-3](../methods/dassau/results/dassau_2of3/protocol_v1/README.md) | 74.4 [69.5, 78.9] | 72.4 [68.3, 76.5] | 0.740 [0.700, 0.778] | 0.56 [0.46, 0.68] | 20 [18, 23] | 5.5 | 0.70 |
| [Dassau 3-of-4](../methods/dassau/results/dassau_3of4/protocol_v1/README.md) | 71.7 [67.5, 75.5] | 82.7 [78.1, 87.3] | 0.736 [0.701, 0.770] | 0.30 [0.21, 0.40] | 24 [21, 27] | 8.8 | 0.70 |
| [Lim wavelet PPGR](../methods/lim/results/protocol_v1/README.md) | 67.9 [62.8, 72.8] | 89.2 [85.3, 92.6] | 0.713 [0.664, 0.759] | 0.16 [0.11, 0.22] | 25 [20, 30] | 1.2 | 0.67 |
| [Popp SBE](../methods/popp/results/protocol_v1/README.md) | 63.8 [57.1, 70.1] | 69.8 [64.3, 75.0] | 0.649 [0.588, 0.706] | 0.55 [0.43, 0.68] | 43 [39, 47] | 32.2 | 0.61 |
| [Turksoy UKF](../methods/turksoy/results/protocol_v1/README.md) | 53.5 [49.4, 57.4] | 89.1 [84.3, 93.6] | 0.581 [0.541, 0.620] | 0.13 [0.07, 0.19] | 38 [35, 41] | 8.6 | 0.70 |

## Comparison with Hochsmann 2026 Table 2 (not like-for-like)

tp_lockout with the review matching rule (0 to +120 min), Route B, test data, vs Hochsmann 2026 Table 2 (16 healthy young adults, Libre 2, three meals a day, afternoon detections suppressed, per-participant or global tuning). Cohort, sensor, scored meals, scoring window and tuning all differ. Delay is the mean, as in Table 2. Difference = ours minus Hochsmann (pp).

| Method | Sens % ours | Sens % Hochsmann | Difference (pp) | FP/day ours | FP/day Hochsmann | Delay ours | Delay Hochsmann |
|---|---|---|---|---|---|---|---|
| Dassau 2-of-3 | 81.4 | 72.2 | +9.2 | 0.90 | 0.60 | 29.2 | 37.6 |
| Dassau 3-of-4 | 73.9 | 49.1 | +24.8 | 0.47 | 0.12 | 31.6 | 36.8 |
| Faccioli STMD | 88.0 | 64.4 | +23.6 | 1.07 | 1.39 | 36.0 | 39.6 |
| Harvey GRID | 80.6 | 70.4 | +10.2 | 0.64 | 0.26 | 35.7 | 37.3 |
| Popp SBE | 65.5 | 82.9 | -17.4 | 1.00 | 1.28 | 49.9 | 60.5 |
| Samadi IGT | 89.8 | 89.8 | +0.0 | 1.84 | 2.42 | 29.5 | 58.5 |
| Turksoy UKF | 55.1 | 76.9 | -21.8 | 0.19 | 0.22 | 42.1 | 40.7 |

## Grid boundary hits and main deviations

Boundary hits: Route B sets (5 folds and all_participants, refractory) whose value lies on the lower or upper grid bound.

| Method | Boundary hits | Main deviations | File |
|---|---|---|---|
| Samadi IGT | yes: gamma1 low 6/6 | Simplified rule as in the review; membership functions are defaults (Samadi 2017 not available). | [deviations](../methods/samadi/docs/deviations.md) |
| Faccioli STMD | yes: Th_Res low 5/6, Th_Der high 5/6, L low 1/6 | Observer bound L tuned on the grid, added after the first result (night gain rule gave Sens about 20 %). | [deviations](../methods/faccioli/docs/deviations.md) |
| Harvey GRID | yes: G_min low 5/6, G'_min,3 low 6/6, G'_min,2 low 6/6 | Native 5-min Dexcom; rising-edge events; grid as Hochsmann. | [deviations](../methods/harvey/docs/deviations.md) |
| Dassau 2-of-3 | yes: Threshold_ROC low 5/6, Threshold_Acceleration low 4/6 | Eq. 5 as written (Threshold_ROC and Threshold_Acceleration only, unlike Table 1); Kalman settings are defaults. | [deviations](../methods/dassau/docs/deviations.md) |
| Dassau 3-of-4 | yes: Threshold_Glucose low 6/6, Threshold_maxROC high 1/6, Threshold_ROC low 6/6 | Eq. 6 as written; same Kalman defaults; detection at t(i), available 4 min later. | [deviations](../methods/dassau/docs/deviations.md) |
| Lim wavelet PPGR | fixed, not tuned | Appendices A-C missing: smoothing, wavelet scale and tie-break are defaults; breakfast and lunch windows only. | [deviations](../methods/lim/docs/deviations.md) |
| Popp SBE | yes: phi low 6/6, epsilon high 6/6 | Dalla Man 2007 model from BioModels; anchoring of the no-meal simulation is a default. | [deviations](../methods/popp/docs/deviations.md) |
| Turksoy UKF | yes: Threshold_Ra low 6/6 | Original model has no insulin input; trimming bounds, 120-min warm-up and sigma-point clipping are defaults. | [deviations](../methods/turksoy/docs/deviations.md) |

## Findings

- The five best methods by F2 lie within 0.05 of each other: Samadi 0.786, Faccioli 0.758, Harvey 0.749, Dassau 2-of-3 0.740, Dassau 3-of-4 0.736. Lim follows at 0.713, Popp 0.649, Turksoy 0.581.
- Sensitivity and precision trade off. Samadi has the highest Sens (87.4 %) but the lowest Prec (55.9 %) and the most FP/day (1.37). Turksoy and Lim have the highest Prec (about 89 %) at Sens 53.5 % and 67.9 %.
- Lim is the most even across groups (Sens range 1.2 pp; it is window-limited, at most 2 detections per day). Popp is the least even: T2D Sens 44.5 % vs 76.8 % in healthy (range 32.2 pp).
- Recovery-time ICC(A,1) between detector and logged-meal anchors ranges from 0.61 (Popp) to 0.72 (Harvey).
- In all seven tuned methods at least one selected parameter sits on a grid bound (table above), mostly the permissive one (Faccioli's Th_Der is on the strict bound), so a better operating point may lie outside the published grids. Faccioli's observer bound L was added to the grid after the first result.
- Turksoy is limited by a weak R_a response: only 59 % of meals push the estimated R_a above 1.5 mg/dL/min, the lowest threshold, within 120 min.

Excluded: Pellizzari 2025 TMA (needs training; common/docs/deviations.md Z6).
