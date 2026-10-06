# Standard result format (one folder per run)

Every method run that should appear in the dashboard exports one folder:

```
methods/<method>/results/<anything>/<run>/
  run.json          required
  detections.csv    required
  meals.csv         optional (declare in run.json "available")
  days.csv          optional (declare in run.json "available")
```

The dashboard finds runs by scanning `methods/*/results/**/run.json`. Nothing else is
registered anywhere. Write the files with `common/export/result_format.write_run`, which
checks the columns and the status values below and refuses to write an invalid run.

Times are local wall-clock timestamps as in CGMacros (`YYYY-MM-DD HH:MM:SS`, no time zone).
`participant` is the CGMacros folder name (`CGMacros-001`).

## run.json

| Key | Type | Meaning |
|---|---|---|
| `format_version` | int | `1` |
| `method` | str | Method folder name (`harvey`, `pellizzari2025_tma`) |
| `run` | str | Run name, unique within the method |
| `title` | str | Short label for selectors |
| `description` | str | One or two sentences |
| `date` | str | Date the underlying results were produced (ISO) |
| `source` | str | Folder of the original results, relative to the replication repo |
| `routes` | object | One entry per value of the `route` column (see below) |
| `adjacent_rule` | str | `tp_lockout`, `meal_window_max_peak`, `refractory`, or a method-specific name |
| `adjacent_rule_uses_labels` | bool | True if the rule needs meal labels (cannot run on AI-READI) |
| `matching_rule` | object | `name`, `tp_before_min`, `tp_after_min` |
| `scoring_window` | str | Plain description of when detections are scored |
| `parameters_file` | str or null | Parameter file(s), relative to the replication repo |
| `available` | object | `{"detections": true, "meals": bool, "days": bool}` |
| `comparable` | bool | False if the run uses a different cohort or scoring rules from `common/` |
| `comparability_note` | str | Required when `comparable` is false; shown in the dashboard |

`routes.<route>`:

| Key | Meaning |
|---|---|
| `label` | Text shown in the dashboard |
| `kind` | `tuning` (how parameters were chosen on this data) or `parameter_source` (fixed parameters taken from elsewhere) |
| `evaluated_days` | Which days count for FP/day: `{"column": "route_a_split", "values": ["test"]}`, or `"all"` (every scored day in `days.csv`) |
| `parameters_file` | Optional, overrides the run-level one |

## detections.csv

One row per detection returned by the detector (before and after any adjacent rule).

| Column | Required | Meaning |
|---|---|---|
| `participant` | yes | |
| `detection_time` | yes | The time that is scored |
| `route` | yes | Key into `run.json` `routes` |
| `split` | yes | `validation`, `test`, `cv-fold<k>`, or `all` |
| `status` | yes | See below |
| `status_original` | yes | The status as the method wrote it |
| `matched_meal_time` | yes | Logged meal start, TP only |
| `delay_min` | yes | `detection_time - matched_meal_time` in minutes, TP only |
| `excursion_start`, `peak_time`, `excursion_end` | no | For methods that return whole excursions (Popp: `excursion_start` = estimated meal start m_st). The dashboard draws a span when start and end are both present. |

Other columns are allowed and ignored by the dashboard.

`status` values:

| Value | Meaning |
|---|---|
| `TP` | Matched to a logged breakfast or lunch |
| `FP` | Scored, no match |
| `not_scored` | Outside the scoring window (night, after lunch + 180 min, day without a window) |
| `removed_by_rule` | Dropped **before scoring** by a label-free adjacent-detection rule (`meal_window_max_peak`, `refractory`) |
| `ignored_by_tp_lockout` | Ignored **at scoring** because it falls within the lockout after a TP. Uses meal labels, so it cannot be applied on AI-READI. |

## meals.csv

One row per ground-truth meal (breakfast and lunch on valid days) per route.

| Column | Required | Meaning |
|---|---|---|
| `participant` | yes | |
| `meal_time` | yes | Merged meal start (`common/data/cgmacros.py`) |
| `meal_type` | yes | `breakfast`, `lunch` |
| `carbs` | yes | g |
| `scored` | yes | bool |
| `outcome` | yes | `TP`, `FN`, `not_scored` |
| `route`, `split` | yes | As in detections.csv |
| `detection_time`, `delay_min` | no | Matched detection, TP only |

## days.csv

One row per participant-day screened by the cohort flow (`common/results/cohort_flow/day_level_qc.csv`).

| Column | Required | Meaning |
|---|---|---|
| `participant` | yes | |
| `date` | yes | Calendar day |
| `qc_status` | yes | `valid`, `gap_partial`, `gap_internal`, `no_breakfast_lunch`, `participant_excluded` (fewer than `min_valid_days` valid days), `sensor_warmup` (before the first retained minute) |
| `route_a_split` | yes | `validation`, `test`, or empty (not in the analysis cohort) |
| `window_start`, `window_end` | yes | Scoring window (empty if the day has none) |
| `scored` | yes | bool; the day counts in FP/day |

Per-participant summary (dashboard and checks): TP and FN from `meals.csv`, FP from
`detections.csv`, sensitivity = TP / (TP + FN), FP/day = FP / number of scored days in
the route's `evaluated_days`.
