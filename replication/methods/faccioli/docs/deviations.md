# Faccioli (super-twisting meal detector): deviations and defaults

Framework entries (E, R, X, Y, Z) are in common/docs/deviations.md. The standard protocol
(refractory main, tp_lockout comparison, Route B, excursion segmentation) is section Z there.
Rules follow **docs/evaluation_plan_v3.md** (section 5 note: "Observer gain
tuning procedure not stated").

> Commit hashes in this file refer to the archived local repository (tag `archive-before-atlas-import`); see `docs/prespecification_log.md` for the order of commits.

## Sources

- Hochsmann 2026: Supplementary Methods "Algorithm by Faccioli et al." (lines 55-65) and Supplementary Table 1, Equation 7 (Supplement p. 9).
- Original: Faccioli S, Sala-Mira I, Diez JL, et al. Comput Methods Programs Biomed 2022;219:106736 (https://doi.org/10.1016/j.cmpb.2022.106736). Two local copies of the paper were compared; only the download stamp differs. It gives the observer (Eqs. 1-8), the gain rule (Sec. 3.1), the Kalman filter (Eqs. 9-12) and the decision rules (Sec. 2.1.3).
- The earlier STMD paper (Sala-Mira I et al. J Process Control 2019;78:68-77, https://doi.org/10.1016/j.jprocont.2019.03.008; Faccioli's ref. 15) was not available to us. It was not needed: Faccioli 2022 restates everything used here.

## Equation as printed (Hochsmann 2026 Supplementary Table 1)

Transcribed from the PDF image (Supplement p. 9).

```
Eq. 7  MDA_Faccioli(i) = 1, if Res(i) > Th_Res & dG_hat(i) > Th_Der
                         0, otherwise
       where Th_Res in {1.0, 1.1, ..., 4.0} mg/dL
             Th_Der in {0.2, 0.3, 0.4, 0.5} mg/dL/min
```

dG_hat is printed as G with a dot and a hat (the Kalman estimate of the glucose derivative).
Supplementary Methods (lines 56-65, paraphrased): a super-twisting observer generates Res(i) at
each CGM sample; the derivative is estimated by a Kalman filter; a meal is declared when both
exceed participant-specific thresholds. "In contrast to the original implementation, observer gain
was tuned separately for each day, and a 3-point median filter was applied to reduce CGM noise
before processing." Thresholds were tuned per participant on the validation set.

Hochsmann 2026 Table 1 (tuned per participant): Th_Der = 0.23 +/- 0.11, Th_Res = 1.25 +/- 0.54, F2 0.82 +/- 0.09.
Table 2 (test set, review rule, tp_lockout): TP 139, FP 100, FN 77, Sens 64.4 %, FP/day 1.39, delta t 39.6 min.
Faccioli 2022 Table 2 (30 T1D adults, free-living, 180-min TP window, median [IQR]): recall 70 [13] %, precision 73 [26] %, FP/day 1.4 [1.4], detection time 45 [45] min. Its chosen Th_Res and Th_Der are shown only in its Fig. 3, not as numbers.

## Observer and Kalman filter (Faccioli 2022)

- Continuous observer (Eq. 1): d(ig_hat)/dt = u + k1 |res|^0.5 sign(res), du/dt = k2 sign(res), res = ig - ig_hat. Gains (Eq. 3): k1 = 1.5 L^0.5, k2 = 1.1 L, with L the bound on the lumped disturbance F.
- Implicit discretisation (Eq. 4): cgm_ST(k) - cgm_ST(k-1) = h u(k) + h k1 |res(k)|^0.5 lambda(k), u(k) - u(k-1) = h k2 lambda(k), lambda(k) in msign(res(k)) (set-valued sign, Eq. 5).
- Disturbance estimate (Eq. 8): F_hat(k) = (h / tau) (k2 sign(res(k-1)) - F_hat(k-1)) + F_hat(k-1), tau = 5 min.
- Gain rule (Sec. 3.1): personalised L = maximum F_hat(k) over each patient's first night.
- Kalman filter (Eqs. 9-12): per-sample model A = [[1, 1, 0], [0, 1, 1], [0, 0, 1]], C = [0, 0, 1]', G = [1, 0, 0]; Q = sigma_w^2 = 0.01, R = sigma_v^2 = 4.
- Decision (Sec. 2.1.3): res(k) > Th_Res and der(k) > Th_Der; detections at least TW_shut = 90 min apart; detection silenced for 30 min after a calibration.

## F. Faccioli

| ID | Topic | What we did | Source / reason |
|---|---|---|---|
| F1 | CGM only | The observer (Eq. 1) has no insulin input: F lumps meals and every other disturbance. Nothing was removed or set to zero. Insulin appears in Faccioli 2022 only through the clinical setting (SAP therapy), not in the detector. | Faccioli 2022 Eqs. 1-2. |
| F2 | Sampling | Native 5-min Dexcom readings (E1). h = 5 min. | Plan 2.2; Hochsmann and Faccioli used 5 min. |
| F3 | Median filter | Causal 3-point median, cgm(k) = median(g(k-2), g(k-1), g(k)), applied before the observer, the Kalman filter and the night gain rule. Missing if any of the three is missing. A single-sample spike is removed (tests). | Hochsmann line 64 gives the filter, not its alignment. Causal keeps the detector real-time; it adds up to one sample of lag. |
| F4 | Implicit observer | The printed Eq. 6 (closed form of Eq. 4) did not survive text extraction, so we re-derived it from Eq. 4: with g = cgm_ST(k-1) + h u(k-1) and e = cgm(k) - g, if abs(e) <= h^2 k2 then res = 0 and lambda = e / (h^2 k2); otherwise s = (h k1 / 2)(sqrt(1 + 4 (abs(e) - h^2 k2) / (h k1)^2) - 1), res = sign(e) s^2, lambda = sign(e). The test checks Eq. 4 to 1e-15. Start and restart (after missing data): cgm_ST = cgm, u = 0, Res = 0. | Faccioli Eqs. 4-7. Initial state is a default. The restart transient can trigger a detection right after a restart (spot check: 00:24, not scored). |
| F5a | Gain rule, first run | L per participant-day = max F_hat(k) over the same day's 00:00-07:00 night. With h = tau = 5 min, Eq. 8 read literally gives F_hat(k) = k2 sign(res(k-1)), which is only 0 or +/- k2 and depends on L itself. We read sign as the set-valued sign the observer uses, lambda(k-1), so F_hat(k) = k2 lambda(k-1) = e(k-1) / h^2, computed with a non-saturating provisional gain (L = 1e6). Floor: L >= 0.02 mg/dL/min^2, so a flat night cannot give L = 0. Per day, not per patient, because Hochsmann tuned the gain per day and the detector runs per day. Label-free. | Faccioli Sec. 3.1 and Eq. 8; Hochsmann line 63. Interpretation and floor are defaults, fixed before the first run (feda1a4). |
| F5b | Gain, main run | L is a global grid parameter (`l_bound`), tuned with Th_Res and Th_Der on Route B. Values (mg/dL/min^2): 0.02, 0.0325, 0.0529, 0.0859, 0.14, 0.227, 0.369, 0.6 (8 log-spaced, 0.02 to 0.6) plus 0.28. Reason for the range: it covers the per-day night values of the first run (10th to 90th percentile 0.12 to 0.60, median 0.28) and the floor 0.02. | **Decided after seeing the first result** (user decision, 2026-10-05). This was the pre-written fallback (option 3 of the task). Grid fixed and committed before the second run (4e21fba). The locked L is a constant, so the detector still runs without labels. |
| F6 | Kalman filter | Faccioli's model and noise (Eqs. 11-12, sigma_w^2 = 0.01, sigma_v^2 = 4) in `common/evaluation/kalman.filter_faccioli`. Not stated, so defaults as Dassau D6 converted to per-sample units: x0 = [cgm, 0, 0], P0 = diag(4, 5^2, 2.5^2) (rate SD 1 mg/dL/min, second-derivative SD 0.1 mg/dL/min^2), restart after missing data, outputs unused for 2 samples (10 min). | Faccioli 2022 Sec. 2.1.2 (after its ref. 37). |
| F7 | Derivative unit | Faccioli's state model uses a time step of one sample, so its rate is in mg/dL per 5 min. dG = rate / 5, in mg/dL/min, to match Hochsmann's Th_Der unit. | Hochsmann prints Th_Der in mg/dL/min. |
| F8 | Not applied | TW_shut (90 min between detections) and the 30-min silencing after calibrations. Repeats are handled by the protocol's adjacent rule (refractory) or by tp_lockout, as for Dassau (D10). CGMacros gives no calibration times. | Task. |
| F9 | Missing data | QC interpolates gaps <= 30 min linearly (E2); Faccioli used a zero-order hold. Longer gaps reset the observer and the Kalman filter, as Faccioli resets the algorithm. The detector runs per participant-day (00:00-23:55). | E2; Faccioli Sec. 2.2.2. |
| F10 | Grid | Th_Res 1.0:0.1:4.0 mg/dL (31), Th_Der 0.2:0.1:0.5 mg/dL/min (4), exactly as Eq. 7. With L (F5b): 1,116 points. Tie-break grid order: Th_Res, Th_Der, L, ascending. | Hochsmann Supp. Table 1. |
| F11 | Detection and tuning | Rising edge of MDA = 1, as the other detectors. Route B, one global set per fold (Z4). Hochsmann tuned thresholds per participant; Faccioli tuned them on the population (F1 score). | Z4. |
| F12 | detect_grid | Kalman once per day, observer once per L value, thresholds broadcast. Tested equal to `detect` (night gain: all 124 points; grid gain: 150 random points; 10 days each). | Speed and a check of the fast path. |

## First run: night gain rule (results/protocol_v1_nightgain/)

- Route B, refractory: Sens 20.3 %, Prec 88.7 %, FP/day 0.05. tp_lockout, review rule: Sens 20.0 % vs 64.4 % in Hochsmann (44 pp, past the 25 pp stop line). The run was stopped and reported.
- Cause: the per-day night L had median 0.28 mg/dL/min^2 (10th to 90th percentile 0.12 to 0.60). That gives the observer a dead zone of about 7.7 mg/dL per 5-min step (h^2 k2 = 27.5 L). Only 25 % of meals pushed Res above 1 mg/dL within 120 min, and on 47 % of days Res never exceeded 1 mg/dL in daytime. Th_Der was not the limit (dG > 0.2 on 37 % of daytime samples).
- Reading: Faccioli's first-night rule does not transfer to this cohort. In T1D the meal disturbance is much larger than the night maximum; in CGMacros a night maximum over 84 samples is often as large as a meal's disturbance.
- Reproduce: `python methods/faccioli/src/run_nightgain.py` (identical CSV and JSON files to the first run).

## Findings after the main run (2026-10-05, nothing changed)

- **Detection.** Route B, refractory: Sens 77.7 %, Prec 69.1 %, F2 0.758, FP/day 0.69. tp_lockout, review rule: Sens 88.0 % vs 64.4 % in Hochsmann (23.6 pp, under the stop line), FP/day 1.07 vs 1.39.
- **Grid edges.** The tuning picks a very sensitive observer and the strictest derivative threshold. L: 0.0325 in 5 of 6 refractory sets and 0.02 (the lowest value) in fold_4; 0.02 in all tp_lockout (ours) sets. Th_Der: 0.5, the upper bound, in 5 of 6 refractory sets and all tp_lockout (ours) sets. Th_Res: 1.0, the lower bound, in 5 of 6 refractory sets. The best operating point may lie outside the Hochsmann grid (Th_Der > 0.5). The grid was not extended. Hochsmann's tuned values (Th_Der 0.23, Th_Res 1.25) are near the same lower Th_Res edge but far from the Th_Der upper edge.
- **Chosen L vs the night rule.** The tuned L (0.02 to 0.03) is 4 to 30 times smaller than the night-rule values. This is why the first run had so few detections.
- **Refractory vs tp_lockout (our matching rule).** As tuned: FP/day 0.69 vs 0.92 (-25 %), Sens 77.7 vs 90.9 %. At identical parameters (the tp_lockout sets): FP/day 0.74 vs 0.92 (-20 %), Sens 79.1 vs 90.9 %.
- Spot check (`results/spot_check.md`): one day per group, filtered glucose, dG, Res and the flags around every kept detection. The flags agree with Eq. 7.
