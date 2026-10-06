# Lim (wavelet PPGR identification) on CGMacros

Lim 2026 wavelet algorithm, in its original design: one PPGR per clock meal window, breakfast
(06:00-11:45) and lunch (12:00-16:00) only. Fixed parameters, not tuned. Appendices A-C of the
paper are not in the PDF, so the smoothing, wavelet and tie-break details are defaults. Run through
the standard protocol (common/docs/deviations.md section Z).

## Results

Route B, refractory (main), our matching rule:

| Min height | Sens % | Prec % | F2 | FP/day | README |
|---|---|---|---|---|---|
| 10 mg/dL (main) | 67.9 | 89.2 | 0.713 | 0.16 | `results/protocol_v1/README.md` |
| 20 mg/dL | 61.5 | 90.6 | 0.657 | 0.13 | `results/protocol_v1_h20/README.md` |
| 30 mg/dL | 53.9 | 90.8 | 0.587 | 0.11 | `results/protocol_v1_h30/README.md` |

- Window-limited: at most 2 detections per day, so FP/day is not comparable with the all-day detectors.
- The adjacent rules change nothing (refractory and tp_lockout give identical results).
- Start-time error vs Lim's own CGMacros numbers, and meals logged outside their window: `results/start_error.md`.
- Spot check (candidates, chosen PPGR, wavelet coefficient): `results/spot_check.md`.
- Deviations (missing appendices, defaults, findings): `docs/deviations.md`.

## Layout

| Path | Content |
|---|---|
| `src/lim.py` | Smoothing, wavelet transform, candidate segments, choice per window, `detect`, `detect_grid`, `detection_extras`. |
| `configs/lim.toml` | Windows, smoothing and wavelet settings, fixed threshold, README metadata. |
| `docs/deviations.md` | L1-L10 and findings. |
| `tests/test_lim.py` | Synthetic cases and detect_grid vs detect. |
| `src/run_sensitivity.py` | The 20 and 30 mg/dL runs. |
| `src/start_error.py` | Writes `results/start_error.md` and `.csv`. |
| `src/spot_check.py` | Writes `results/spot_check.md`. |

## Run (from `replication/`)

```
python methods/lim/tests/test_lim.py
python common/run_protocol.py lim
python methods/lim/src/run_sensitivity.py
python methods/lim/src/start_error.py
python methods/lim/src/spot_check.py
```

- The main run takes about 20 s, the two sensitivity runs about 35 s. They are deterministic (a second run gave identical files).
- Row-level tables and the standard exports are regenerated and not committed.
