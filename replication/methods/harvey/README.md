# Harvey (GRID) on CGMacros

Harvey 2014 Glucose Rate Increase Detector, implemented as in the Hochsmann 2026 review
(Supplementary Table 1, Eq. 8). It is evaluated with the shared framework in `common/evaluation/`,
under docs/evaluation_plan_v3.md.

## Rule roles (2026-10-05)

Decisions: common/docs/deviations.md, section Z.

| Rule | Needs meal log? | Role |
|---|---|---|
| refractory (120 min) | no | main (Z1) |
| tp_lockout (Hochsmann 2026) | yes | comparison only (Z2) |
| excursion_end | no | record only, not run for new methods (Z3) |
| baseline_return | no | record only (Z3) |
| meal_window_max_peak | no | record only (Z3) |

- Standard results: `results/protocol_v1/` (Route B only, excursion segmentation). See its README.
- Route A results and the other rules stay in the earlier folders as a record.
- The rule check in `results/rule_check/` favoured excursion_end. The main rule was then set to refractory by decision (Z1).

## Layout

| Path | Content |
|---|---|
| `src/harvey.py` | Detector: `detect`, the vectorised `detect_grid`, and `fixed_params`. |
| `configs/harvey.toml` | Grid, method settings and README metadata (`[methods.harvey.about]`). Merged over `common/configs/cgmacros_eval.toml`. |
| `docs/deviations.md` | Harvey-specific deviations (H1-H11). Framework entries are in `common/docs/deviations.md`. |
| `results/protocol_v1/` | Standard protocol: refractory (main) and tp_lockout (comparison, ours and review), Route B. |
| `src/check_protocol_v1.py` | Check that protocol_v1 equals excursion_v2 (Route B, refractory and tp_lockout). |
| `results/reference_tp_lockout/` | Record. Route A and B with the 120-min TP lockout, our and the review matching rule. |
| `results/peak_rules/` | Record. baseline_return, meal_window_max_peak and refractory, provisional segmentation. |
| `results/excursion_v2/` | Record. All rules with the shared excursion definition, Route A and B. |
| `results/rule_check/` | Record. excursion_end vs refractory check (section Y). |
| `results/standard/` | Standard-format export of the earlier runs (`src/export_standard.py`). |
| `src/run_harvey.py`, `src/run_harvey_peak_rules.py`, `src/run_harvey_excursion_v2.py`, `src/run_rule_check.py` | Runners of the record folders. They use the shared `common/evaluation/protocol.run_method`. |

## Run (from `replication/`)

Standard protocol (about 35 s):

```
python common/run_protocol.py harvey
python methods/harvey/src/check_protocol_v1.py
```

Record folders, in this order:

```
python methods/harvey/src/run_harvey.py
python methods/harvey/src/run_harvey_peak_rules.py
python methods/harvey/src/run_harvey_excursion_v2.py
python methods/harvey/src/run_rule_check.py
python methods/harvey/src/export_standard.py
```

- Each later runner reads the outputs of the earlier ones.
- Row-level tables (`detections.csv`, `meals.csv`, `recovery_features.csv`) and the standard exports are regenerated and not committed.
