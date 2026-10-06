# Turksoy (UKF on a modified minimal model): deviations and defaults

Framework entries (E, R, X, Y, Z) are in common/docs/deviations.md. The standard protocol
(refractory main, tp_lockout comparison, Route B, excursion segmentation) is section Z there.
Rules follow **docs/evaluation_plan_v3.md** (section 5 note: "No insulin
input in CGMacros").

> Commit hashes in this file refer to the archived local repository (tag `archive-before-atlas-import`); see `docs/prespecification_log.md` for the order of commits.

## Sources

- Hochsmann 2026: Supplementary Methods "Algorithm by Turksoy et al." (lines 134-146) and Supplementary Table 1, Equation 16 (Supplement p. 10).
- Original: Turksoy K, Samadi S, Feng J, et al. IEEE J Biomed Health Inform 2016;20(1):47-54 (https://doi.org/10.1109/JBHI.2015.2446413; Hochsmann ref. 27). Two local copies were available: the published IEEE version and the PMC author manuscript of the same paper. We used the **published version**. Where the manuscript text could be extracted, its values match.

## Equation as printed (Hochsmann 2026 Supplementary Table 1)

Transcribed from the PDF image (Supplement p. 10).

```
Eq. 16  MDA_Turksoy(i) = 1, if R_a_hat(i) > Threshold_Ra & G_s(i) > 100 mg/dL
                         0, otherwise
```

Supplementary Methods (lines 135-146, paraphrased): a modified Bergman minimal model with a
two-compartment meal subsystem; state at each 1-min sample: I_eff, G_s, R_a and R_a(i-1), p1, p2,
p4 and tau; a UKF estimates the state; a meal when R_a_hat exceeds Threshold_Ra while G_s is above
100 mg/dL. Threshold_Ra was tuned per participant over 1.5-2.5 mg/dL/min (no step given). The
post-detection threshold raising of the original was not applied.

Hochsmann 2026 Table 1: Threshold_Ra = 1.56 +/- 0.09 (F2 0.84 +/- 0.12). Table 2 (test set, review rule, tp_lockout): TP 166, FP 16, FN 50, Sens 76.9 %, FP/day 0.22, delta t 40.7 min.
Original results (Hochsmann Supplementary Table 2, metrics from Kolle et al.; T1D, TP window -30 to 120 min): Sens 97 / 64 %, FP/day 1.28, delta t 32.7 min.

## Model and UKF as printed (Turksoy 2016, published version pp. 48-49)

```
Eq. 4  G_s(k+1)   = h [ p1(k) (G_b(k) + G_s(k) / (h p1(k)) - G_s(k)) - p2(k) I_eff(k) G_s(k) + R_a(k) ]
Eq. 5  I_eff(k+1) = h [ p2(k) (I_eff(k) / (h p2(k)) - I_eff(k)) + p3(k) I_p(k) ]
Eq. 6  R_a(k+1)   = h C(k) / (V(k) a tau(k)^2) + 2 R_a(k) / a - R_a(k-1) / a^2,   a = e^(h / tau(k))
Eq. 7  [I_p, C, p1, p2, p3, p4, V, tau](k+1) = [0, 0, p1(k), p2(k), 0, p4(k), 0, tau(k)] + w(k)
Eq. 8  G_b(k) = 100                                       for k < 2l/h
              = (h / l) sum_{i = k - 2l/h + 1}^{k - l/h} G_s(i)   for k >= 2l/h,   l = 30 min
Eq. 10 W0x = mu / (L + mu), W0y = mu / (L + mu) + (1 - alpha^2 + beta), Wix = Wiy = 1 / [2 (L + mu)],
       mu = alpha^2 (L + kappa); alpha, beta, kappa = 1, 2, 0
Eq. 11 sigma points x_hat +/- gamma eta_i, eta_i = column i of sqrt(P), gamma = sqrt(L + mu)
Eq. 12 prior sigma points trimmed to [chi_min, chi_max] (min-norm projection)
Eq. 13-21 standard UKF prior, innovation and update
Eq. 22 x_hat(0) = [I_eff 0, G_s CGM(1), R_a 0, R_a(-1) 0, p1 0.068, p2 0.037, p4 1.3, tau 20]
       Qp = diag[1e-6 1e-6 1e-3 1e-3 1e-2 1e-1 1e-2 1e-1], P(0) = I (8 x 8), Qm = 100
Detection (Sec. III): R_a > 2 mg/dL/min; another meal only after R_a falls below the threshold;
a bolus only when CGM > 100 mg/dL; after a bolus the threshold rises to 3, then by 1 per correction bolus.
```

With L = 8: mu = 8, gamma = 4, W0x = 0.5, W0y = 2.5, Wi = 1/32.

## T. Turksoy

| ID | Topic | What we did | Source / reason |
|---|---|---|---|
| T1 | Source file | Published IEEE version (Hochsmann ref. 27). The PMC manuscript is the same paper. | Hochsmann reference list. |
| T2 | No insulin input | Nothing to remove: Eq. 7 already sets the plasma insulin I_p and p3 to 0 at every step, and the carbohydrate C and volume V to 0 (these are "part of the noise term"). So the deterministic model has no insulin input and no meal input. I_eff is a free state: it starts at 0, is driven only by process noise (variance 1e-6) and decays with p2. Meals enter through the process noise on R_a. No diagnosis or demographic is used. | Turksoy 2016 Eq. 7 and text ("only CGM readings"). Plan v3 section 5. |
| T3 | Model step | Eqs. 4-6 expanded: G_s(k+1) = G_s + h (-p1 G_s - p2 I_eff G_s + p1 G_b + R_a), I_eff(k+1) = I_eff - h p2 I_eff, R_a(k+1) = 2 R_a / a - R_a(k-1) / a^2. h = 1 min. Measurement y = G_s. | As printed. |
| T4 | Basal glucose G_b | Eq. 8 with G_s(i) read as the measured CGM, at the previous sample (the step from k-1 to k uses G_b(k-1)): 100 mg/dL for the first 60 samples of a run, then the mean CGM over samples k-59 ... k-30. The counter restarts with the filter. | Turksoy calls G_s(k) "CGM" in Eq. 4. Using the measurement keeps G_b out of the filter state. |
| T5 | Sampling | QC'd 1-min series: linear interpolation of the native Dexcom readings (E1, E2). Turksoy used pchip interpolation of 5-min data. | Plan 2.2. |
| T6 | G_s > 100 | Tested on the measured CGM. | Turksoy: "only when CGM values are above 100"; Hochsmann writes G_s. |
| T7 | Trimming bounds (Eq. 12) | Not stated, so defaults, fixed before any run: I_eff 0 to 1, G_s 20 to 600 mg/dL, R_a and R_a(k-1) 0 to 20 mg/dL/min, and p1, p2, p4, tau from x0/10 to 10 x0 (p1 0.0068-0.68, p2 0.0037-0.37, p4 0.13-13, tau 2-200 min). Box trimming = clipping (the min-norm projection onto a box). The posterior mean is clipped to the same bounds. P is symmetrised; eigenvalues below 1e-9 would be floored (never needed on the 333 days). One setting for everyone. | Default. Trimming at R_a >= 0 and I_eff >= 0 biases the means upward: on flat glucose R_a settles near 0.4 mg/dL/min, not 0 (tests). |
| T7b | Clipping before propagation | The generated sigma points are also clipped to the bounds before f. **Found on the first run attempt**, which crashed before producing any result: on CGMacros-036, 2022-04-07, a tau sigma point near 0 made a = e^(h/tau) overflow. After the fix all 333 days run with positive variances and states within bounds. | Numerical stability (task). Committed separately (1d358a7) before the run that produced results. |
| T8 | Warm-up | Outputs unused for 120 min after each (re)start (start of day, or after a QC gap). Set from the synthetic tests before any run: with P(0) = I and trimming, R_a reaches about 3.4 mg/dL/min within 30 min of a start on flat glucose (3.9 before T7b) and falls below 1.5 only after about 70 min (1.1 at 120 min, 0.4 at 24 h). On real days a detection can still occur just after 02:00 (spot check); it is in the night block-out and not scored. | Default. A 10-min warm-up (as Dassau) gave false detections at minute 10. |
| T9 | Grid | Threshold_Ra 1.5:0.1:2.5 mg/dL/min (11 values). Range from Hochsmann; the step is not stated, 0.1 is a default (as the other thresholds). Fixed before running (7ee4b07). | Hochsmann line 144. |
| T10 | R_a response | R_a reacts weakly and also to sustained rises. Synthetic: a 2 mg/dL/min rise for 40 min gives max R_a about 2.6, a 0.3 mg/dL/min drift for 4 h about 1.6 (it triggers at Threshold_Ra 1.5-1.6). The filter can explain a rise by lowering p1 (process noise 1e-2 per step) instead of raising R_a, and G_b lags the glucose by 30-60 min. The estimated G_s lags the CGM by about 15 mg/dL during rises (Qm = 100). | Property of the stated model and noise settings; not changed. |
| T11 | Not applied | The threshold raising after a bolus (2 to 3, +1 per correction bolus), the 30-min bolus spacing and the bolus logic. No built-in lockout. The original's "another meal only after R_a falls below the threshold" is the rising-edge rule. Repeats are handled by the protocol's adjacent rule or by tp_lockout. | Hochsmann lines 144-146; task. |
| T12 | p4 | p4 appears in the state (Eq. 7) but in none of Eqs. 4-6. It is an unobservable random walk; its estimate drifts (spot check: 1.3 to about 2.8) and has no effect on R_a. Kept, as Hochsmann lists it. | As printed. |
| T13 | UKF weights | As printed (mu = 8, gamma = 4, W0x = 0.5, W0y = 2.5, Wi = 1/32). This differs from the common form (lambda = alpha^2 (L + kappa) - L = 0) but is a valid weight set: the sigma points reproduce the mean and covariance exactly. | Turksoy Eq. 10. |
| T14 | Tuning | Route B, one global threshold per fold (Z4). Hochsmann tuned per participant; Turksoy used a fixed threshold of 2. | Z4. |
| T15 | detect_grid | The UKF runs once per day (results cached in memory, keyed on the input); thresholds are broadcast. Tested equal to `detect` on all 11 points x 7 days. | Speed. |

## Findings after the run (2026-10-05, nothing changed)

- **Detection.** Route B, refractory: Sens 53.5 %, Prec 89.1 %, F2 0.581, FP/day 0.13, delay mean 41.6 min. tp_lockout, review rule: Sens 55.1 % vs 76.9 % in Hochsmann (21.8 pp lower, under the 25 pp stop line), FP/day 0.19 vs 0.22, delay mean 42.1 vs 40.7 min. Run time about 37 s.
- **Why Sens is low.** Within 120 min after a logged meal, the maximum R_a has median 1.74 mg/dL/min; only 59 % of meals exceed 1.5 and 38 % exceed 2.0. Sens is capped near 60 % at the lowest threshold.
- **Grid edge.** Threshold_Ra = 1.5, the lower bound, in all 6 Route B sets for every rule. The best value may lie below the Hochsmann range. The grid was not extended. Hochsmann's tuned 1.56 +/- 0.09 is also near that bound.
- **Refractory vs tp_lockout (our matching rule).** Both tune to 1.5, so as tuned and at identical parameters are the same: FP/day 0.13 vs 0.15 (-14 %), Sens 53.5 vs 56.7 %. The detector fires rarely (1,005 raw detections over 333 days, about 3 per day), so the rule has little to remove.
- **Stability.** All 333 days: no failure, no eigenvalue floor, positive variances, states within bounds.
- Spot check (`results/spot_check.md`): one day per group, CGM, G_s, R_a, p1, p2, p4 and tau around every kept detection. The flags agree with Eq. 16.
