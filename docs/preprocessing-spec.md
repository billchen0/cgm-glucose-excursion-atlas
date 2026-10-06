# Preprocessing specification — CGM prior to analysis

This is the contract every stage in `src/cgm_excursions/` implements. It is written to be
read before the code, and the code is written to be read.

## Governing principle

**Preprocessing prepares data for analysis. It does not analyse, detect, clean silently,
or decide.** Nothing is deleted, clipped, smoothed, interpolated, or corrected on the
way through. Every questionable value survives, carrying a named flag that a later stage
can act on explicitly and auditable.

Three consequences that shape everything below:

1. No glucose value is ever modified. A flag is added next to it.
2. No row is ever dropped. An eligibility column is added next to it.
3. No gap is ever bridged inside the canonical outputs. A separate opt-in view may
   interpolate, and only when a caller states the maximum gap it will bridge.

## Stages

Each stage is one function in `preprocessing.py` and is independently testable.

| # | Stage | Input | Output | Fails when |
|---|---|---|---|---|
| 0 | `resolve_dataset` | path to ZIP or extracted dir | `DatasetSource` (file inventory) | no participant CSVs found |
| 1 | `read_participant` | one participant CSV | raw frame, normalized headers | a required column is missing |
| 2 | `type_and_sort` | raw frame | typed, time-ordered frame | duplicate or non-monotonic timestamps remain |
| 3 | `flag_values` | typed frame | + value-integrity flags | — |
| 4 | `flag_stream_qc` | typed frame | + per-stream QC flags | — |
| 5 | `mark_fresh_observations` | typed frame | + freshness flags | — |
| 6 | `derive_analysis_columns` | typed frame | + analysis value/grid/eligibility/segment | — |
| 7 | `detect_gaps` | typed frame | gap runs per stream | — |
| 8 | `roll_up_coverage` | per-participant results | participant/day/segment summaries | — |
| 9 | `write_outputs` | results + config | 3 parquet + 1 json + manifest | output dir not writable |

## Canonical outputs

Written to `data/processed/`, named by a versioned run id.

### `cgm.parquet` — one row per participant-minute

The file's own rows. No bucketing, no resampling, no gap filling.

| Column | Type | Meaning |
|---|---|---|
| `subject_id` | string `"001"` | participant, zero-padded, matching the folder name |
| `timestamp_shifted` | datetime64[ns] | upstream-shifted timestamp, an ordering key only |
| `elapsed_minutes` | float64 | minutes since that participant's first sample |
| `dexcom_glucose_raw` | float64 | observed value, byte-for-byte from the file |
| `libre_glucose_raw` | float64 | observed value, byte-for-byte from the file |
| `dexcom_glucose_is_fresh` | boolean | True when this row's value differs from Dexcom's previous non-null value |
| `libre_glucose_is_fresh` | boolean | as above, for Libre |
| `meal_type_raw` | string | meal label on this row, else null |
| `analysis_glucose` | float64 | primary-stream value for this row (Dexcom) |
| `analysis_on_grid` | boolean | whether the primary stream has an observation at this timestamp |
| `qc_eligible` | boolean | **the** analysis mask: primary value present, no hard flag |
| `segment_id` | Int64 | contiguous eligible run index, reset per participant |
| `qc_*` | boolean | one column per flag below |

### `meals.parquet`

One row per meal, de-duplicated from the minute rows into discrete events.

`subject_id, meal_timestamp, elapsed_minutes, meal_type_raw, calories, carbs_g, protein_g, fat_g, fiber_g, amount_consumed, has_complete_macros`

### `participants.parquet`

`bio.csv`, joined to the CGM cohort, plus derived CGM summary counts:
`subject_id, age, gender, bmi, body_weight_kg, height_cm, self_identified_ethnicity, a1c_percent, a1c_band, fasting_glucose_mgdl, insulin, triglycerides, cholesterol, hdl, non_hdl, ldl_cal, vldl_cal, cho_hdl_ratio, collection_time, has_cgm_data, cgm_row_count, cgm_first_ts, cgm_last_ts`

`a1c_band` uses the published cohort definition: `<5.7` normal, `5.7–6.4` prediabetes,
`>6.4` diabetes. The pipeline reports the band; it does not use it to filter.

### `qc_summary.json`

Rollups at the three levels the QC contract requires, plus the run manifest.

```jsonc
{
  "manifest": { /* see below */ },
  "participants": [ /* one record per participant */ ],
  "days": [ /* one record per participant-calendar-day */ ],
  "segments": [ /* one record per contiguous usable run */ ]
}
```

## QC flags (v1: objective only)

Every flag is a boolean column. A flag records an observation; it does not exclude a row
by itself except where marked **hard**.

| Flag | Rule | Hard? |
|---|---|---|
| `qc_out_of_documented_range` | value outside the stream's documented range | no |
| `qc_possible_compression_low` | value exactly at the low sentinel (40.0) | no |
| `qc_duplicate_timestamp` | timestamp repeats for the same participant (never observed in CGMacros, kept as a guard) | **hard** |
| `qc_rate_of_change` | \|Δglucose\| / Δt > `max_mgdl_per_min` | no |
| `qc_flatline` | run of ≥ `min_run_minutes` identical consecutive readings in one stream | no |
| `qc_isolated_spike` | single sample ≥ `min_delta_mgdl` from the midpoint of its neighbours while the neighbours are within `neighbour_max_delta_mgdl` of each other | no |

Advanced heuristics (sensor-artifact models, compression-low prediction, non-wear
inference) exist as configuration keys and are **disabled**, pending threshold validation
against this dataset. They are named here so they are not invented ad hoc later.

## Eligibility

`qc_eligible` is computed **only** from the primary stream:

```
qc_eligible = analysis_glucose.notna()
              AND NOT qc_duplicate_timestamp
```

Range, rate-of-change, flatline, and spike flags **do not** clear eligibility. They are
evidence for a downstream detector or a human to weigh. This is deliberate: a flag whose
threshold is a screening guess must never silently remove physiology. Any exclusion rule
belongs to a detector or an analysis, configured and reported there.

## Missingness and gaps

- The canonical table preserves every absent minute as a row with null values.
- Gaps are detected **per stream** on that stream's own observation series. A minute where
  only Libre reported is not a Dexcom gap caused by the file; it is a refresh boundary.
- `min_gap_seconds` (default 900) sets the shortest run worth reporting.
- `segment_break_seconds` (default 3600) sets the gap length that ends a usable segment.

## Per-stream conventions

- `timestamp_shifted` — a shifted calendar date. Never displayed as a real date. Charts
  use `elapsed_minutes`.
- Sensor values — mg/dL, native decimal precision, never rounded by this pipeline.
- Meal times — taken from the same shifted clock, so they share the participant's axis.

## Reproducibility

The manifest records the dataset source and archive SHA-256, the number of participants
and rows read, the config file's SHA-256, the pipeline version, the exact software
versions, and the SHA-256 of every written output. A run is reproducible when its
manifest matches.
