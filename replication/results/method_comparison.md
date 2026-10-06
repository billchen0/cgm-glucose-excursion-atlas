# Method comparison (standard protocol)

One row per method. Protocol protocol_v1: main adjacent rule refractory, Route B, our matching rule (-30 to +120 min), test data (5 held-out folds pooled). CIs and all other rules are in each method README.

| Method | Sens % | Prec % | F2 | FP/day | Delay median (min) | Sens range (pp) | Recovery-time ICC |
|---|---|---|---|---|---|---|---|
| [Dassau 2-of-3](../methods/dassau/results/dassau_2of3/protocol_v1/README.md) | 74.4 | 72.4 | 0.740 | 0.56 | 20 | 5.5 | 0.70 |
| [Dassau 3-of-4](../methods/dassau/results/dassau_3of4/protocol_v1/README.md) | 71.7 | 82.7 | 0.736 | 0.30 | 24 | 8.8 | 0.70 |
| [Faccioli STMD](../methods/faccioli/results/protocol_v1/README.md) | 77.7 | 69.1 | 0.758 | 0.69 | 30 | 6.7 | 0.71 |
| [Harvey GRID](../methods/harvey/results/protocol_v1/README.md) | 73.6 | 80.5 | 0.749 | 0.36 | 29 | 7.2 | 0.72 |
| [Lim wavelet PPGR](../methods/lim/results/protocol_v1/README.md) | 67.9 | 89.2 | 0.713 | 0.16 | 25 | 1.2 | 0.67 |
| [Popp SBE](../methods/popp/results/protocol_v1/README.md) | 63.8 | 69.8 | 0.649 | 0.55 | 43 | 32.2 | 0.61 |
| [Samadi IGT](../methods/samadi/results/protocol_v1/README.md) | 87.4 | 55.9 | 0.786 | 1.37 | 25 | 6.2 | 0.66 |
| [Turksoy UKF](../methods/turksoy/results/protocol_v1/README.md) | 53.5 | 89.1 | 0.581 | 0.13 | 38 | 8.6 | 0.70 |

Sens range = max minus min sensitivity across healthy, prediabetes and T2D. Recovery-time ICC = ICC(A,1), detector vs logged-meal anchor, excursion segmentation.

Run dates: dassau_2of3 2026-10-05; dassau_3of4 2026-10-05; faccioli 2026-10-05; harvey 2026-10-05; lim 2026-10-06; popp 2026-10-05; samadi 2026-10-05; turksoy 2026-10-05.

Notes:

- Lim wavelet PPGR: Lim is window-limited (one detection per breakfast and lunch window, at most 2 per day), so its FP/day is not comparable with the all-day detectors.

With 95 % CIs, the comparison with Hochsmann 2026, grid boundary hits and findings: `docs/results_summary.md`.

Rebuilt by `common/run_protocol.py` at the end of every method run.
