# CGM meal-detection method replications on CGMacros

## Purpose

This repository replicates published CGM-only meal-detection methods on one dataset (CGMacros) with
one evaluation protocol, so they can be compared like for like. The aim is to choose a method, or a
starting point for a new one, that runs on CGM alone, without meal logs, insulin or diagnosis (as
needed for AI-READI).

## Data

- CGMacros (Das et al. 2025): Dexcom G6 Pro and Libre Pro CGM, meal logs with photos, 45 adults
  (healthy, prediabetes, type 2 diabetes). Only the Dexcom signal is used (native 5-min readings).
- The analysis cohort after QC is 42 participants with at least 7 valid days (333 days, 666
  breakfasts and lunches). Ground truth is breakfast and lunch only.
- The data are not in this repository.

## Setup

- Python 3.13 (tested with 3.13.5; at least 3.11 is needed for `tomllib`).
- Install the packages: `pip install -r requirements.txt` (numpy, pandas, scipy, scikit-learn,
  matplotlib, PyWavelets; exact versions of the environment used for all results).
- Get CGMacros from PhysioNet (https://doi.org/10.13026/3z8q-x658). The folder must contain
  `bio.csv` and one folder per participant (`CGMacros-001/CGMacros-001.csv`, ...).
- Tell the code where it is, in one of two ways:
  - set the environment variable `CGMACROS_DIR` to the CGMacros folder, or
  - edit `cgmacros_dir` in `common/configs/paths.toml`. A relative path is resolved from this
    repository's root; the default `../../CGMacros` points to a `CGMacros/` folder two levels up.
- Run all commands from this repository's root. Results are deterministic: a second run gives
  identical files.

## Standard protocol

The evaluation plan is `docs/evaluation_plan_v3.md`. Later decisions are logged in
`common/docs/deviations.md` (sections X, Y and Z). In short:

- Scoring window 07:00 to lunch start + 180 min on each valid day. A detection is a TP if it falls
  within -30 to +120 min of a logged breakfast or lunch start ("our" matching rule).
- Tuning: Route B only, one global parameter set per participant fold (5 folds, stratified by
  group), F2 objective; an all-participant set is also tuned as the candidate lock.
- Main adjacent-detection rule: refractory (a detection within 120 min after the previous kept one
  is dropped). tp_lockout (120-min lockout after each TP, Hochsmann 2026) is a comparison only,
  because it uses meal labels. It runs with our matching rule and the review rule (0 to +120 min).
- Recovery features use the frozen shared excursion definition (`common/evaluation/excursion.py`).
- Each method: detector module, config, tests, and a deviations file. Detector, grid and settings
  are committed before the first CGMacros run (`docs/prespecification_log.md`).

## Methods

| Method | Folder | Status |
|---|---|---|
| Harvey 2014 GRID | `methods/harvey/` | Done (standard protocol). Earlier exploratory runs kept. |
| Dassau 2008, 2-of-3 and 3-of-4 | `methods/dassau/` | Done (two detectors). |
| Samadi 2018 fuzzy IGT | `methods/samadi/` | Done. |
| Faccioli 2022 super-twisting | `methods/faccioli/` | Done (observer bound tuned on the grid; first run with the night gain rule kept). |
| Turksoy 2016 UKF | `methods/turksoy/` | Done. |
| Popp 2024 simulation-based | `methods/popp/` | Done. |
| Lim 2026 wavelet PPGR | `methods/lim/` | Done (breakfast and lunch windows; 20 and 30 mg/dL sensitivity runs). |
| Pellizzari 2025 TMA | `methods/pellizzari2025_tma/` | **Excluded**: needs training (templates and threshold learned from meal labels). Earlier results kept as a record; not in the method comparison (deviations Z6). |

Each method folder has a README with results, a `docs/deviations.md`, and tests.
Kolle 2020 (Kolle-Ra, Kolle-CGM) was excluded for the same reason as TMA (training), and
Archavli 2024 was not replicated.

## How to run

From the repository root:

| What | Command | Output |
|---|---|---|
| Cohort flow (QC) | `python common/qc/build_cohort_flow.py` | `common/results/cohort_flow/` |
| Standard protocol, one method | `python common/run_protocol.py <method>` | `methods/<folder>/results/.../protocol_v1/`, `results/method_comparison.md` |
| Rebuild READMEs only | `python common/run_protocol.py <method> --docs-only` | as above |
| Tests | `python methods/<folder>/tests/test_<name>.py`, `python common/evaluation/tests/test_excursion.py` | console |

Registered methods: harvey, dassau_2of3, dassau_3of4, samadi, faccioli, turksoy, popp, lim
(`common/evaluation/detectors.py`). A new method needs a detector module, a config under
`methods/<folder>/configs/` with `[methods.<name>]` and an about block, and a registry entry.

## Results

- Summary with 95 % CIs, the comparison with Hochsmann 2026, grid boundary hits and findings:
  `docs/results_summary.md` (rebuild with `python common/make_results_summary.py`).
- Cross-method table: `results/method_comparison.md` (Route B, refractory, our matching rule).
- Per method: `methods/<folder>/results/.../protocol_v1/README.md`.

## Result status

Nothing is deleted. Current results:

| Folder | What it is |
|---|---|
| `results/method_comparison.md` | Cross-method table (Route B, refractory, our matching rule). |
| `methods/<folder>/results/protocol_v1/` (Dassau: `results/dassau_2of3/protocol_v1/`, `results/dassau_3of4/protocol_v1/`) | Standard protocol run of each method: README, summaries, parameters, plots. |
| `methods/<folder>/results/spot_check.md`, `methods/lim/results/start_error.md` | Spot checks and the Lim start-time error, from the protocol_v1 outputs. |
| `common/results/cohort_flow/` | QC and cohort flow of the analysis cohort. |

Earlier or exploratory results, kept as a record:

| Folder | What it was for |
|---|---|
| `methods/harvey/results/reference_tp_lockout/` | First Harvey run: Route A and B, 120-min TP lockout, our and the review matching rule, provisional recovery features. |
| `methods/harvey/results/peak_rules/` | Label-free adjacent rules (baseline_return, meal_window_max_peak, refractory) compared with the TP lockout. |
| `methods/harvey/results/excursion_v2/` | All rules with the shared excursion definition (excursion_end then the candidate main rule). |
| `methods/harvey/results/rule_check/` | Pre-set check of excursion_end vs refractory (deviations section Y); later overridden by Z1. |
| Route A outputs (`summary_routeA.csv`, `chosen_params_routeA_*.json` in the Harvey folders above) | Per-participant tuning; Route B only for new methods (Z4). |
| `methods/faccioli/results/protocol_v1_nightgain/` | First Faccioli run with Faccioli's night gain rule (Sens about 20 %); superseded by the grid gain. |
| `methods/lim/results/protocol_v1_h20/`, `protocol_v1_h30/` | Lim sensitivity runs with 20 and 30 mg/dL minimum height. |
| `methods/pellizzari2025_tma/results/` | Earlier TMA runs under an older evaluation setup (all meals, then breakfast and lunch). |
| `common/results/cohort_flow/v2/` | Older version of the cohort flow. |

Standard-format exports for the dashboard (`methods/*/results/**/standard/`) and row-level tables
of the protocol runs (`detections.csv`, `meals.csv`, `recovery_features.csv`) are regenerated
by the runs and not tracked.

## Layout

```
common/
  data/cgmacros.py        CGMacros loader (native Dexcom 5-min grid, meal merging, groups)
  qc/build_cohort_flow.py QC and cohort flow (plan section 2.4)
  evaluation/             cohort, scoring, matching, tuning, metrics, adjacent rules, excursion,
                          detector registry, protocol runner, README writer, method comparison
  export/result_format.py standard result format (read by the dashboard)
  configs/                cgmacros_eval.toml (shared settings, [protocol]), paths.toml (data path)
  docs/                   deviations.md (framework decisions), result_format.md
methods/<folder>/         src/, configs/, docs/, tests/, results/
docs/                     evaluation plan, references, pre-specification log
results/                  method_comparison.md
```
