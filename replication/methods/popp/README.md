# Popp (simulation-based meal detection) on CGMacros

Popp 2024 simulation-based explanation (SBE, after Zheng 2019), with the Hochsmann 2026 review rule
(Supplementary Table 1, Eqs. 11-13). The glucose model is the Dalla Man 2007 meal model with
normal-subject population parameters; insulin is endogenous only. Run through the standard protocol
(common/docs/deviations.md section Z).

## Results

Route B, refractory (main), our matching rule: Sens 63.8 %, Prec 69.8 %, F2 0.649, FP/day 0.55.

- Full results: `results/protocol_v1/README.md`.
- The estimated meal start m_st is a median 16 min after the logged start; the detection follows a median 33 min later. See `results/spot_check.md`.
- Sens differs a lot by group: healthy 76.8 %, prediabetes 69.5 %, T2D 44.5 %.
- Cross-method table: `results/method_comparison.md` (repo root).
- Deviations (Eqs. 11-13 as printed, model source and parameters, anchoring, findings): `docs/deviations.md`.

Hochsmann 2026 Table 1 (global, their cohort): phi = 0.10, tau = 20 min, epsilon = 18 mg/dL.
Popp 2024 did not report sensitivity, FP/day or delay.

## Layout

| Path | Content |
|---|---|
| `src/popp.py` | Dalla Man 2007 model, Div (Eq. 11), back-search, meal fit (Eq. 12), rule (Eq. 13), `detect`, `detect_grid`, `detection_extras` (m_st). |
| `configs/popp.toml` | Grid, loads, meal duration, README metadata. |
| `docs/deviations.md` | P1-P13 and findings. |
| `tests/test_popp.py` | Model checks, synthetic cases, timing, detect_grid vs detect. |
| `src/spot_check.py` | Writes `results/spot_check.md` (with the m_st delay table). |

## Run (from `replication/`)

```
python methods/popp/tests/test_popp.py
python common/run_protocol.py popp
python methods/popp/src/spot_check.py
```

- The protocol run takes about 70 s and is deterministic (a second run gave identical files, apart from the run date).
- Row-level tables and the standard exports are regenerated and not committed.
