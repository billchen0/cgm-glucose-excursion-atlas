# Samadi (fuzzy-logic IGT) on CGMacros

Samadi 2018 increase-of-glucose-trend (IGT) detector, with the simplified rule of the
Hochsmann 2026 review (Supplementary Table 1, Eqs. 14-15). Shapes and weights come from Samadi
2018 Fig. 2. The membership functions are defaults: Samadi 2017, which defines them, is not
available. Run through the standard protocol (common/docs/deviations.md section Z).

## Results

Route B, refractory (main), our matching rule: Sens 87.4 %, Prec 55.9 %, F2 0.786, FP/day 1.37.

- Full results: `results/protocol_v1/README.md`.
- Cross-method table: `results/method_comparison.md` (repo root).
- Spot check (d1G, d2G, memberships, IGT around each detection): `results/spot_check.md`.
- Deviations (equations as printed, membership defaults, findings): `docs/deviations.md`.

Hochsmann 2026 Table 1 (tuned per participant, their cohort): gamma1 = 1 +/- 1, Threshold_act = 1.33 +/- 0.49.

## Layout

| Path | Content |
|---|---|
| `src/samadi.py` | Quadratic fit, memberships, IGT (Eq. 14), rule (Eq. 15), `detect`, `detect_grid`. |
| `configs/samadi.toml` | Grid, fixed settings, README metadata. |
| `docs/deviations.md` | S1-S11 and findings. |
| `tests/test_samadi.py` | Synthetic cases, IGT range, detect_grid vs detect. |
| `src/spot_check.py` | Writes `results/spot_check.md`. |

## Run (from `replication/`)

```
python methods/samadi/tests/test_samadi.py
python common/run_protocol.py samadi
python methods/samadi/src/spot_check.py
```

- The protocol run takes about 20 s and is deterministic (a second run gave identical files).
- Row-level tables and the standard exports are regenerated and not committed.
