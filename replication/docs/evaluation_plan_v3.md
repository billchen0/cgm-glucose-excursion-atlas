# Evaluation plan (v3)

> **Status note (added 2026-10-06).** This is a Markdown conversion of the original plan
> (Evaluation_Plan_CGMacros_v3.docx, September 2026). The text below is unchanged apart from
> formatting. Decisions taken later, which change or settle parts of it, are logged in
> `common/docs/deviations.md`:
>
> - Route B only for new methods (global tuning, participant-level 5-fold CV); Route A results kept as a record (section Z4).
> - Main adjacent-detection rule: refractory, 120 min (Z1), chosen after the rule check in section Y. tp_lockout (Hochsmann 2026) is a comparison only, because it uses meal labels (Z2). The other adjacent rules are a record only (Z3).
> - Recovery features use a shared excursion definition, frozen on 2026-10-01 (section X; Z5). This settles "Decide from data" in section 8.
> - Minimum valid days: 7 (42 participants). FP/day denominator: scored days, FP per scored hour as secondary (E10).
> - Lim 2026: breakfast and lunch windows only, fixed parameters (methods/lim/docs/deviations.md).
> - Pellizzari 2025 TMA is excluded because it needs training; Archavli 2024 was not replicated.
>
> Method-specific decisions are in `methods/<name>/docs/deviations.md`. The order of decisions is in `docs/prespecification_log.md`.

Food-log-free glucose excursion detection on CGMacros

## 1. Purpose

We will evaluate training-free CGM excursion detectors on CGMacros. One detector will then be locked and applied to AI-READI, which has no meal labels. The evaluation answers two questions:

- Detection. Does the method find the excursions it should find?

- Recovery features. Do features computed from detected excursions agree with features anchored to logged meal times?

The benchmark design follows Hochsmann et al. 2026 (Sci Rep 16:15714). Deviations are listed in Section 9.

## 2. Data processing

### 2.1 Dataset and device

- Dataset: CGMacros, 45 participants (healthy, prediabetes, T2D).

- Device: Dexcom only. AI-READI uses Dexcom G6 only, and Dexcom and Libre readings in CGMacros differ substantially.

- Results are reported overall and by glycaemic group.

### 2.2 Sampling

- CGMacros provides Dexcom data linearly interpolated from 5 min to 1 min. We use this as provided.

- Methods run at 1 min use the 1-min series. Methods run at 5 min take every fifth sample.

- On AI-READI (native 5 min), we apply the same linear interpolation to 1 min. Both datasets therefore receive identical input handling.

### 2.3 Gaps

- Gaps of 30 min or less are linearly interpolated. Longer gaps stay missing.

### 2.4 Quality control

- Exclude the first 24 h after each sensor insertion (sensor warm-up).

- One analysis day is one calendar day.

- Exclude days with a continuous gap longer than 120 min.

- Exclude days without both a logged breakfast and a logged lunch.

- Minimum valid days per participant. [ 7 or 8 valid days]

- Report a cohort flow table: screened, excluded by each rule, final.

- The same QC rules apply to AI-READI, except those that need meal logs.

### 2.5 Meal events

- Log entries within 30 min are merged into one meal.

- Meal start is the time of the first photo.

### 2.6 Cohort flow

The table shows the cohort flow on the CGMacros Dexcom data. All 45 participants pass rules 1 to 3. Rule 2 removes the most days (103 of 457). Most of these (91) are partial days at the start or end of a sensor. Real sensor gaps remove 12 days, in two participants. Two participants (018 and 026) have a second sensor insertion, so a second warm-up is removed. 007 has recurring short gaps of about 20 min, which are filled by the 30-min interpolation rule. Rule 1 removes the most meals (87). After rule 3, 345 days and 690 breakfast and lunch meals remain. Rule 4 rows are each compared with rule 3. At most 8 valid days are possible because each sensor lasts about 10 days. Counts by glycaemic group and gap lengths are in common/results/cohort_flow/.

| Step | Participants | Days | Breakfast + lunch meals | Days removed | Meals removed |
|---|---|---|---|---|---|
| 0. Screened (all Dexcom data) | 45 | 502 | 852 |  |  |
| 1. Remove first 24 h after each sensor insertion | 45 | 457 | 765 | 45 | 87 |
| 2. Remove days with a gap over 120 min | 45 | 354 | 700 | 103 | 65 |
| of which partial first or last day of a sensor |  |  |  | 91 | 62 |
| of which internal sensor gap |  |  |  | 12 | 3 |
| 3. Remove days without breakfast and lunch | 45 | 345 | 690 | 9 | 10 |
| 4. Minimum valid days per participant [Confirm with PhD] |  |  |  |  |  |
| at least 7 valid days | 42 | 333 | 666 | 12 | 24 |
| at least 8 valid days | 39 | 312 | 624 | 33 | 66 |

## 3. Ground truth

- Primary: breakfast and lunch.

- Sensitivity analysis: clean meals, including dinner. A clean meal has no other logged intake within a set time before and after it. [2 hours?]

- Snacks are not scored.

## 4. Evaluation windows and block-out periods

- Night block-out (22:00 to 07:00). Detections whose onset falls in this period are not scored.  Recovery of an excursion that starts in the day may be followed into the night.

- Scoring window (primary analysis). Only detections between 07:00 and lunch start plus 180 min are scored. Detections caused by dinner or afternoon snacks are then not counted as false positives. [4:00 pm?]

- Clean-meal analysis. The scoring window covers the day outside the night block-out. Detections near non-clean meals are not scored.

## 5. Methods in scope

All methods are training-free. Group A methods follow the review's implementation. Lim and Archavli follow their own papers.

| Method | Family | Sampling | Source | Notes |
|---|---|---|---|---|
| Dassau 2-of-3 | Rate-of-change voting | 1 min | Hochsmann | Tuned thresholds in the review do not match its voting rule. We implement the equation as written. |
| Dassau 3-of-4 | Rate-of-change voting | 1 min | Hochsmann |  |
| Faccioli | Super-twisting observer | 5 min | Hochsmann | Observer gain tuning procedure not stated. |
| Harvey (GRID) | Filtered rate of change | 5 min | Hochsmann |  |
| Popp | Simulation-based | 1 min | Hochsmann | No insulin input in CGMacros. |
| Samadi | Fuzzy logic | 5 min | Hochsmann | Simplified rule as in the review. |
| Turksoy | UKF on minimal model | 1 min | Hochsmann | No insulin input in CGMacros. |
| Lim 2026 | Wavelet + fixed threshold | 5 min | Own paper | Uses fixed clock-time meal windows. One detection per window, so it cannot find non-meal excursions. Appendices A to C needed. |
| Archavli 2024 | Local maxima + group thresholds | 5 min | Own paper | Needs glycaemic group. Returns whole peaks with start and end, which suits recovery analysis. Some details not stated. |

- Excluded: Kolle-Ra and Kolle-CGM (require training). Template matching (Pellizzari 2025) is not included at this stage.

## 6. Tuning and data splits

### 6.1 Two tuning routes

|  | Route A: faithful replication | Route B: transferable (proposed primary) |
|---|---|---|
| Purpose | Check our implementation against the review | Produce the detector locked for AI-READI |
| Tuning | Per participant, as in the review | One global parameter set per method |
| Split | Each participant's days split into validation and test | Participant-level 5-fold cross-validation, stratified by glycaemic group |
| Transfer to new people | No | Yes |

- Global tuning has precedent: Kolle 2020, Popp 2024, Harvey 2014, Faccioli 2022 (original), Archavli 2024 and Lim 2026 all use population-level parameters. [Route B as primary?]

### 6.2 Tuning objective

- F2 score on validation data, as in the review. F2 combines precision and recall and weights recall about four times as much.

- Ties: lower FP/day first, then shorter delay.

- All parameters and rules are fixed before test data are scored.

## 7. Matching rules

- True positive (TP): a detection within a window around the logged meal start. Proposed window: 30 min before to 120 min after.

- False negative (FN): a scored meal with no TP.

- False positive (FP): a detection inside the scoring window that matches no meal.

- Delay: detection time minus logged meal start, for TPs.

- FP/day denominator: all scored days, or scored hours converted to days. [Decide from data]

### 7.1 Adjacent peaks

[not sure about double peaks] Choose one rule:

- A 120-min lockout after each TP. Detections within it are not counted (Hochsmann 2026).

- Merge two peaks unless glucose returns near baseline between them. This matches the definition of recovery.

- One detection per meal window, keeping the highest peak (Lim 2026).

## 8. Metrics

| Level | Metrics | Notes |
|---|---|---|
| Detection | Sensitivity, precision, FP/day, delay | Comparable with the review. 95% CI by participant-level bootstrap. |
| Recovery-feature agreement | Peak time, peak height, iAUC, recovery time | For matched events. Each feature: ICC (absolute agreement) and Bland-Altman bias with 95% limits of agreement. |

- Reference features are computed from the logged meal start, with termination at 180 min (project charter).

- Detected excursions need a segmentation step to find peak and end. Archavli returns these directly. For other methods the step is [Decide from data].

- Stratified reporting: glycaemic group and meal (breakfast, lunch). Optional: carbohydrate tertile, using CGMacros meal macronutrients.

- [primary metric level and final metric set]

## 9. Reporting principles

- Report results under the review's original rules (for comparison with the literature) and under our rules (for project decisions).

- Record every deviation from a source paper in a deviations log, with the reason.

- Rules are changed only from development data, never from the test set.

- Report null or weak results as they are.

## 10. Questions for the PhD mentor

- Route B (global tuning, participant-level cross-validation) as the primary result?

- Early tolerance for a TP: 15 or 30 min before the logged meal?

- Adjacent-peak rule: lockout, return to baseline, or highest peak per window?

- Primary metric: detection level or recovery-feature agreement? Should the tuning objective change with it?

- Scoring window for the breakfast and lunch analysis: is 07:00 to lunch plus 180 min acceptable?

- Minimum valid days per participant: 7 or 8?

