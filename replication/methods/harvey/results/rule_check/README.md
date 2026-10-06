# Main adjacent rule check: excursion_end vs refractory (2026-10-01)

One-off check. No rule, no excursion parameter and no earlier result was changed.

## Decision criteria (fixed before running)

Choose excursion_end as main if ANY of these holds on Route B; otherwise choose refractory.

- C1. >= 10 % of refractory-kept events start inside an ongoing excursion (split excursions).
- C2. The C1 percentage differs by >= 5 pp between any two groups (healthy, prediabetes, T2D).
- C3. Events per participant-day differ by >= 10 % between the two rules within at least one group, and the direction or size of that difference is not the same across groups (state exactly what you compared).

Operational definitions (written before any result was computed):

- All criteria use Route B, main analysis (each rule with its own locked parameters).
- Events = kept detections with onset 07:00 to 21:59 (night block-out excluded). The rules themselves run on the whole detector day, as in the pipeline.
- C1: M1 overall, % of refractory-kept events that are split. Met if >= 10.0 %.
- C2: M1 by group. Met if max minus min across the three groups >= 5.0 pp.
- C3: for each group g, d_g = 100 * (mean events per participant-day under excursion_end minus the same under refractory) / (refractory value). Participant-days = all evaluated test days, days with no event count as 0. Met if max abs(d_g) >= 10.0 AND (the signs of d_g differ across groups OR max(d_g) - min(d_g) >= 5.0 pp). The 5 pp size threshold mirrors C2.

## Setup

- Detections: the saved excursion_v2 runs of excursion_end and refractory (our matching rule).
- Route B: each held-out participant with that fold's locked parameters. Route A (appendix): each participant's test days with that participant's parameters.
- Main analysis: each rule with its own locked parameters, so raw detections differ.
- Same-raw analysis: refractory applied to excursion_end's raw detections (excursion_end parameters), to isolate the rule effect.
- Excursions: the shared function in `common/evaluation/excursion.py`, frozen parameters.
- Events and merged detections count only with onset 07:00 to 21:59. M3 uses the scoring window and logged breakfast and lunch.

## Results, Route B

### M1. Split excursions under refractory (main analysis)

Route B, test data. n = refractory-kept events (07:00 to 21:59). Split = starts before the previous kept detection's excursion end.

| Group | Kept events | Split | % split |
|---|---|---|---|
| overall | 1100 | 32 | 2.9 |
| healthy | 369 | 3 | 0.8 |
| prediabetes | 348 | 6 | 1.7 |
| T2D | 383 | 23 | 6.0 |

### M1. Split excursions under refractory (same raw detections)

Route B, test data. n = refractory-kept events (07:00 to 21:59). Split = starts before the previous kept detection's excursion end.

| Group | Kept events | Split | % split |
|---|---|---|---|
| overall | 1109 | 33 | 3.0 |
| healthy | 377 | 4 | 1.1 |
| prediabetes | 349 | 7 | 2.0 |
| T2D | 383 | 22 | 5.7 |

### M2. Long merges under excursion_end

Route B, test data. n = merged detections (07:00 to 21:59). Long = more than 120 min after the event anchor.

| Group | Merged | > 120 min | % long |
|---|---|---|---|
| overall | 452 | 44 | 9.7 |
| healthy | 100 | 7 | 7.0 |
| prediabetes | 126 | 7 | 5.6 |
| T2D | 226 | 30 | 13.3 |

### M3. Rule-caused misses (main analysis)

Route B, scoring window, logged breakfast and lunch. n = FN meals.

| Rule | Reason | Healthy | Prediabetes | T2D | Total |
|---|---|---|---|---|---|
| excursion_end | excursion_end: removed while the anchor's excursion was ongoing | 6 | 1 | 5 | 12 |
| excursion_end | no removed detection in TP window | 55 | 45 | 37 | 137 |
| refractory | no removed detection in TP window | 56 | 45 | 38 | 139 |
| refractory | refractory: removed after the blocking excursion had ended | 13 | 7 | 7 | 27 |
| refractory | refractory: removed while the blocking excursion was ongoing | 2 | 1 | 5 | 8 |

### M3. Rule-caused misses (same raw detections)

Route B, scoring window, logged breakfast and lunch. n = FN meals.

| Rule | Reason | Healthy | Prediabetes | T2D | Total |
|---|---|---|---|---|---|
| excursion_end | excursion_end: removed while the anchor's excursion was ongoing | 6 | 1 | 5 | 12 |
| excursion_end | no removed detection in TP window | 55 | 45 | 37 | 137 |
| refractory | no removed detection in TP window | 55 | 45 | 38 | 138 |
| refractory | refractory: removed after the blocking excursion had ended | 14 | 6 | 7 | 27 |
| refractory | refractory: removed while the blocking excursion was ongoing | 2 | 1 | 5 | 8 |

### M4. Events per participant-day (main analysis)

Route B, test data. n = participant-days (days with no event count as 0). Events with onset 07:00 to 21:59. Diff = excursion_end vs refractory, on the mean.

| Group | Days | excursion_end mean (median) | refractory mean (median) | Diff % |
|---|---|---|---|---|
| overall | 333 | 3.99 (4) | 3.30 (3) | +20.7 |
| healthy | 119 | 4.11 (4) | 3.10 (3) | +32.5 |
| prediabetes | 104 | 4.04 (4) | 3.35 (3) | +20.7 |
| T2D | 110 | 3.81 (4) | 3.48 (3) | +9.4 |

### M4. Events per participant-day (same raw detections)

Route B, test data. n = participant-days (days with no event count as 0). Events with onset 07:00 to 21:59. Diff = excursion_end vs refractory, on the mean.

| Group | Days | excursion_end mean (median) | refractory mean (median) | Diff % |
|---|---|---|---|---|
| overall | 333 | 3.99 (4) | 3.33 (3) | +19.7 |
| healthy | 119 | 4.11 (4) | 3.17 (3) | +29.7 |
| prediabetes | 104 | 4.04 (4) | 3.36 (3) | +20.3 |
| T2D | 110 | 3.81 (4) | 3.48 (3) | +9.4 |

### M5. Event duration, anchor to excursion end (main analysis)

Route B, test data. n = kept events (07:00 to 21:59). Median [IQR], min.

| Group | excursion_end | refractory |
|---|---|---|
| overall | 78 [40, 150] (1328) | 85 [44, 157] (1100) |
| healthy | 55 [30, 110] (489) | 56 [33, 119] (369) |
| prediabetes | 88 [45, 150] (420) | 90 [48, 154] (348) |
| T2D | 110 [58, 180] (419) | 112 [60, 180] (383) |

### M5. Event duration, anchor to excursion end (same raw detections)

Route B, test data. n = kept events (07:00 to 21:59). Median [IQR], min.

| Group | excursion_end | refractory |
|---|---|---|
| overall | 78 [40, 150] (1328) | 84 [44, 157] (1109) |
| healthy | 55 [30, 110] (489) | 55 [32, 118] (377) |
| prediabetes | 88 [45, 150] (420) | 90 [49, 155] (349) |
| T2D | 110 [58, 180] (419) | 112 [60, 180] (383) |

## Result

Route B, main analysis.

| Criterion | Value | Threshold | Met |
|---|---|---|---|
| C1 | 2.9 % split | >= 10.0 % | no |
| C2 | range 5.2 pp (healthy 0.8, prediabetes 1.7, T2D 6.0) | >= 5.0 pp | yes |
| C3 | d_g healthy +32.5 %, prediabetes +20.7 %, T2D +9.4 %; max abs(d_g) 32.5; spread 23.1 pp | >= 10 % in a group AND (sign differs OR spread >= 5 pp) | yes |

Criteria met: C2, C3.
Choice: **excursion_end** is the main rule.

## Appendix: Route A (secondary check)

Criteria on Route A, main analysis. Shown for information; the choice uses Route B only.

| Criterion | Value | Threshold | Met |
|---|---|---|---|
| C1 | 1.9 % split | >= 10.0 % | no |
| C2 | range 2.9 pp (healthy 0.6, prediabetes 1.7, T2D 3.5) | >= 5.0 pp | no |
| C3 | d_g healthy +35.3 %, prediabetes +5.8 %, T2D +5.8 %; max abs(d_g) 35.3; spread 29.5 pp | >= 10 % in a group AND (sign differs OR spread >= 5 pp) | yes |

### M1. Split excursions under refractory (main analysis)

Route A, test data. n = refractory-kept events (07:00 to 21:59). Split = starts before the previous kept detection's excursion end.

| Group | Kept events | Split | % split |
|---|---|---|---|
| overall | 514 | 10 | 1.9 |
| healthy | 170 | 1 | 0.6 |
| prediabetes | 173 | 3 | 1.7 |
| T2D | 171 | 6 | 3.5 |

### M1. Split excursions under refractory (same raw detections)

Route A, test data. n = refractory-kept events (07:00 to 21:59). Split = starts before the previous kept detection's excursion end.

| Group | Kept events | Split | % split |
|---|---|---|---|
| overall | 496 | 6 | 1.2 |
| healthy | 171 | 0 | 0.0 |
| prediabetes | 155 | 0 | 0.0 |
| T2D | 170 | 6 | 3.5 |

### M2. Long merges under excursion_end

Route A, test data. n = merged detections (07:00 to 21:59). Long = more than 120 min after the event anchor.

| Group | Merged | > 120 min | % long |
|---|---|---|---|
| overall | 158 | 11 | 7.0 |
| healthy | 32 | 0 | 0.0 |
| prediabetes | 42 | 0 | 0.0 |
| T2D | 84 | 11 | 13.1 |

### M3. Rule-caused misses (main analysis)

Route A, scoring window, logged breakfast and lunch. n = FN meals.

| Rule | Reason | Healthy | Prediabetes | T2D | Total |
|---|---|---|---|---|---|
| excursion_end | excursion_end: removed while the anchor's excursion was ongoing | 2 | 0 | 3 | 5 |
| excursion_end | no removed detection in TP window | 36 | 27 | 24 | 87 |
| refractory | no removed detection in TP window | 37 | 23 | 23 | 83 |
| refractory | refractory: removed after the blocking excursion had ended | 6 | 3 | 2 | 11 |
| refractory | refractory: removed while the blocking excursion was ongoing | 3 | 1 | 3 | 7 |

### M3. Rule-caused misses (same raw detections)

Route A, scoring window, logged breakfast and lunch. n = FN meals.

| Rule | Reason | Healthy | Prediabetes | T2D | Total |
|---|---|---|---|---|---|
| excursion_end | excursion_end: removed while the anchor's excursion was ongoing | 2 | 0 | 3 | 5 |
| excursion_end | no removed detection in TP window | 36 | 27 | 24 | 87 |
| refractory | no removed detection in TP window | 36 | 27 | 24 | 87 |
| refractory | refractory: removed after the blocking excursion had ended | 4 | 1 | 4 | 9 |
| refractory | refractory: removed while the blocking excursion was ongoing | 2 | 0 | 4 | 6 |

### M4. Events per participant-day (main analysis)

Route A, test data. n = participant-days (days with no event count as 0). Events with onset 07:00 to 21:59. Diff = excursion_end vs refractory, on the mean.

| Group | Days | excursion_end mean (median) | refractory mean (median) | Diff % |
|---|---|---|---|---|
| overall | 168 | 3.54 (3) | 3.06 (3) | +15.6 |
| healthy | 60 | 3.83 (4) | 2.83 (3) | +35.3 |
| prediabetes | 52 | 3.52 (3) | 3.33 (4) | +5.8 |
| T2D | 56 | 3.23 (3) | 3.05 (3) | +5.8 |

### M4. Events per participant-day (same raw detections)

Route A, test data. n = participant-days (days with no event count as 0). Events with onset 07:00 to 21:59. Diff = excursion_end vs refractory, on the mean.

| Group | Days | excursion_end mean (median) | refractory mean (median) | Diff % |
|---|---|---|---|---|
| overall | 168 | 3.54 (3) | 2.95 (3) | +19.8 |
| healthy | 60 | 3.83 (4) | 2.85 (3) | +34.5 |
| prediabetes | 52 | 3.52 (3) | 2.98 (3) | +18.1 |
| T2D | 56 | 3.23 (3) | 3.04 (3) | +6.5 |

### M5. Event duration, anchor to excursion end (main analysis)

Route A, test data. n = kept events (07:00 to 21:59). Median [IQR], min.

| Group | excursion_end | refractory |
|---|---|---|
| overall | 78 [40, 147] (594) | 90 [45, 164] (514) |
| healthy | 48 [28, 101] (230) | 56 [28, 113] (170) |
| prediabetes | 85 [44, 146] (183) | 95 [50, 164] (173) |
| T2D | 115 [65, 180] (181) | 115 [70, 180] (171) |

### M5. Event duration, anchor to excursion end (same raw detections)

Route A, test data. n = kept events (07:00 to 21:59). Median [IQR], min.

| Group | excursion_end | refractory |
|---|---|---|
| overall | 78 [40, 147] (594) | 85 [44, 158] (496) |
| healthy | 48 [28, 101] (230) | 50 [28, 109] (171) |
| prediabetes | 85 [44, 146] (183) | 87 [51, 156] (155) |
| T2D | 115 [65, 180] (181) | 114 [66, 180] (170) |

## Files

`criteria.csv`, `m1_split_excursions.csv`, `m2_long_merges.csv`, `m3_rule_caused_misses.csv`, `m4_events_per_day.csv`, `m5_event_duration.csv`.

Run from `replication/`: `python methods/harvey/src/run_rule_check.py`
