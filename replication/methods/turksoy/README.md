# Turksoy (UKF on a modified minimal model) on CGMacros

Turksoy 2016 meal detector, with the Hochsmann 2026 review rule (Supplementary Table 1, Eq. 16).
An unscented Kalman filter estimates the rate of glucose appearance R_a from CGM alone. The model
and UKF settings come from Turksoy 2016 (published IEEE version). Run through the standard
protocol (common/docs/deviations.md section Z).

## Results

Route B, refractory (main), our matching rule: Sens 53.5 %, Prec 89.1 %, F2 0.581, FP/day 0.13.

- Full results: `results/protocol_v1/README.md`.
- Sens is low because R_a reacts weakly: only 59 % of meals push R_a above 1.5 mg/dL/min, the lowest threshold. Every Route B set picks that lower bound.
- Cross-method table: `results/method_comparison.md` (repo root). Spot check: `results/spot_check.md`.
- Deviations (Eq. 16 and the model as printed, insulin handling, UKF defaults, findings): `docs/deviations.md`.

Hochsmann 2026 Table 1 (per participant, their cohort): Threshold_Ra = 1.56 +/- 0.09.
Original (via Kolle, T1D): Sens 97 / 64 %, FP/day 1.28, delay 32.7 min.

## Layout

| Path | Content |
|---|---|
| `src/turksoy.py` | Model (Eqs. 4-8), UKF (Eqs. 10-22), Eq. 16, `detect`, `detect_grid`. |
| `configs/turksoy.toml` | Grid, UKF settings (stated and default), README metadata. |
| `docs/deviations.md` | T1-T15 and findings. |
| `tests/test_turksoy.py` | Synthetic cases, stability on real days, detect_grid vs detect. |
| `src/spot_check.py` | Writes `results/spot_check.md`. |

## Run (from `replication/`)

```
python methods/turksoy/tests/test_turksoy.py
python common/run_protocol.py turksoy
python methods/turksoy/src/spot_check.py
```

- The protocol run takes about 40 s and is deterministic (a second run gave identical files).
- Row-level tables and the standard exports are regenerated and not committed.
