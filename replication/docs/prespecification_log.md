# Pre-specification log

This table shows the order of decisions: which settings were committed before which results.

**The hashes refer to the archived local repository** (git tag `archive-before-atlas-import`).
The import into the cgm-glucose-excursion-atlas repository is a single squashed commit, so these
hashes do not exist there. Dates are commit times (local time).

A detector commit "before the first CGMacros run" holds the detector code, its config and grid,
and its tests. The tests only use synthetic data and up to 10 real days without meal labels or
scores (to check the fast path and numerical stability).

## Shared framework and decisions

| Hash | Date | What |
|---|---|---|
| 3cc3cdf | 2026-09-29 11:46 | Cohort flow v3 (QC per evaluation plan v3). |
| 4ef222d | 2026-09-29 11:53 | Evaluation framework: config, cohort, scoring windows and matching. |
| dc319bc | 2026-09-29 11:55 | Tuning: grid scoring, Route A day split, Route B stratified 5-fold CV. |
| 91a7d13 | 2026-09-29 11:58 | Metrics: bootstrap CIs, recovery features, ICC(A,1), Bland-Altman. |
| 30cb6e2 | 2026-10-01 13:16 | baseline_return adjacent rule, parameters fixed in advance. |
| 492c238 | 2026-10-01 14:00 | Shared excursion definition (with the rise gate, a fix found after the first run; deviations X1). |
| f888bf4 | 2026-10-01 14:11 | Excursion definition: fall requirement (second fix, X6) and **definition frozen**. |
| d01982d | 2026-10-01 16:50 | Rule check excursion_end vs refractory: pre-set criteria and result (deviations section Y). The criteria text and the result were committed together; the criteria are quoted in `methods/harvey/src/run_rule_check.py`. |
| ced31db | 2026-10-05 18:33 | Shared protocol runner (`[protocol]`, `common/run_protocol.py`). |
| 7dc4681 | 2026-10-05 18:33 | Harvey through the runner: identical to excursion_v2 (check). |
| 8e19f83 | 2026-10-05 18:33 | Decision record, deviations section Z: refractory main (Z1, overrides Y), tp_lockout comparison only (Z2), other rules a record (Z3), Route B only (Z4), excursion segmentation (Z5). |
| bf04ec3 | 2026-10-06 13:45 | Decision record Z6: TMA excluded (needs training). |

## Methods: settings committed before results

| Method | Settings committed | Results committed | Notes |
|---|---|---|---|
| Harvey GRID | 5a171b7 (2026-09-29 11:54) | 213c0d9 (12:02) | First run, Route A and B. |
| Dassau 2-of-3, 3-of-4 | f7a211f (2026-10-05 19:00) | b3a94f3 (19:07) | Detectors, grid, Kalman defaults. |
| Samadi IGT | d50a4ba (2026-10-05 19:13) | 2f96105 (19:18) | Membership defaults. |
| Faccioli STMD | feda1a4 (2026-10-05 20:41) | 4e21fba (21:30), first run as `protocol_v1_nightgain/` | Night gain rule (F5a). The first run gave Sens about 20 %; it was reported before any change. |
| Faccioli STMD, L grid | 4e21fba (2026-10-05 21:30) | 08158da (21:36) | Observer bound L as a grid parameter (F5b), decided after the first result and committed before the second run. |
| Turksoy UKF | 7ee4b07 (2026-10-05 22:41) | ef98007 (22:51) | UKF settings and defaults. |
| Turksoy UKF, stability fix | 1d358a7 (2026-10-05 22:43) | ef98007 (22:51) | Sigma points clipped before propagation (T7b); the first run attempt crashed before producing any result. |
| Popp SBE | 850db97, 4152448 (2026-10-05 23:58) | 2b48e32 (2026-10-06 00:07) | Model source and anchoring default. |
| Lim wavelet PPGR | 7d2a6d1, 160f225 (2026-10-06 00:25) | eb8e4e8 (00:35) | Wavelet scale calibrated on Lim Fig. 1, not on CGMacros. |

## Other runner changes made with the methods

| Hash | Date | What |
|---|---|---|
| dac964b | 2026-10-05 21:28 | Export check counts every participant (earlier exports re-exported unchanged). |
| 74e166d | 2026-10-05 21:36 | README writer lists uneven grid values. |
| cf30ffe | 2026-10-06 00:35 | README writer shows a fixed grid value as the value. |
