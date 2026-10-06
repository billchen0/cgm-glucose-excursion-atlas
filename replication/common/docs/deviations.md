# Deviations and defaults log

Rules follow **docs/evaluation_plan_v3.md** (the source of truth; section
numbers below refer to it). All settings live in `common/configs/cgmacros_eval.toml` (method settings in `methods/<name>/configs/`).
Each entry states what we did, the source, and why. "Default" means neither the plan nor
the source paper states the detail, so we chose it.

Sources: Hochsmann 2026 = Sci Rep 16:15714 (main text) and its Supplementary Material
("Supp."); Harvey 2014 = J Diabetes Sci Technol 8(2):307-320.

## E. Evaluation framework (all methods)

| ID | Topic | What we did | Source / reason |
|---|---|---|---|
| E1 | Sampling for 5-min methods | Plan 2.2 says to take every fifth sample of the 1-min series. We take the fifth samples that fall on the native Dexcom minute phase, i.e. the native readings. The phase is identified per day with the interpolation-residual method in `common/cgmacros.py`. The residual is 0 on all 333 days. | User decision (native 5-min readings). Consistent with plan 2.2, with the phase choice made explicit. |
| E2 | Series used | Cohort-flow 1-min series (`build_cohort_flow.load_1min`, gaps <= 30 min interpolated), with the 24-h post-insertion warm-up set to missing. After QC, no valid day has a missing 5-min sample. | Plan 2.3, 2.4. Reuses the cohort flow code. |
| E3 | Which meals are scored | A breakfast or lunch on a valid day is scored if its TP window reaches into the scoring window (meal start + 120 min >= 07:00). Earlier meals cannot be matched, because detections before 07:00 are not scored. Counts are in `methods/harvey/results/reference_tp_lockout/sample_sizes.csv`. | Default. Plan 4 does not say what happens to meals logged before 07:00. |
| E4 | Scoring window | [07:00, lunch start + 180 min], both ends inclusive, capped at 22:00. Every valid day has exactly one merged lunch. A detection is scored if its onset time is inside the window. | Plan 4. The cap and inclusive ends are defaults. |
| E5 | Snacks and dinner inside the window | Not masked. A detection caused by a morning snack counts as FP. The per-detection table flags FPs within [-60, +120] min of a logged snack or dinner, as a diagnostic only. | Plan 3 (snacks not scored) and 4 (window only). Differs from the TMA `bl_maskDS` protocol, which masked them. |
| E6 | Tuning tie-break | Highest F2, then lower FP/day, then shorter mean delay, then grid order (ascending tau_F, G_min, G'_min,3, G'_min,2). A delay with TP = 0 counts as worst. The number of tied grid points is reported. | Plan 6.2 and Hochsmann 2026 Methods for the first three. The last step is a default. |
| E7 | Route A split | Per participant, days shuffled with the fixed seed. Validation = floor(n/2) days, test = the rest (7 days: 3/4; 8 days: 4/4). There is no training set, because Harvey needs no training. | Plan 6.1. The review used about 31/33/36 % training/validation/test (Methods), and its training set was used only by Kolle. |
| E8 | Route B folds | `StratifiedKFold(5, shuffle=True, seed)` over participants, stratified by glycaemic group. Test metrics pool the five held-out folds. We also tune once on all 42 participants. This is the candidate parameter set to lock for AI-READI. It has no held-out score. | Plan 6.1. The all-data set is an addition. |
| E9 | Recovery features | **PROVISIONAL** segmentation rule, as specified in the task. Details are in the "Recovery features" section below. | Plan 8 says "[Decide from data]". |
| E10 | FP rates | FP/day = FP / number of scored days in the evaluated set. FP per scored hour = FP / total length of the scoring windows. | Plan 7 and the user decision. |
| E11 | Per-meal strata | An FP cannot be assigned to a meal. By meal (breakfast, lunch) we report TP, FN, sensitivity and delay only. FP, precision, F2 and FP rates are reported overall and by group. | Default. |
| E12 | Bootstrap CI | 2000 participant-level resamples, not stratified, percentile 95 % CI. Metrics are recomputed on pooled counts in each resample. Delay CI comes from the pooled TP delays of the resampled participants. | Plan 8. Resample count and percentile method are defaults. |
| E13 | TP window bounds | Inclusive on both ends: [start - before, start + after]. For the review rule, a detection exactly at the logged start (delay 0) counts as TP. The review says "(0,120]" and "only detections occurring after the logged meal start". Delay-0 TPs are counted in `summary_*.csv` (`n_delay_zero`). | `common/evaluation.match_events` (reused) is inclusive. |
| E14 | Review rule comparison | Only the TP window changes (0 to +120 min). The review's afternoon suppression (post-lunch to 15 min before dinner) is not applied. Our scoring window already ends at lunch + 180 min. | User instruction ("everything else unchanged"). |
| E15 | ICC | ICC(A,1): two-way, absolute agreement, single measure (McGraw & Wong 1996, Shrout & Fleiss ICC(2,1)), implemented directly from the ANOVA mean squares. | Plan 8. |
| E16 | Day with no scoring window | CGMacros-043, 2025-10-22: the only "lunch" is logged at 02:17, so lunch + 180 min < 07:00. The day stays in the cohort (it passes QC rules 1-3), but it has no scoring window. Its meals are not scored and it is excluded from the FP/day denominator (332 scored days of 333). | Default. This is a probable meal-label error in CGMacros. The plan does not cover it. |
| E17 | Grid edges and tie-break | `grid_edges` lists parameters at a grid bound. `grid_edges_forced` lists those that every tied grid point shares. Route A has a median of 28 tied grid points per participant (3-4 validation days), so most Route A edge hits come from the grid-order tie-break (E6), not from the data. | Reported so that edge flags are not over-read. |

### Recovery features (PROVISIONAL, E9)

- Anchor: detection time (detector) or logged meal start (reference), for every TP pair.
- Series: QC'd 1-min series (E2), the same for both anchors.
- Baseline: mean glucose in [anchor - 30, anchor).
- Peak: maximum glucose in (anchor, anchor + 180]. The first maximum is used if there are ties.
- Recovery end: first minute after the peak at which glucose <= baseline, capped at anchor + 180 min. A cap-censored end is flagged.
- Features:
  - `peak_time_min` (minutes from anchor to peak)
  - `peak_height` (peak - baseline, mg/dL)
  - `iauc` (trapezoid of max(glucose - baseline, 0) from anchor to recovery end, mg/dL*min)
  - `recovery_time_min` (peak to recovery end)
- A pair is featurised only if the window [anchor - 30, anchor + 180] has no missing minute.
- Note: `peak_time_min` is measured from each anchor. The detector-minus-reference bias therefore contains the detection delay by construction: bias is about -delay when both anchors see the same peak.

## R. Label-free adjacent-detection rules (methods/harvey/results/peak_rules/)

Selected by `[scoring] adjacent_rule`. The default `tp_lockout` reproduces methods/harvey/results/reference_tp_lockout/.

| ID | Topic | What we did | Source / reason |
|---|---|---|---|
| R1 | Meal windows | Breakfast 06:00-11:45, lunch 12:00-16:00, dinner 17:00-21:00, both ends inclusive. The gaps 11:45-12:00 and 16:00-17:00 belong to no window, so detections there are dropped. | Lim 2026 (JDST 20(3):664-672) p. 666, "Definition of PPGR", and the Methods data-integrity paragraph. The paper gives the boundaries, so the task's fallback windows were not used. Inclusive ends are a default. |
| R2 | Which detection is kept | Highest peak = max QC'd 1-min glucose in (t, t + 180 min]. Ties go to the earlier detection. | Task specification. Lim 2026 instead ranks candidate PPGR segments by height (peak minus the lowest point before it) and applies a relative-height/timing tie-break (Appendix C, not available). Its candidates are wavelet segments, not GRID detections. |
| R3 | Window applies to | The detection (onset) time. | Lim 2026 applies the windows to the PPGR start time, and a GRID detection is our onset estimate. |
| R4 | Missing glucose in the peak horizon | Max over available minutes. Valid days have no missing samples after QC. | Default. |
| R5 | Refractory rule | Chronological over the whole detector day (00:00-23:55), including the night. A detection is dropped if it is <= 120 min after the previous kept detection. It does not carry over midnight. | Task specification. The midnight reset is a default. |
| R6 | No TP lockout | With either new rule the scorer's lockout is 0, so every kept detection is TP or FP. | Task specification. |
| R7 | Order of post-processing and scoring | Rule first, then the 07:00-to-lunch+180 scoring window. Harvey counts: see methods/harvey/docs/deviations.md (R7). | Consequence of applying the rule before scoring (task) combined with the night block-out (plan 4). |
| R8 | Tuning | The rule is applied inside the grid search, so each rule has its own parameters. Matching rule is "ours" only. | Task specification. |

## X. Shared excursion definition (added 2026-10-01)

- **What changed:** the baseline and the excursion end are unified in one function (`common/evaluation/excursion.py`, `[excursion]` in the config). The adjacent rule `excursion_end` and the recovery features (`[features] segmentation = "excursion"`) both use it. The provisional rule (E9) stays the default, so earlier runs reproduce exactly.
- **Definition:** baseline b = min glucose over the valid minutes in [a - 60, a]. End = return (glucose <= b + max(10, 0.20 * (P - b)) after the running peak P) or a confirmed trough (drop >= 50 % of P - b, then a rise of >= 10 mg/dL within 30 min) or the 180-min censor. Peak = max in (a, end].
- **Unchanged:** the completeness window ([a - 30, a + 180], no missing minute), so the pair set is identical. Recovery time (peak to end), iAUC (anchor to end, above baseline) and peak time (from the anchor) keep their definitions.
- **Parameters** (lookback 60, abs_tol 10, rel_tol 0.20, trough_drop 0.50, trough_rise 10, trough_confirm 30, max_event 180) were fixed before seeing results. They are not tuned.
- **Reason:** the provisional recovery rule had no tolerance (return only at glucose <= baseline) and censored 42-58 % of reference windows at 180 min. That is stricter than the literature.

| ID | Topic | What we did | Source / reason |
|---|---|---|---|
| X1 | Rise gate (specification error) | Found during implementation, after seeing the first results. The original specification omitted the requirement that an excursion must first rise. Without it, 62 % of reference excursions (Route B) ended within 5 min of the logged meal start, before the rise. A return or trough now counts only once P(t) - b >= 10 mg/dL. Excursions that never rise 10 mg/dL within 180 min get end_type no_rise (end set to a + 180), separate from censored. | No new parameter: the gate reuses abs_tol = 10, which matches the Lim 2026 minimum PPGR rise. |
| X2 | no_rise in agreement | Pairs with no_rise at either anchor are left out of the recovery-time ICC only. Counts are reported per rule and anchor type. | User decision, 2026-10-01. |
| X3 | Trough as local minimum | t_m qualifies when glucose rises to >= m + 10 within (t_m, t_m + 30] without first going below m and without missing minutes. The earliest such minute after the peak is the local minimum. The confirmation may look past a + 180; the end stays <= a + 180. If return and trough fall on the same minute, the end type is returned. | Implementation of the specification. |
| X4 | trough_interrupted window | Detector anchor: raw detection in (t_m, t_m + 30]. Reference anchor: logged food entry (any type, entries not merged) in [t_m - 30, t_m + 30]. The anchor meal's own entries are not excluded. This label was rare (0.6 % of reference pairs, Route B). | Specification taken literally. |
| X5 | Merge rule details | excursion_end merges detections before the end into the anchor; a detection at or after the end opens a new excursion. It runs per participant-day like the other rules (see Harvey deviations BR4). A no_rise detector event would close at a + 180; none occurred among TP pairs. | Same structure as baseline_return. |
| X6 | Fall requirement (second post-result fix) | Found after seeing the results of the rise-gate run. A rise just over 10 mg/dL followed by a 1 mg/dL dip still counted as a return, because the gate and the return tolerance were both b + 10. Any end (return or trough) now also needs P(t) - glucose(t) >= trough_drop * (P(t) - b), with trough_drop = 0.50. | No new parameter: reuses trough_drop. Reason: an end must be a real fall from the peak, not sensor noise at the tolerance edge. |

**Frozen (2026-10-01):** the excursion definition is frozen after X6. Any later change goes to sensitivity analyses only.

## Y. Main adjacent rule check: excursion_end vs refractory (2026-10-01)

- **What:** a one-off check to choose the main adjacent rule (`methods/harvey/results/rule_check/`, script `methods/harvey/src/run_rule_check.py`). No rule, no excursion parameter and no earlier result was changed.
- **Pre-set criteria** (fixed before running, not changed after). Choose excursion_end as main if any holds on Route B; otherwise refractory.
  - C1: >= 10 % of refractory-kept events start inside an ongoing excursion.
  - C2: the C1 percentage differs by >= 5 pp between any two groups.
  - C3: events per participant-day differ by >= 10 % between the rules within at least one group, and the direction or size of that difference is not the same across groups.
- **Operationalisation of C3** (written before results): group means of events per participant-day (07:00 to 21:59 onsets, all evaluated days, zero days included); d_g = % difference excursion_end vs refractory. Met if max abs(d_g) >= 10 and (signs differ or spread >= 5 pp).
- **Outcome (Route B, main analysis):** C1 not met (2.9 % split). C2 met narrowly (range 5.2 pp: healthy 0.8, prediabetes 1.7, T2D 6.0). C3 met (d_g healthy +32.5 %, prediabetes +20.7 %, T2D +9.4 %; spread 23.1 pp). Choice: excursion_end is the main rule. Route A (secondary): C1 and C2 not met, C3 met.
- **Superseded:** the main rule was later set to refractory by decision, against this outcome. See section Z1 (2026-10-05).

## Z. Protocol decisions for new methods (2026-10-05)

These decisions set the standard protocol (`[protocol]` in `common/configs/cgmacros_eval.toml`, runner `common/evaluation/protocol.py`, command `common/run_protocol.py <method>`). Earlier config keys are unchanged, so every earlier run still reproduces.

| ID | Decision | Reason / note |
|---|---|---|
| Z1 | Main adjacent rule = refractory (120 min). Decided after the rule check in section Y, which favoured excursion_end. This overrides the pre-set criteria of section Y. | False positives become extra events in event-level features, and excursion_end has much lower precision (Route B: 71.5 % vs 80.5 %; FP/day 0.61 vs 0.36; healthy precision 64.9 % vs 80.2 %). Known cost: refractory removed 27 detections after the blocking excursion had already ended, and gives about 25 % fewer events per day in healthy participants. |
| Z2 | tp_lockout (Hochsmann 2026) is kept as a comparison only. It runs with our matching rule and with the review rule (0 to +120 min), for comparison with Hochsmann 2026 Table 2. | It uses meal labels, so it cannot run on AI-READI. |
| Z3 | excursion_end, baseline_return and meal_window_max_peak are not run for new methods. | Their Harvey results (`methods/harvey/results/peak_rules/`, `excursion_v2/`) stay as a record. |
| Z4 | Route B only for new methods (5 participant folds plus the all_participants set). | PhD mentor decision, 2026-10-05. Harvey Route A results stay as a record. |
| Z5 | Recovery features for new methods use segmentation = "excursion". | The frozen shared definition (section X). |
| Z6 | **Added 2026-10-06.** Pellizzari 2025 TMA is excluded from the standard protocol and from `results/method_comparison.md`. Its earlier results in `methods/pellizzari2025_tma/results/` are kept as a record. | TMA needs training: each template and its threshold are learned from labelled meals (persTMA per participant, popTMA from the other participants). The project compares only methods that need no training on meal labels (plan section 5: "All methods are training-free"; Kolle-Ra and Kolle-CGM were excluded for the same reason). The earlier TMA runs also used an older evaluation setup, so they are not comparable. |

Check: Harvey run through the new runner (`methods/harvey/results/protocol_v1/`) gives Route B refractory and tp_lockout (our matching rule) results identical to `excursion_v2/` (summary, recovery agreement, parameters and row-level tables; `methods/harvey/src/check_protocol_v1.py`).
