# Lim (wavelet PPGR identification): deviations and defaults

Framework entries (E, R, X, Y, Z) are in common/docs/deviations.md. The standard protocol
(refractory main, tp_lockout comparison, Route B, excursion segmentation) is section Z there.
Rules follow **docs/evaluation_plan_v3.md** (section 5 note: "Uses fixed
clock-time meal windows. One detection per window, so it cannot find non-meal excursions.
Appendices A to C needed.").

> Commit hashes in this file refer to the archived local repository (tag `archive-before-atlas-import`); see `docs/prespecification_log.md` for the order of commits.

## Source

- Lim W, Zhong Y, Bruno J, et al. J Diabetes Sci Technol 2026;20(3):664-672 (https://doi.org/10.1177/19322968261427499), Methods pp. 666-667.
- **Appendices A-C are not in the published article.** The text refers to them for the Gaussian filter (A), the wavelet details (B) and the tie-break (C), and to an online Supplemental Material that we do not have. Every detail they hold is a default below, chosen before any CGMacros run (commit 160f225).
- Hochsmann 2026 did not evaluate Lim, so there is no Table 2 row. Lim reports PPGR start-time error, not sensitivity or FP/day.

## Method as described (Lim 2026, paraphrased)

- PPGR definition: (i) the start lies in a meal window, breakfast 06:00-11:45, lunch 12:00-16:00, dinner 17:00-21:00; (ii) the rise from start to peak exceeds 10 mg/dL; (iii) if several qualify, a tie-break on height and timing applies. Sensitivity analysis: thresholds 20 and 30 mg/dL.
- Stage 1: Gaussian smoothing (scipy `ndimage.gaussian_filter`). Stage 2: Gaussian wavelet transform (PyWavelets) of each 24-h profile (00:00-23:59). Stage 3: each wavelet maximum in a meal window and the next minimum form a candidate segment; peak = highest glucose in the segment; PPGR start = lowest glucose before the peak in the segment. Stage 4: segments with height < 10 mg/dL are excluded; the rest are ranked by height and the tie-break (Appendix C) gives the final PPGR.
- Missing data: gaps <= 15 min linearly interpolated; a meal window with a gap > 15 min is excluded; continuous data required from 03:00 to 24:00.
- Results: Hall breakfast median absolute start error 10 [4, 19] min. CGMacros (Dexcom): breakfast 14 [6, 29], lunch 36 [19, 63], dinner 28 [11, 56] min; (Libre): 15 [7, 27], 26 [14, 47], 18 [9, 39] min.

## L. Lim

| ID | Topic | What we did | Source / reason |
|---|---|---|---|
| L1 | Windows | Breakfast 06:00-11:45 and lunch 12:00-16:00, both ends inclusive, on the PPGR start. Dinner is not used: our ground truth is breakfast and lunch. One PPGR per window, so at most 2 detections per day. | Lim p. 666; task. Same windows as our meal_window_max_peak rule (R1). |
| L2 | Gaussian smoothing (Appendix A missing) | `scipy.ndimage.gaussian_filter1d`, sigma = 2 samples (10 min), on the 24-h profile. | Default. Light smoothing of 5-min sensor noise that keeps a 30-60 min rise. |
| L3 | Wavelet (Appendix B missing) | PyWavelets continuous transform with the 'gaus1' wavelet (first derivative of a Gaussian) at one scale, 15 samples (75 min); sign flipped so that a rise gives positive coefficients. The scale was calibrated on the example in Lim Fig. 1 (meal 08:00, peak 09:00, back to pre-meal at 10:00; a raised-cosine bump of 50 mg/dL): the coefficient maximum and minimum fall at 08:05 and 10:00, as the figure shows. | Default. Lim says only "Gaussian wavelet" and that the maxima and minima match the start and end of a PPGR (Fig. 1). The calibration uses Lim's own figure, not CGMacros. |
| L4 | Edges | The transform runs on the mean-removed day with reflect padding of one day on each side. | Default. Without it the edges dominate the coefficients. Lim requires a 3-h buffer for the same reason. |
| L5 | Tie-break (Appendix C missing) | Highest height; exact ties go to the earlier start. A candidate whose start falls outside the window is dropped. | Default. Lim: "based on relative height and timing" (details unknown). Same rule as R2. |
| L6 | Candidates | Local maxima of the coefficient (strict on the left) whose time is inside the window; segment to the next local minimum (or the day end). Peak, start and height use the QC'd glucose, not the smoothed curve. | Lim stage 3. Using the measured glucose is our reading ("highest glucose point", "starting glucose = CGM reading"). |
| L7 | Missing data | Our QC is kept, so the cohort matches the other methods: gaps <= 30 min interpolated (E2), days with a gap > 120 min removed (plan 2.4). A window with any missing 5-min sample gets no PPGR (the closest match to Lim's "gap > 15 min excludes the window"). Lim's 03:00-24:00 continuity rule is not applied. Remaining gaps are bridged linearly for the transform only. | Task. Lim interpolates <= 15 min and requires 03:00-24:00. |
| L8 | Detection time and columns | Detection = PPGR start. Exported columns: excursion_start (= start), peak_time, excursion_end (= the next wavelet minimum). | Task. |
| L9 | Parameters | Fixed, not tuned: minimum height 10 mg/dL. All Route B folds therefore have the same parameters (expected). Sensitivity runs at 20 and 30 mg/dL (`src/run_sensitivity.py`, `results/protocol_v1_h20/`, `results/protocol_v1_h30/`), reported next to the main run, not as a grid. | Lim p. 666 and its sensitivity analysis. |
| L10 | Sampling | Native 5-min Dexcom readings (E1). | Lim used 5-min Dexcom data for Hall. |

## Findings after the run (2026-10-06, nothing changed)

- **Detection.** Route B, refractory, our matching rule: Sens 67.9 %, Prec 89.2 %, F2 0.713, FP/day 0.16, delay median 25 min. Breakfast Sens 80.2 %, lunch 55.7 %. By group: healthy 67.9, prediabetes 68.5, T2D 67.3 % (range 1.2 pp, the most even of all methods so far). FP/day is not comparable with the all-day detectors: at most 2 detections per day.
- **Adjacent rules.** refractory and tp_lockout give identical results (TP 448, FP 54, FN 212). Refractory removed none of the 552 raw detections and the TP lockout ignored none: a breakfast and a lunch PPGR start are always more than 120 min apart here.
- **Sensitivity runs** (Route B, refractory): 20 mg/dL Sens 61.5 %, Prec 90.6 %, FP/day 0.13; 30 mg/dL Sens 53.9 %, Prec 90.8 %, FP/day 0.11.
- **Start-time error** (`results/start_error.md`), median [IQR] absolute error. Lim-style (every scored meal inside its window, against the PPGR of that window): breakfast 18 [8, 37] min, lunch 44 [26, 77] min. TP only: breakfast 16 [7, 31], lunch 40 [26, 62]. Lim on CGMacros (Dexcom): breakfast 14 [6, 29], lunch 36 [19, 63]. Our errors are a few minutes larger, with the same breakfast-lunch gap.
- **Out-of-window meals.** 115 of 660 scored meals (17.4 %) were logged outside their window: breakfast 20 of 328 (6.1 %), lunch 95 of 332 (28.6 %). They account for 79 of the 212 FN (37 %).
- **Start lag in synthetic tests.** The wavelet maximum sits a little into the rise, so the start is 5-10 min after a synthetic true start.
- Spot check (`results/spot_check.md`): one day per group, every candidate segment, the chosen PPGR and the smoothed curve with the wavelet coefficient. The choices agree with L5-L6.
