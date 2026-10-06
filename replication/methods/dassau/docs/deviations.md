# Dassau 2-of-3 and 3-of-4: deviations and defaults

Framework entries (E, R, X, Y, Z) are in common/docs/deviations.md. The standard protocol
(refractory main, tp_lockout comparison, Route B, excursion segmentation) is section Z there.
Rules follow **docs/evaluation_plan_v3.md**.

> Commit hashes in this file refer to the archived local repository (tag `archive-before-atlas-import`); see `docs/prespecification_log.md` for the order of commits.

## Source

- The original paper (Dassau E et al. Diabetes Care 2008;31(2):295-300) is not available to us (abstract only).
- The only spec is Hochsmann 2026: Supplementary Methods "Algorithms by Dassau et al." (lines 36-54) and Supplementary Table 1, Equations 1-6 (Supplement pp. 8-9).
- Anything the review does not state is a default (D5-D8, D10). Each is listed below.

## Equations as printed (Hochsmann 2026 Supplementary Table 1)

Transcribed from the PDF images (Supplement pp. 8-9). Plain-text notation: `&` = logical and, `1{...}` = indicator.

```
Eq. 1  BD(i)  = 1, if BD_raw(i) > Threshold_ROC
                0, otherwise
       where Threshold_ROC in {1.0, 1.1, 1.2, ..., 3.0} mg/dL/min

Eq. 2  BDK(i) = 1, if BD_Kalman(i) > Threshold_ROC
                0, otherwise
       where Threshold_ROC in {1.0, 1.1, 1.2, ..., 3.0} mg/dL/min

Eq. 3  KF(i)  = 1, if G'_Kalman(i) > Threshold_ROC
                     & G'_Kalman(i) < Threshold_maxROC
                     & G_Kalman(i)  > Threshold_Glucose
                0, otherwise
       where Threshold_ROC     in {1.0, 1.1, 1.2, ..., 3.0} mg/dL/min,
             Threshold_maxROC  in {2, 3, 4, 5} mg/dL/min
             Threshold_Glucose in {100, 110, ..., 200} mg/dL/min      [sic: unit printed as mg/dL/min]

Eq. 4  ACC(i) = 1, if G''_Kalman(i) > Threshold_Acceleration
                0, otherwise
       where Threshold_Acceleration in {0.2, 0.3, ..., 0.8} mg/dL/min^2

Eq. 5  MDA_Dassau_2of3(i) = 1, if sum_{j=0}^{4} 1{BD(i+j) + BDK(i+j) + ACC(i+j) >= 2} = 5
                            0, otherwise

Eq. 6  MDA_Dassau_3of4(i) = 1, if sum_{j=0}^{4} 1{BD(i+j) + BDK(i+j) + KF(i+j) + ACC(i+j) >= 3} = 5
                            0, otherwise
```

Supplementary Methods text (lines 39-54, paraphrased): indicators are computed at each 1-min sample;
2-of-3 declares a meal when at least two of BD, BDK, ACC are true "within a 5-minute window of
consecutive samples (i, ..., i + 4)"; 3-of-4 when any three of the four are "simultaneously true
throughout the same 5-minute window"; both run at 1-min sampling; thresholds were tuned per participant.

Hochsmann 2026 main text, Table 1 (tuned, mean +/- SD over participants):

| Detector | Threshold_Glucose | Threshold_maxROC | Threshold_ROC | Threshold_Acceleration |
|---|---|---|---|---|
| 2-of-3 | 103.8 +/- 5.0 | 2.69 +/- 0.7 | 1.18 +/- 0.24 | not reported |
| 3-of-4 | 100.6 +/- 2.5 | 3.94 +/- 0.77 | 1.01 +/- 0.03 | 0.21 +/- 0.03 |

Table 2 (test set, review rule, tp_lockout): 2-of-3 Sens 72.2 %, FP/day 0.60, delta t 37.6 min; 3-of-4 Sens 49.1 %, FP/day 0.12, delta t 36.8 min.

## D. Dassau

| ID | Topic | What we did | Source / reason |
|---|---|---|---|
| D1 | Spec source | Hochsmann 2026 equations only. Details of the original (its Kalman model, its 15-20 min post-meal and night detection lockouts, its glucose thresholds of 150-220 mg/dL) are unknown or not used. | Original paper not available. The lockouts and thresholds are quoted in Hochsmann Supp. Table 2 and main text. |
| D2 | Table 1 vs the 2-of-3 rule | Table 1 lists Threshold_Glucose, Threshold_maxROC and Threshold_ROC for 2-of-3. Eq. 5 uses BD, BDK and ACC only. BD and BDK use Threshold_ROC (Eqs. 1, 2). ACC uses Threshold_Acceleration (Eq. 4). Threshold_Glucose and Threshold_maxROC appear only in KF (Eq. 3), which Eq. 5 does not use. Threshold_Acceleration, which Eq. 5 needs, is not reported. We implement Eq. 5 as written and tune Threshold_ROC and Threshold_Acceleration (147 points). For 3-of-4, Table 1 and Eq. 6 agree (all four thresholds). | Plan v3 section 5: "We implement the equation as written." |
| D3 | 5-min window | Eq. 5 requires the vote at every sample i, ..., i+4 (the sum of five indicators must equal 5). The 2-of-3 text says "within a 5-minute window", which could mean at any sample. We follow Eq. 5. The same window applies to 3-of-4 (Eq. 6 and its text agree). | Equation over text. |
| D4 | Detection time | MDA(i) needs samples up to i+4. The detection is the first i of each run of MDA = 1 (rising edge), reported at t(i), as the equations index it. In real time the decision is available 4 min later, at t(i+4). All delays would be 4 min longer; a detection near a window bound could change status. | Task rule: follow the equations and log it. Same rising-edge rule as Harvey (H4). |
| D5 | Backward difference | "Three-point backward difference" = (3 g(i) - 4 g(i-1) + g(i-2)) / (2 dt), dt = 1 min, on the raw series (BD_raw) and on the Kalman glucose estimate (BD_Kalman). It is undefined if any of the three samples is missing. | Default. The review names the method without a formula. This is the standard second-order formula, the same as Harvey's Lagrange derivative at the end point. |
| D6 | Kalman filter | Constant-acceleration model, state [G, G', G''], glucose measured. Discretised white-noise jerk with PSD q = 2.0e-4 (mg/dL)^2/min^5. Measurement noise SD 3 mg/dL. Start and restart after any missing sample: x = [g, 0, 0], P = diag(9, 1, 0.01). Outputs unused for the first 10 min after each (re)start (warm-up). Code: common/evaluation/kalman.py, settings `[kalman.dassau]`. | Default; the review states no model or noise settings. A 3-state model is the smallest that gives the G, G' and G'' that Eqs. 3-4 need. Measurement SD 3 mg/dL is a typical CGM noise level. q was chosen by a criterion fixed before any CGMacros run: the fastest filter for which white sensor noise alone gives a ROC SD <= 0.25 mg/dL/min and an acceleration SD <= 0.05 mg/dL/min^2 (1/4 of the lowest Threshold_ROC and Threshold_Acceleration). Result: 0.243 and 0.020; a ramp of 2 mg/dL/min reaches 90 % of its rate in about 9 min. Committed before running (f7a211f). |
| D7 | Raw series | QC'd 1-min series (plan 2.2). CGMacros 1-min Dexcom values are linear interpolations of the native 5-min readings (E1), plus interpolation of gaps <= 30 min (E2). BD_raw is therefore the slope of the current 5-min segment except at its knots, and sensor noise is correlated over 5 min (the Kalman white-noise assumption does not hold). Hochsmann used 1-min Libre 2 data. | Plan 2.2 and the task. |
| D8 | Missing data and day boundaries | Comparisons with a missing value are false, so a window that touches a missing sample cannot vote. The detector runs per participant-day (00:00-23:59), as Harvey does (H3). The filter restarts at 00:00, inside the night block-out. The last 4 samples of a day cannot complete a window. | Default. |
| D9 | Grid | Exactly as Supplementary Table 1. 2-of-3: Threshold_ROC 1.0:0.1:3.0, Threshold_Acceleration 0.2:0.1:0.8 (147 points). 3-of-4: Threshold_Glucose 100:10:200 mg/dL, Threshold_maxROC 2:1:5, Threshold_ROC 1.0:0.1:3.0, Threshold_Acceleration 0.2:0.1:0.8 (6,468 points). Every range is stated, so none was added. Tie-break grid order: the parameter order above, ascending. Strict inequalities as printed. Grid fixed before running (f7a211f). | Hochsmann Supp. Table 1. The Threshold_Glucose unit is printed as mg/dL/min; we read mg/dL. |
| D10 | No detector-level lockout | The original's 15-20 min post-detection lockout is not in Eqs. 5-6 and is not applied. Repeated detections are handled by the protocol's adjacent rule (refractory 120 min) or by tp_lockout. | Hochsmann Supp. Table 2 lists the lockout for the original only. |
| D11 | Tuning | Route B, one global set per fold (Z4). The review tuned per participant. | common/docs/deviations.md Z4. |
| D12 | detect_grid | Signals are computed once per day; thresholds are broadcast over the grid. Tested equal to `detect` on 40 random grid points x 8 days per detector (tests/test_dassau.py). | Speed (the 3-of-4 grid has 6,468 points). |

## Findings after the run (2026-10-05, nothing changed)

- **ACC is rarely true.** With the D6 filter, the Kalman acceleration exceeds 0.2 mg/dL/min^2 at 1.6 % of the 07:00-22:00 samples, 0.3 at 0.3 %, and 0.5 at 0.01 % (99.9th percentile 0.36). The upper part of the Threshold_Acceleration grid has almost no effect. In practice 2-of-3 is close to "BD and BDK" and 3-of-4 to "BD, BDK and KF". This depends on the unstated Kalman settings. Hochsmann's 3-of-4 also chose the lowest values (0.21 +/- 0.03).
- **Grid edges.** Both detectors tune to the permissive corner: Threshold_ROC = 1.0 in almost every Route B set, Threshold_Glucose = 100 in every 3-of-4 set (Hochsmann: 100.6 +/- 2.5). The review also notes that 3-of-4 sat at its grid boundary. The grid was not extended (fixed before running).
- **3-of-4 vs Hochsmann.** tp_lockout with the review rule gives Sens 73.9 % vs 49.1 % in Hochsmann Table 2 (24.8 pp, just under the 25 pp stop line). 2-of-3: 81.4 % vs 72.2 % (9.2 pp). Not like-for-like: cohort, sensor, scored meals, scoring window, Route B global tuning and the Kalman defaults all differ.
- **Strictness.** 3-of-4 is stricter than 2-of-3, as expected (Route B, refractory: Sens 71.7 vs 74.4 %, FP/day 0.30 vs 0.56). At equal Threshold_ROC and Threshold_Acceleration, a 3-of-4 flag always implies a 2-of-3 flag (tested).
- **Single bad reading.** One +20 mg/dL Dexcom reading (a 10-min triangle in the 1-min series) triggers 2-of-3 at Threshold_ROC 1.0 but not 3-of-4 (tests).
- Spot check (`results/spot_check.md`): one day per group, indicators around every detection. The flags agree with Eqs. 1-6.
