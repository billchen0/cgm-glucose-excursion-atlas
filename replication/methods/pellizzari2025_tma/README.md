# Pellizzari 2025 Template Matching Algorithm (TMA) on CGMacros

Pellizzari E et al. Sci Rep 2025;15:7797 (https://doi.org/10.1038/s41598-025-92275-3).
Reference code: github.com/elisapellizzari/TMA (MATLAB, commit 55baa8b; no licence file, so the
logic was rewritten in Python, not copied).

**Status: excluded from the standard protocol.** TMA needs training: each template and its
threshold are learned from labelled meals. The project only compares methods that need no training
on meal labels (see common/docs/deviations.md, section Z, and the top-level README). These results
are kept as a record. They use an earlier evaluation setup (all 45 participants, a time-ordered
60:40 split, the C05 rule of Hochsmann 2026), so they are not comparable with
results/method_comparison.md.

## What was done

- persTMA (personalised): per participant, a template from 5 training meals (peak-aligned mean)
  and a threshold TH tuned for F1 on the training period. Upper reference.
- popTMA (population): leave-one-subject-out template and threshold from the other 44
  participants. No meal label of the tested participant is used.
- Signal: Dexcom only (native 5-min grid, gaps < 30 min interpolated). Zero-phase Butterworth
  filter, cross-correlation with the template, peaks above TH. Meal time = peak minus half a
  template length.
- Template meals were chosen by an automatic rule (largest 5 qualifying rises), not by an expert.
- Evaluation rules: C05 (detections in (0, 120] min after the logged start, 120-min lockout,
  22:00-07:00 excluded), C05-15 (window -15 to +120 min) and native (the original code's rule).

## Main results (all meals, test period = last 40 % of each participant's meals)

| Version | Rule | Sens | FP/day | Precision | F1 |
|---|---|---|---|---|---|
| persTMA | C05 | 51.2 % | 1.35 | 0.55 | 0.53 |
| popTMA | C05 | 35.4 % | 1.81 | 0.39 | 0.37 |
| persTMA | native | 69.4 % | 1.42 | 0.63 | 0.66 |
| popTMA | native | 66.1 % | 1.28 | 0.65 | 0.65 |

The paper reports F1 0.90 (population 0.86) in 20 patients with post-bariatric hypoglycaemia and
expert-annotated unreported meals. That is not comparable: different population, sensor use and
ground truth.

## Follow-up analyses (one line each)

| Script | Output | Finding |
|---|---|---|
| `run_grouped.py` (`chrono`) | `results/grouped*/` | Group-specific population templates did not help: the healthy-group gain was a threshold shift (precision unchanged), T2D got worse, overall F1 0.37 to 0.38. |
| `run_bl.py` | `results/bl/` | Breakfast and lunch only (fixed window 04:43-17:31): ground-truth quality explains only about 6-8 pp of native Sens. Most C05 errors are onset estimates 0-60 min before the logged meal. |
| `run_bl_mask.py` | `results/bl_maskDS/` | Masking logged dinners and snacks ([-60, +120] min, breakfast and lunch windows kept): their FPs fell from about 20 % to 0; Sens unchanged. |
| `run_train_vs_test.py` | `results/train_vs_test/` | Train vs test period: about 6 pp of the test-period Sens gap is a period effect, about 4 pp in-sample optimism (persTMA). |
| `run_population_variants.py` | `results/population_variants/` | Population mixed vs grouped under the breakfast-lunch setup (C05-15): F1 0.597 vs 0.585; grouping helps healthy and prediabetes, hurts T2D (small donor pools). |
| `run_detection_diagnostics.py`, `export_detections.py` | `results/diagnostics/`, `results/bl_maskDS/detections.csv` | Detection-level diagnostics for the training period and the masked run. |
| `export_standard.py` | `results/standard/` (not tracked) | Standard-format export for the dashboard. |

## Conclusion

The bottleneck is the method itself (onset estimate and the amplitude-sensitive, unnormalised
cross-correlation score), not ground-truth noise. Even in the most favourable setting (standardised
meals, masked dinners and snacks, the original lenient rule) F1 is about 0.67-0.72.

## Run (from the repository root)

```
python methods/pellizzari2025_tma/run_tma.py
python methods/pellizzari2025_tma/run_grouped.py
python methods/pellizzari2025_tma/run_bl.py
python methods/pellizzari2025_tma/run_bl_mask.py
python methods/pellizzari2025_tma/run_train_vs_test.py
python methods/pellizzari2025_tma/run_population_variants.py
python methods/pellizzari2025_tma/run_detection_diagnostics.py
```

Each script writes to its own folder under `results/` and does not overwrite the others.
