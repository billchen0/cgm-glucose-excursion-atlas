# CGMacros data shape — verified 2026-10-06

Measured directly from the 45 participant CSVs in
`/Users/billchen/Desktop/JupyterHealth/Datasets/CGMacros/1.0.0/extracted/CGMacros/`.
Reproduce with `python -m cgm_excursions.audit` (reads only, writes nothing).

## What the files are

Each participant CSV is a **one-row-per-minute snapshot**, not two clean CGM streams.

| Property | Value across all 45 participants |
|---|---|
| Row cadence (base) | 60 s — the smallest interval seen anywhere |
| Row cadence (uniform?) | **No.** 1,155 intervals exceed 60 s across 10 participants |
| Longest single interval | 54,060 s (15.0 h) in participant `018` |
| Worst skip rate | participant `007` — 870 of 5,654 intervals (15.4 %) skip minutes, up to 1,380 s |
| Duplicate timestamps | 0 |
| Out-of-order timestamps | 0 (strictly monotonic in all 45) |
| Rows where **both** sensors are null | 0 |
| Rows where only Dexcom is null | 0–669 per participant |
| Rows where only Libre is null | 0–465 per participant |

> **Do not describe this cadence as "uniform".** Every participant's *median* interval is
> exactly 60 s, which is what made a median-only summary read as a uniform 60 s grid. The
> median cannot see a tail by construction: 10 of 45 participants skip minutes.
> `cgm audit` now reports the base, the longest interval, and the skipped-interval count,
> and `tests/test_audit.py` pins that behaviour.

### The one participant whose cadence truly breaks — `018`

Participant `018` is the only file in the cohort containing a **run** of long steps; every
other long step is isolated. Its 14,085 rows form three contiguous regimes:

| Regime | Rows | Count | Median step | Span | Dexcom null | Eligible |
|---|---|---|---|---|---|---|
| A — dense | 0–945 | 946 | 1 min | 0.7 d | 69 | 877 |
| B — **sparse block** | 946–960 | **15** | **901 min (15 h)** | **8.8 d** | **15 (all)** | **0** |
| C — dense again | 961–14,084 | 13,124 | 1 min | 9.1 d | 67 | 13,057 |

Regime B is a genuine 8.8-day span represented by only 15 rows at ~15-hour spacing, with
**Dexcom absent from every one of them**. Minute-resolution recording resumes immediately
after. This is not a single "hole" — it is a sustained low-rate stretch bracketed by normal
recording, and it is the reason the cohort's longest interval is 54,060 s rather than the
~1,380 s of the next-worst participant.

## The load-bearing finding

The README's phrase "5-minute Dexcom / 15-minute Libre" describes the **underlying
sensor cadence, not the file layout**. The file is minute-resolution, and each sensor's
last reading is **carried forward** into the following minutes until it refreshes.

Measured as the fraction of a sensor's non-null readings that are identical to the
immediately preceding reading in the same file:

| Stream | median | min | max |
|---|---|---|---|
| Dexcom GL | 15.4 % | 9.8 % | 29.9 % |
| Libre GL | 8.9 % | 4.5 % | 46.8 % |

A 5-minute sensor sampled into a 1-minute grid would show ~80 % carried values. The
measured 9–30 % is lower, so the true refresh interval is **not** safely assumed to be
5 minutes, and a fixed 5-minute grid is therefore not safe either: bucketing a 60 s
snapshot into 300 s bins silently mixes fresh readings with carried-forward copies and
invents a sampling pattern the file does not have.

**Consequence for the pipeline: there is no bucketing and no resampling.** The canonical
table is the file's own rows, and each row carries an explicit
`*_glucose_is_fresh` flag (a reading that differs from that stream's previous
non-null reading, plus the first reading in each stream). The dashboard plots fresh
observations by default and can reveal carried values for provenance, so a consumer
can never mistake a held value for a new measurement.

## Sensor values

| Stream | observed min | observed max | documented range | reading precision |
|---|---|---|---|---|
| Dexcom GL | 40.0 | 400.0 | 40–400 mg/dL | 0.1 (one decimal) |
| Libre GL | 40.0 | 405.0 | 40–500 mg/dL | 0.1 (one decimal, mean-interpolated) |

`40.0` sits exactly at the floor of both documented ranges and is also the value some
sensors emit at/below their lower limit, so it is flagged `qc_possible_compression_low`.
It is never treated as a true reading and never deleted.

## Header variation across the 45 files

**Nine** distinct layouts exist (`cgm audit` enumerates them; the counts sum to 45).
Column **order is not stable**, so every column must be resolved by normalized header name
and never by position.

| # | Layout | Participants | Distinctive feature |
|---|---|---|---|
| 1 | `libre_first`, activity=`METs` | 22 | baseline layout |
| 2 | `libre_first`, activity=`Intensity` | 10 | activity field renamed |
| 3 | `libre_first`, activity=`METs`, leading index | 6 | leading unnamed index column |
| 4 | `libre_first`, activity=`METs` | 2 | — (differs from #1 in unlisted column detail) |
| 5 | `libre_first`, activity=`METs`, index, padded | 1 (`001`) | `Amount Consumed ` with trailing space |
| 6 | `dexcom_first`, activity=`METs`, index | 1 (`004`) | **sensor columns swapped** — a positional parser silently swaps the two sensors for this participant alone |
| 7 | `libre_first`, activity=`METs`, steps, record index | 1 (`007`) | `Steps` column, `RecordIndex` shifts the meal fields |
| 8 | `libre_first`, activity=`METs` | 1 (`013`) | — |
| 9 | `libre_first`, activity=`Intensity`, index | 1 (`033`) | — |

Layouts #1 and #4 carry the same label but are distinct groups, which means the grouping
key does not yet capture every differing column. Treat the numeric count (9) as
authoritative and the labels as descriptive.

## Timestamps

Upstream shifted every participant's dates by a private offset of 365–720 days. Within-
participant intervals and clock times are preserved; the calendar dates are **not** real.
The pipeline therefore reports `elapsed_minutes` from each participant's first sample as
the primary time axis and treats `timestamp_shifted` as an opaque ordering key. It never
presents a shifted date as a real calendar date.

## Companion tables

- `bio.csv` — 45 rows, keyed by integer `subject` 1–49 matching folder numbers, all 45
  present, `A1c PDL (Lab)` complete (0 nulls) in percent.
- `gut_health_test.csv` — 47 rows, includes subjects 24 and 25 which have **no CGM
  folder**. Any join must be explicit and left-validated against the CGM cohort.
- `microbes.csv` — out of scope for this pipeline.
