# Faccioli (super-twisting meal detector) on CGMacros

Faccioli 2022 super-twisting meal detector (STMD), with the Hochsmann 2026 review rule
(Supplementary Table 1, Eq. 7) and its 3-point median filter. The observer, Kalman filter and
gain rule come from Faccioli 2022. The detector is CGM only. Run through the standard protocol
(common/docs/deviations.md section Z).

## Results

| Run | Gain L | Route B, refractory (main): Sens / Prec / FP/day | README |
|---|---|---|---|
| main | global grid parameter, tuned on Route B | 77.7 % / 69.1 % / 0.69 | `results/protocol_v1/README.md` |
| first run, superseded | per day, max disturbance over the night (Faccioli's first-night rule) | 20.3 % / 88.7 % / 0.05 | `results/protocol_v1_nightgain/README.md` |

- The first run is the faithful label-free gain rule. It does not transfer to this cohort: the night bound is too large for the meal disturbances, so few meals pass the residual threshold.
- The grid gain was added after seeing that result (user decision, 2026-10-05). Its L grid was fixed before the second run.
- Cross-method table: `results/method_comparison.md` (repo root). Spot check: `results/spot_check.md`.
- Deviations (Eq. 7 as printed, observer derivation, gain rules, findings): `docs/deviations.md`.

Hochsmann 2026 Table 1 (per participant, their cohort): Th_Der = 0.23 +/- 0.11, Th_Res = 1.25 +/- 0.54.
Faccioli 2022 (30 T1D adults, 180-min TP window): recall 70 %, precision 73 %, FP/day 1.4, detection time 45 min (medians).

## Layout

| Path | Content |
|---|---|
| `src/faccioli.py` | Median filter, implicit super-twisting observer, gain rules, Eq. 7, `detect`, `detect_grid`. |
| `common/evaluation/kalman.py` | `filter_faccioli`: Faccioli's three-state Kalman filter (shared module). |
| `configs/faccioli.toml` | Grids (including L), observer and Kalman settings, README metadata. |
| `docs/deviations.md` | F1-F12, the first run, findings. |
| `tests/test_faccioli.py` | Synthetic cases, observer equation, gain rule, detect_grid vs detect. |
| `src/run_nightgain.py` | Reproduces the first run (night gain rule). |
| `src/spot_check.py` | Writes `results/spot_check.md`. |

## Run (from `replication/`)

```
python methods/faccioli/tests/test_faccioli.py
python common/run_protocol.py faccioli
python methods/faccioli/src/run_nightgain.py
python methods/faccioli/src/spot_check.py
```

- Each protocol run takes about 25 s and is deterministic (a second run gave identical files).
- Row-level tables and the standard exports are regenerated and not committed.
