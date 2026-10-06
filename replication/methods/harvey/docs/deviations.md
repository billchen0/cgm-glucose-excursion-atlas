# Harvey (GRID) deviations and defaults

Framework-level deviations (E1-E17, R1-R8) and the source list are in common/docs/deviations.md;
this file holds the Harvey-specific entries. Rules follow
**docs/evaluation_plan_v3.md**.

## H. Harvey (GRID)

| ID | Topic | What we did | Source / reason |
|---|---|---|---|
| H1 | Noise-spike filter | Clip the step from the previous spike-filtered value to +/- dG, with dG = 3 mg/dL per minute x sampling period = 15 mg/dL per 5-min sample. | The review (Supp. lines 67-69) names the filter without its parameter. Harvey 2014 p. 308, Eq. 1: "maximum allowable ROC, set to 3 mg/dL in a 1-minute period". Scaling it to the 5-min period is our reading. |
| H2 | Low-pass filter | GF(k) = dt/(tau_F+dt)*GF_NS(k) + (1 - dt/(tau_F+dt))*GF(k-1), with dt = 5 min. | Review names "a low-pass filter with time constant tau_F" (Supp. line 69). The formula is Harvey 2014 p. 308, Eq. 2. |
| H3 | Filter initialisation and missing data | Both filters start at the first reading of each run of consecutive readings, and restart after any missing sample. The ROC needs 3 samples of the run. The detector runs on one calendar day (00:00-23:55), so filter state does not carry over from the previous day. The restart at 00:00 falls inside the night block-out. | Default. Not stated in the review or Harvey 2014. |
| H4 | Detection event | GRID+ (Eq. 8) is a per-sample flag. A detection is the first sample of each run of GRID+ = 1 (rising edge). There is no detector-level refractory period: repeated detections after a TP are handled by the evaluation lockout. | Default. The review returns "detected meal onset times" but does not say how per-sample flags become events. Harvey 2014 Fig. 1 starts a treatment protocol at detection and has no refractory period. |
| H5 | ROC | Derivative of the 3-point Lagrange polynomial through k-2, k-1, k, evaluated at k, using actual sample times. | Review Supp. line 70. Formula from Harvey 2014 p. 308, Eq. 3. |
| H6 | Decision rule | GF(k) > G_min and (all of G'F(k-2..k) > G'_min,3 or all of G'F(k-1..k) > G'_min,2), with strict ">". | Review Supp. Table 1 Eq. 8 = Harvey 2014 Eq. 4. |
| H7 | Grid | G_min 100:5:140 mg/dL; G'_min,3 and G'_min,2 0.8:0.1:1.8 mg/dL/min; tau_F 4:1:8 min (5,445 points). | Review Supp. Table 1 Eq. 8. |
| H8 | Sampling | Native Dexcom 5-min readings. The review resampled 1-min Libre 2 data to 5 min (Methods, "Algorithm implementation"). | E1. |
| H9 | Tuning | Route A (per participant) matches the review ("tuned individually for each participant", Supp. lines 76-77). Route B (one global set) is a project addition (plan 6.1). Harvey 2014 itself used one population set (tau_F = 6, G_min = 130, G'_min,3 = 1.5, G'_min,2 = 1.6). | Plan 6.1. |
| H10 | Grid edge | The review reports G'_min,3 = 0.8 +/- 0.1, which is at the lower grid edge in the review itself. Parameters that land on a grid edge are flagged in `methods/harvey/results/reference_tp_lockout/chosen_params_*.json`. | Hochsmann 2026 Table 1. |
| H11 | G'_min,3 identifiability | When G'_min,2 <= G'_min,3, "last 3 ROC > G'_min,3" implies "last 2 ROC > G'_min,2", so G'_min,3 has no effect. Route B selects G'_min,2 = 0.8. All 11 G'_min,3 values then tie, and the reported 0.8 comes from grid order. The same happens for any participant with G'_min,2 = 0.8. | A property of Eq. 8 on this grid. The review's reported G'_min,3 = 0.8 +/- 0.1 may reflect the same effect (its tie-break beyond FP/day and delta t is not stated). |

## R7 (Harvey counts)

Moved from common/docs/deviations.md R7: A kept 06:00-06:59 breakfast-window detection is therefore not scored, and it still displaces later breakfast-window detections: 13 in Route A, 30 in Route B.

## Differences from the evaluation plan (v3)

- **2.2 Sampling.** The plan takes every fifth 1-min sample. We use the fifth samples on the native Dexcom phase (E1). This is the same data, with the phase made explicit.
- **2.4 rule 4.** "[7 or 8 valid days]" is set to 7 (user decision): 42 participants, 333 days, 666 meals. This reproduces plan table 2.6 exactly.
- **3 / 4 Ground truth and window.** Snacks are not ground truth, and they are also not masked inside the scoring window (E5). Meals before 07:00 whose TP window ends before 07:00 are not scored (E3). One day has no scoring window (E16).
- **7 FP/day denominator** ("[Decide from data]"). Scored days is primary, FP per scored hour is secondary (user decision).
- **7.1 Adjacent peaks** ("[not sure]"). Reference: 120-min lockout after each TP (user decision). The plan's third option (one detection per meal window, highest peak) is the main label-free rule in methods/harvey/results/peak_rules/, with a 120-min refractory as a sensitivity rule (R1-R8). The plan's second option (merge unless glucose returns to baseline) is not implemented. The lockout ignores many detections: 125 in Route A and 300 in Route B ("ours" rule).
- **8 Segmentation** ("[Decide from data]"). PROVISIONAL rule (E9). Recovery to baseline within 180 min fails for about half of the reference windows, so recovery time is often cap-censored.
- **8 Metrics.** ICC and Bland-Altman have no CI (the plan asks for bootstrap CIs at detection level only).
- **6.1 Route B as the locked detector.** The review grid is too narrow for global tuning on CGMacros. Every fold lands on the permissive corner. Locking the all-participant set for AI-READI would lock a grid-edge solution. The plan (9) says rules change only on development data, so extending the grid is a decision for review, not something done here.
- **9 Review rules.** The review's afternoon suppression is not applied in the "review" rule run (E14).

## Adjacent rule baseline_return (added 2026-10-01)

- **Added:** 2026-10-01, as `adjacent_rule = "baseline_return"` (`common/evaluation/postprocess.py`). Results in `methods/harvey/results/peak_rules/baseline_return/`.
- **Fixed in advance:** the rule and its four parameters (lookback 60 min, abs_tol 10 mg/dL, rel_tol 0.20, max_event 180 min) were fixed before running any further methods. They are not tuned.
- **Reason:** recovery features are defined at the level of the whole-day event, so the adjacent rule should follow the recovery logic. Two detections belong to the same excursion unless glucose returns near baseline between them.
- **Role:** candidate main rule, pending mentor confirmation. tp_lockout is reference only. meal_window_max_peak and refractory are sensitivity analyses.

| ID | Topic | What we did | Source / reason |
|---|---|---|---|
| BR1 | Definition | Anchor d0 = first detection of an event. b = min 1-min glucose in [d0 - 60, d0]. P(t) = max glucose in (d0, t]. Close at the first minute t after the time of P(t) with glucose(t) <= b + max(10, 0.20 * (P(t) - b)). Not closed by d0 + 180: close at d0 + 180, flagged censored. Missing minutes never close an event. Detections before the close are removed (merged into the anchor). | User specification, 2026-10-01. |
| BR2 | Fallback baseline | The window [d0 - 60, d0] contains d0, which always has data, so read literally the fallback never triggers. We flag fallback when [d0 - 60, d0) has no valid data; then b = glucose at d0, which equals the window minimum anyway. It was never used (0.0 % of events). | Interpretation of the specification. |
| BR3 | Boundaries | "After the time of P(t)" is strict: the minute that sets a new peak cannot close the event. If P has ties, the first time counts. A detection exactly at the closing minute opens a new event. | Default. |
| BR4 | Processing unit | Rules run per participant-day (00:00-23:55), as the detector does. An event's glucose is followed past midnight, but next-day detections are not merged into it. Any event anchored before midnight closes by 03:00, and scoring starts at 07:00, so this cannot change a scored detection. It can only change how unscored night detections are counted as removed. | Default, consistent with the grid search. The specification says "each participant's detections in time order". |
| BR5 | Recovery features | Unchanged and PROVISIONAL (E9), so the ICC is comparable across rules. Their baseline (mean in [anchor - 30, anchor)) differs from the BR1 baseline. | User specification. |

## Shared excursion definition and excursion_end (added 2026-10-01)

- **Unified:** the baseline and excursion end are now one shared definition. End = return or confirmed trough or 180-min censor. Peak = max in (a, end]. The completeness window is unchanged. Full entry: common/docs/deviations.md, section X.
- **Parameters** were fixed before seeing results. Reason: the provisional recovery rule had no tolerance and censored 42-58 % of reference windows, stricter than the literature.
- **Specification error found after the first run:** the specification omitted that an excursion must first rise. In the first Harvey run, 62 % of reference excursions (Route B, excursion_end pairs) ended within 5 min of the meal start, 70 % within 15 min, and recovery-time ICC fell to 0.12-0.19. A 10 mg/dL rise gate was added (reusing abs_tol, which matches the Lim 2026 minimum PPGR rise). After the gate, 6 % ended within 15 min.
- **New rule `excursion_end`** (candidate main). tp_lockout stays reference only; refractory and meal_window_max_peak are sensitivity analyses. baseline_return results in peak_rules/ are kept as they are.
- **Outputs:** methods/harvey/results/excursion_v2/. Detection metrics of tp_lockout, meal_window_max_peak and refractory equal peak_rules/ exactly; only the recovery features changed.
- **Second post-result fix (fall requirement):** after the rise gate, 6.6 % of reference excursions that rose still ended within 15 min (Route B), from a 1 mg/dL dip right at the b + 10 tolerance. Any end now also needs a fall of >= 0.50 of the rise from the running peak (reuses trough_drop). After the fix: 2.4 %. excursion_end detections changed slightly on Route B (FP 207 to 204, precision 71.2 to 71.5 %). Route A is unchanged. Details: common/docs/deviations.md X6.
- **Frozen:** the excursion definition is frozen after this change. Any later change goes to sensitivity analyses only.
