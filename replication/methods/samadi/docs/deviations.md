# Samadi (fuzzy-logic IGT): deviations and defaults

Framework entries (E, R, X, Y, Z) are in common/docs/deviations.md. The standard protocol
(refractory main, tp_lockout comparison, Route B, excursion segmentation) is section Z there.
Rules follow **docs/evaluation_plan_v3.md** (section 5 note: "Simplified rule
as in the review").

> Commit hashes in this file refer to the archived local repository (tag `archive-before-atlas-import`); see `docs/prespecification_log.md` for the order of commits.

## Sources

- Hochsmann 2026: Supplementary Methods "Algorithm by Samadi et al." (lines 119-133) and Supplementary Table 1, Equations 14-15 (Supplement p. 10).
- Original: Samadi S, Rashid M, Turksoy K, et al. Diabetes Technol Ther 2018;20(3):235-246 (https://doi.org/10.1089/dia.2017.0364). It gives the seven shapes (Fig. 2), their IGT values, the 5-min update, the 4-point quadratic fit and the role of gamma1 (p. 239).
- Samadi 2018 refers the membership functions and shape logic to Samadi 2017 (IEEE J Biomed Health Inform 21(3):619-627, https://doi.org/10.1109/JBHI.2017.2677953; its ref. 25) and Bakshi and Stephanopoulos 1994 (Comput Chem Eng 18(4):267-302, https://doi.org/10.1016/0098-1354(94)85028-3; its ref. 28). Neither was available to us. Membership shapes, the d2G scale and the fuzzy AND are therefore defaults (S3-S5).

## Equations as printed (Hochsmann 2026 Supplementary Table 1)

Transcribed from the PDF image (Supplement p. 10).

```
Eq. 14  IGT(i) = ( -3B(i) - 2F(i) - C(i) + A(i) + 2E(i) + 3D(i) )
                 / ( A(i) + B(i) + C(i) + D(i) + E(i) + F(i) + G(i) )

Eq. 15  MDA_Samadi(i) = 1, if IGT(i) > Threshold_act
                        0, otherwise
```

Supplementary Methods (lines 120-133, paraphrased): at each 5-min CGM sample a quadratic is fitted
to the four most recent glucose points and d1G(i), d2G(i) are computed. d1G gets fuzzy memberships
across negative, zero and positive values based on a slope gain gamma1. d2G decides accelerating or
decelerating. The memberships form seven shapes (B, F, C, G, A, E, D), strongly decreasing to
strongly increasing. IGT is their weighted average (Eq. 14). The activation, pause and deactivation
logic of Samadi et al. is omitted; a meal flag is raised when IGT(i) in [-3, 3] exceeds
Threshold_act (Eq. 15). Grid, tuned per participant: gamma1 in {1.00, 1.50, ..., 4.00},
Threshold_act in {1.0, 1.1, ..., 3.0}.

Samadi 2018 Fig. 2 (shapes by derivative signs):

| Shape | Name | d1G | d2G | IGT value |
|---|---|---|---|---|
| B | accelerating decrease | - | - | -3 |
| F | steady decrease | - | 0 | -2 |
| C | decelerating decrease | - | + | -1 |
| G | constant | 0 | (any) | 0 |
| A | decelerating increase | + | - | +1 |
| E | steady increase | + | 0 | +2 |
| D | accelerating increase | + | + | +3 |

Hochsmann 2026 Table 1 (tuned per participant): gamma1 = 1 +/- 1, Threshold_act = 1.33 +/- 0.49, F2 0.86 +/- 0.04.
Table 2 (test set, review rule, tp_lockout): TP 194, FP 174, FN 22, Sens 89.8 %, FP/day 2.42, delta t 58.5 min.
Supplementary Table 2 (original): TP window 120 min, no discrete lockout, Sens 94 % (meals) and 68 % (snacks), FP/day 1.05, delta t 34.8 min.

## S. Samadi

| ID | Topic | What we did | Source / reason |
|---|---|---|---|
| S1 | Simplified rule | MDA(i) = 1 if IGT(i) > Threshold_act (Eq. 15). The original's activation, pause and deactivation states (thresholds with hysteresis, safety rules, CHO estimation) are omitted. A detection is the first sample of each run of MDA = 1 (rising edge). With no hysteresis, IGT that crosses the threshold several times gives several detections. | Hochsmann Supplementary Methods lines 129-133; plan v3 section 5. Rising edge as Harvey (H4) and Dassau (D4). The equation is causal, so the detection time is t(i). |
| S2 | Quadratic fit | Least-squares quadratic through the four most recent 5-min samples (t = -15, -10, -5, 0 min). d1G = its slope and d2G = its second derivative, both at t = 0 (the newest sample). Missing if any of the four samples is missing. | Samadi 2018 p. 238-239 and Hochsmann line 122. Evaluating at the newest sample is our reading ("derivatives at each time step n"). |
| S3 | d1G memberships | Linear sets: positive = clip(d1G / gamma1, 0, 1), negative = clip(-d1G / gamma1, 0, 1), zero = 1 - positive - negative. Centres -gamma1, 0, +gamma1; they sum to 1. Units: mg/dL/min. | Samadi 2018 p. 239: gamma1 "defines the centers of the fuzzy sets for the (negative, zero, positive) sign of the first derivative"; larger gamma1 widens the zero set. Shape and unit are defaults (Samadi 2017 not available). Per-5-min units would make gamma1 = 1 equal 0.2 mg/dL/min. |
| S4 | d2G memberships | The same linear sets with centre gamma2 = gamma1 / 15 min (mg/dL/min^2): the acceleration that changes the slope by gamma1 across the 15-min fit window. gamma1 stays the only tuned shape parameter. | Default. Fig. 2 needs a sign (-, 0, +) for d2G, but neither Hochsmann nor Samadi 2018 gives its scale. Fixed before any CGMacros run (d50a4ba). |
| S5 | Shape memberships | Product of the two sign memberships: B = N1 N2, F = N1 Z2, C = N1 P2, A = P1 N2, E = P1 Z2, D = P1 P2, G = Z1 (constant, any d2G). The seven memberships sum to 1, so the Eq. 14 denominator is 1 and IGT is in [-3, 3]. | Default (product AND). Fig. 2 and the IGT values follow Samadi 2018 p. 237. |
| S6 | Sampling | Native 5-min Dexcom readings (every fifth sample of the QC'd 1-min series, on the native phase; E1), as Harvey. | Plan 2.2; Hochsmann resampled to 5 min for Samadi. |
| S7 | Grid | gamma1 1.0:0.5:4.0 (7), Threshold_act 1.0:0.1:3.0 (21), 147 points, exactly as stated. Tie-break order gamma1 then Threshold_act, ascending. Fixed before running (d50a4ba). | Hochsmann Supplementary Methods lines 132-133. |
| S8 | Convex-corner response | At a point where falling glucose levels off, the 4-point quadratic is convex and its end-point slope is positive, so the shape reads as D (accelerating increase). A single bad 5-min reading flags twice: at the spike and 15 min later, when it is the oldest fit point (tests). This is a property of the spec, not changed. | Found in the synthetic tests, before the CGMacros run. |
| S9 | Missing data | IGT is missing while any of the last four samples is missing, so no flag. The detector runs per participant-day (00:00-23:55). | Default, as Harvey (H3). |
| S10 | Tuning | Route B, one global set per fold (Z4). The review tuned per participant. | common/docs/deviations.md Z4. |
| S11 | detect_grid | Derivatives once per day, IGT once per gamma1, thresholds broadcast. Tested equal to `detect` on all 147 points x 10 days. | Speed and a check of the fast path. |

## Findings after the run (2026-10-05, nothing changed)

- **Agreement with Hochsmann.** tp_lockout with the review rule: Sens 89.8 % (Hochsmann 89.8 %), FP/day 1.84 (2.42), delay mean 29.5 min (58.5). Not like-for-like.
- **Refractory vs tp_lockout.** As tuned (each rule with its own parameters): FP/day 1.37 vs 1.65 (-17 %), Sens 87.4 vs 90.5 %. At identical parameters (the tp_lockout sets): refractory gives FP/day 0.91 vs 1.65 (-45 %) and Sens 80.2 vs 90.5 %. F2 tuning under refractory then moves to a more permissive set (gamma1 = 1.0), which gives back most of the FP reduction.
- **Grid edges.** Refractory: gamma1 = 1.0 (lower edge) in all 6 Route B sets; Threshold_act 2.2 in 5 sets and 1.1 in fold_2. tp_lockout: gamma1 = 1.5, Threshold_act 2.3 to 2.4, no edge. Hochsmann: gamma1 = 1 +/- 1, at the lower edge on average.
- **Raw rate.** At the refractory parameters the detector fires 8,214 times over 333 days (about 25 per day, all day). Refractory keeps 2,717.
- **Turn from falling.** 48.6 % of kept FPs (refractory, Route B) fire right after a sample with d1G < 0, vs 38.8 % of TPs. The S8 response contributes to FPs but is not the main source.
- Spot check (`results/spot_check.md`): one day per group, d1G, d2G, the memberships and IGT around every kept detection. The values agree with S2-S5 (checked by hand for one row).
