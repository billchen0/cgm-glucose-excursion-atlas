# Popp (simulation-based meal detection, SBE): deviations and defaults

Framework entries (E, R, X, Y, Z) are in common/docs/deviations.md. The standard protocol
(refractory main, tp_lockout comparison, Route B, excursion segmentation) is section Z there.
Rules follow **docs/evaluation_plan_v3.md** (section 5 note: "No insulin
input in CGMacros").

> Commit hashes in this file refer to the archived local repository (tag `archive-before-atlas-import`); see `docs/prespecification_log.md` for the order of commits.

## Sources

- Hochsmann 2026: Supplementary Methods "Algorithm by Popp et al." (lines 99-118) and Supplementary Table 1, Equations 11-13 (Supplement pp. 9-10).
- Popp CJ, Wang C, Hoover A, et al. J Diabetes Sci Technol 2024;18(2):266-272 (https://doi.org/10.1177/19322968231197205; Hochsmann ref. 2). Two local copies of this paper were compared; their text is identical. Popp's parameters are in its Supplemental Material, which was not available.
- SBE method: Zheng M, Ni B, Kleinberg S. JAMIA 2019;26(12):1592-1599 (https://doi.org/10.1093/jamia/ocz159; Popp ref. 27).
- Glucose model: Popp and Zheng use "GIM", i.e. Dalla Man C, Rizza RA, Cobelli C. Meal simulation model of the glucose-insulin system. IEEE Trans Biomed Eng 2007;54(10):1740-1749 (https://doi.org/10.1109/TBME.2007.893506; Popp ref. 28). **The article was not available to us.** Its equations and normal-subject parameters were taken from the curated BioModels SBML BIOMD0000000379 (downloaded 2026-10-05 from ebi.ac.uk/biomodels; data only). Two values recalled from memory were wrong and corrected by the SBML (d = 0.01; the curated model sets renal excretion E = 0).

## Equations as printed (Hochsmann 2026 Supplementary Table 1)

Transcribed from the PDF images (Supplement pp. 9-10).

```
Eq. 11  Div(i) = (1/zeta) sum_{j=0}^{zeta-1} | (G(i-j) - G'(i-j)) / G'(i-j) |

Eq. 12  D(m) = sqrt( (1/n) sum_{k=k0}^{k1} (G'_m(k) - G(k))^2 )

Eq. 13  MDA_Popp(i) = 1, if Div(i) > phi and exists m in M: D(m) < epsilon
                      0, otherwise
```

Supplementary Methods (lines 100-118, paraphrased): the Dalla Man minimal model simulates the
expected glucose without a meal; Div is the mean relative error over a 30-min window zeta; Div > phi
flags a candidate onset; the algorithm back-searches up to a maximum delay tau for the earliest
divergence, taken as the meal start m_st; around each candidate, glucose is re-simulated with loads
of 25, 50, 75 and 100 g and a 90-min meal duration; D(m) is the Euclidean distance between simulated
and observed glucose in [m_st, i]; a flag is raised when the fit error of a load is below epsilon. No
participant-specific tuning; global grid: zeta = 30 min, phi in {10, 12}, tau in {20, 30, 40, 50, 60}
min, epsilon in {14, 15, 16, 17, 18}. "The grid was kept small due to high computational demand."

Hochsmann 2026 Table 1 (global): epsilon = 18, tau = 20, phi = 0.10 (F2 0.81). Table 2 (test set, review rule, tp_lockout): TP 179, FP 92, FN 37, Sens 82.9 %, FP/day 1.28, delta t 60.5 min.
Popp 2024 did not report sensitivity, FP/day or delay (Hochsmann Supplementary Table 2: "not reported").

## Dalla Man 2007 model (BIOMD0000000379, normal subject)

Glucose: dG_p/dt = EGP + Ra - U_ii - k_1 G_p + k_2 G_t, dG_t/dt = -U_id + k_1 G_p - k_2 G_t, G = G_p / V_G.
Insulin: dI_l/dt = -(m_1 + m_3) I_l + m_2 I_p + S, dI_p/dt = -(m_2 + m_4) I_p + m_1 I_l, I = I_p / V_I,
m_3 = HE m_1 / (1 - HE), HE = -m_5 S + m_6. EGP = k_p1 - k_p2 G_p - k_p3 I_d - k_p4 I_po (I_1, I_d delayed insulin).
U_id = (1 - part)(V_m0 + V_mX X) G_t / (K_m0 + G_t), dX/dt = -p_2U X + p_2U (I - I_b). E = 0 (curated SBML).
Secretion: S = gamma I_po, dI_po/dt = -gamma I_po + S_po, S_po = Y + K dG_p/dt / V_G + S_b, dY/dt = -alpha (Y - beta (G - G_b)).
Gut: dQ_sto1/dt = -k_gri Q_sto1 + ingestion, dQ_sto2/dt = -k_empt Q_sto2 + k_gri Q_sto1, dQ_gut/dt = -k_abs Q_gut + k_empt Q_sto2,
k_empt from k_min, k_max, b, d and the dose D (tanh form), Ra = f k_abs Q_gut / BW.
Parameters: V_G 1.88, k_1 0.065, k_2 0.079, G_b 95, V_I 0.05, m_1 0.19, m_2 0.484, m_4 0.194, m_5 0.0304, m_6 0.6471, I_b 25, S_b 1.8,
k_max 0.0558, k_min 0.008, k_abs 0.057, k_gri 0.0558, f 0.9, b 0.82, d 0.01, BW 78, k_p1 2.7, k_p2 0.0021, k_p3 0.009, k_p4 0.0618,
k_i 0.0079, U_ii 1, V_m0 2.5, V_mX 0.047, K_m0 225.59, p_2U 0.0331, part 0.2, K 2.3, alpha 0.05, beta 0.11, gamma 0.5.

## P. Popp

| ID | Topic | What we did | Source / reason |
|---|---|---|---|
| P1 | Model | Dalla Man 2007 meal model (GIM), normal subject, as in the curated SBML. One fixed population set for everyone. Basal steady state: the SBML initial state run 3,000 min without a meal (G 94.9 mg/dL; no drift afterwards). RK4, step 0.25 min, output every minute. | Popp and Zheng use GIM; Hochsmann calls it "the Dalla Man minimal model". The normal-subject set because no per-person or per-group fitting is allowed. |
| P2 | No insulin input | Insulin is endogenous only: the model's beta-cell secretion responds to glucose. There is no exogenous insulin input and none is needed. | Dalla Man 2007; plan v3 section 5. Popp also studied people without exogenous insulin. |
| P3 | Meal input | Constant ingestion of the load over 90 min into the stomach (Zheng Eq. 8); k_empt uses the total load. Loads 25, 50, 75, 100 g. | Hochsmann (loads, duration); Zheng (constant rate). |
| P4 | Div (Eq. 11) | As printed: the mean absolute relative error over zeta = 30 min (a fraction). phi in percent: phi = 10 means Div > 0.10 (Table 1 prints phi = 0.10). No Savitzky-Golay smoothing. | Hochsmann. Zheng compares window means against phi as a percent of mean glucose and smooths first; we follow Hochsmann's equation. |
| P5 | Anchoring of the no-meal simulation | With CGM only, the unobserved states are unknown, so at each sample i the model starts at its basal steady state at the anchor a = i - max(zeta, tau), shifted to the observed glucose there. Without a meal the model stays at steady state, so the no-meal prediction is G'(k) = G(a) for k > a. | Default, fixed before any run (4152448). Running the model open loop from its population basal (95 mg/dL) would mark every sample of a participant with a higher baseline (T2D) as divergent and could never fit a meal there. |
| P6 | Back-search (m_st) | m_st = earliest sample k in [i - tau, i] such that glucose stays above G' from k through i. If glucose at i is not above G' (a downward divergence), no meal is searched. | Hochsmann: "back-searches up to tau to locate the earliest divergence". Meals only explain rises. |
| P7 | Meal fit (Eq. 12) | G'_m(k) = G(a) + (model glucose after load m from basal - basal), meal starting at m_st; D(m) = root mean square over the n = i - m_st + 1 samples of [m_st, i] (Eq. 12 has 1/n inside the root; the text says "Euclidean distance"). | Hochsmann Eq. 12; Zheng Eq. 9 is the same average. |
| P8 | Detection time | Time i, the first sample of each run of MDA = 1 (rising edge). m_st is stored as `excursion_start` in detections.csv and the standard export. | The text flags at i; Hochsmann's 60.5-min delay fits i, not m_st. |
| P9 | Not applied | Zheng's coarse-to-fine search over start, size and duration, Popp's extended comparison window past the divergent point (t* = max(t, m_st + m_du) + Delta), stored alternative meals and backtracking, and any lockout. Repeats are handled by the protocol's adjacent rule or by tp_lockout. | Hochsmann's simplified procedure; Popp's parameters (Supplement) not available. |
| P10 | Sampling and missing data | QC'd 1-min series. A sample has no Div or fit if any value in [a, i] is missing. Per participant-day (00:00-23:59). | Plan 2.2; default. |
| P11 | Grid | phi {10, 12} %, tau 20:10:60 min, epsilon 14:1:18 mg/dL, zeta 30 fixed: 50 points, exactly as stated. Tie-break order phi, tau, epsilon, ascending. Fixed before running (4152448). | Hochsmann line 117. |
| P12 | Run time and fast path | One participant-day takes about 0.05 s for all 50 grid points: the meal responses are computed once (they start from the same basal state), and Div, m_st and the best fit are computed once per tau and shared across phi and epsilon. Tested equal to `detect` on 10 real days x 50 points. The protocol run took about 70 s. No further speed-up was needed. | Task. |
| P13 | Tuning | Route B, one global set per fold (Z4). Hochsmann also tuned one global set. | Z4. |
| P14 | Narrow flag window | With 90-min ingestion the simulated meal barely rises in the first 20-30 min, so a flag needs Div to pass phi while the observed rise is still within epsilon of a near-flat curve. Fast rises (about 2 mg/dL/min) are not flagged; a model-made 50 g meal is flagged only with tau >= 40 (anchor further back). | Property of the spec with P5, found in the synthetic tests before any CGMacros run; not changed. |

## Findings after the run (2026-10-05, nothing changed)

- **Detection.** Route B, refractory: Sens 63.8 %, Prec 69.8 %, F2 0.649, FP/day 0.55, delay median 43 min (mean 47.0). tp_lockout, review rule: Sens 65.5 % vs 82.9 % in Hochsmann (17.4 pp lower, under the 25 pp stop line), FP/day 1.00 vs 1.28, delay mean 49.9 vs 60.5 min.
- **Estimated meal start m_st** (TP, Route B): refractory median 16 min after the logged start (mean 16.5, IQR -4 to 37); tp_lockout ours 13 (mean 10.7); tp_lockout review 17 (mean 19.7). The detection follows m_st by a median 32 to 33 min.
- **Group gap.** Sens healthy 76.8 %, prediabetes 69.5 %, T2D 44.5 % (refractory; range 32.2 pp, the largest of all methods so far). A 10 % divergence needs a larger absolute rise at a higher baseline.
- **Grid edges.** Every Route B set, for every rule: phi = 10 (lower bound), tau = 40, epsilon = 18 (upper bound). Hochsmann also chose epsilon = 18 (upper bound) and phi = 0.10, but tau = 20. The grid was not extended.
- **Refractory vs tp_lockout (our matching rule).** One parameter set for both, so as tuned and at identical parameters are the same: FP/day 0.55 vs 0.88 (-38 %), Sens 63.8 vs 68.0 %.
- **How the flag fires (P14).** With a 90-min ingestion, the model's meal rise in the first 20 to 30 min is under 1 mg/dL (50 g: +0.3 at 20 min, +7.6 at 60 min; peak +43 at 145 min), and the four loads fit almost equally. A flag needs Div > phi while the RMS gap to these near-flat curves is still below epsilon, so it usually lasts one sample, at the moment Div crosses phi. Rises faster than about 1.5-2 mg/dL/min pass that window without a flag (tests); a model-made 50 g meal is caught only with tau >= 40.
- Spot check (`results/spot_check.md`): one day per group with G, G', Div, m_st and the fit error of each load around every kept detection, plus the m_st delay table. The flags agree with Eq. 13.
