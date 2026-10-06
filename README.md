# Free-Living Glucose Excursion Detection — Evidence Atlas

A static, self-contained evidence atlas reviewing detection methods for glucose
excursions and postprandial glucose response (PPGR) from continuous glucose
monitoring (CGM) data.

**Live site:** https://billchen0.github.io/cgm-glucose-excursion-atlas/

## What it contains

- **Literature review** — 21 detection/response methods across 7 concept families, each with
  dataset, population and reported performance, plus the four fit gates applied to this review
  (pre-training / per-subject splits, non-CGM inputs, missing implementation details,
  non-transferable population) and the exclusion ledger.
- **Benchmark table** — the nine algorithms assessed in the shared C05 benchmark (Kölle ×2,
  Dassau ×2, Harvey, Faccioli, Samadi, Popp, Turksoy) with whether each required training,
  per-participant tuning, or ground-truth meal labels.
- **Statistical analysis plan**, an **assets** index of extracted figures, and an interactive
  **visualization** of CGMacros CGM traces with per-subject selection.

## Contents

```
index.html            the report (single file, no build step)
viz/plotly.min.js     vendored Plotly (no CDN, no network at view time)
viz/manifest.js       dataset manifest + series metadata
viz/subjects/*.js     45 per-subject CGM traces (loaded on demand)
assets/figures/       8 figures reproduced from the cited publications
figures/extracted/    10 figures extracted from PubMed Central open-access articles
replication/          detection method replications on CGMacros (see replication/README.md)
```

The page loads nothing from the network at view time: open `index.html` from a local
server and it renders offline.

## Provenance

Screening and extraction followed a frozen review protocol: 12 fixed public-index queries
(six concept families across Europe PMC and PubMed routes), 5,937 source records, 3,034
after de-duplication, 2,782 title/abstract exclusions, 166 promoted, 86 uncertain, 252
full-text retrieval attempts, and 124 still awaiting full text. Methods and figures are
reproduced with attribution to their sources; the atlas makes no new scientific claims and
these metrics are not ranked across studies.

## Figure licensing

Figures are reproduced from open-access publications. Licenses were checked via Europe PMC:

- **CC BY** — 11 figures (unrestricted reuse with attribution)
- **CC BY-NC-ND** — 4 figures (non-commercial, no derivatives)
- **CC BY-NC-SA** — 1 figure (non-commercial, share-alike)
- **Unresolved** — 1 figure, whose DOI (`10.1155/2020/7103883`) does not currently resolve

Because several figures are licensed **non-commercial** and **no-derivatives**, reuse of those
figures requires the original license terms. The data visualization uses CGMacros
(PhysioNet, `10.13026/3z8q-x658`).

## Status

Revision v3.2 — four-column detection table, title-as-link citations, single teal
highlight for shared-benchmark membership, and the legend placed after the table and
exclusion ledger. Historically a private researcher-facing atlas.
