# Dassau 2-of-3 and 3-of-4 on CGMacros

Dassau 2008 meal detection, as specified in the Hochsmann 2026 review (Supplementary Table 1,
Eqs. 1-6). The original paper is not available, so the review equations are the only spec.
Two registered detectors share one indicator module and one config. Both run through the
standard protocol (common/docs/deviations.md section Z).

## Results

| Detector | README | Route B, refractory (main): Sens / Prec / FP/day |
|---|---|---|
| dassau_2of3 | `results/dassau_2of3/protocol_v1/README.md` | 74.4 % / 72.4 % / 0.56 |
| dassau_3of4 | `results/dassau_3of4/protocol_v1/README.md` | 71.7 % / 82.7 % / 0.30 |

- Cross-method table: `results/method_comparison.md` (repo root).
- Spot check of the indicators around each detection: `results/spot_check.md`.
- Deviations (equations as printed, Table 1 mismatch, Kalman defaults, findings): `docs/deviations.md`.

## Layout

| Path | Content |
|---|---|
| `src/dassau.py` | Shared code: indicators BD, BDK, KF, ACC (Eqs. 1-4), votes (Eqs. 5-6), `detect`, vectorised `detect_grid`. |
| `src/dassau_2of3.py`, `src/dassau_3of4.py` | The two registered detectors (thin wrappers). |
| `common/evaluation/kalman.py` | Constant-acceleration Kalman filter (shared, reusable by Faccioli). |
| `configs/dassau.toml` | Kalman defaults `[kalman.dassau]`, grids, README metadata. |
| `docs/deviations.md` | D1-D12 and findings. |
| `tests/test_dassau.py` | Synthetic cases and detect_grid vs detect. |
| `src/spot_check.py` | Writes `results/spot_check.md`. |

## Run (from `replication/`)

```
python methods/dassau/tests/test_dassau.py
python common/run_protocol.py dassau_2of3
python common/run_protocol.py dassau_3of4
python methods/dassau/src/spot_check.py
```

- The runs take about 35 s (2-of-3) and 60 s (3-of-4). They are deterministic (a second run gave identical files).
- Row-level tables and the standard exports are regenerated and not committed.
