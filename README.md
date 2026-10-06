# Free-Living Glucose Excursion Detection — evidence atlas and preprocessing workspace

Two things live here:

1. **The evidence atlas** — a literature review of glucose-excursion and postprandial-response
   detection methods, the four fit gates applied to it, a shared-benchmark summary, and a
   statistical analysis plan.
2. **A local-first preprocessing pipeline and dashboard** — readable, tested Python that turns a
   downloaded CGMacros dataset into canonical analysis tables, plus a browser dashboard that
   reads those tables from a local API.

The dashboard renders participant data **dynamically**. Nothing about a participant's glucose
values is compiled into the page.

## Quick start

```bash
# Once: create the environment
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -e ".[dev]"

# Download CGMacros (PhysioNet, open access) and either keep the ZIP or extract it:
#   https://physionet.org/content/cgmacros/1.0.0/

# See what the files actually contain, reading only
.venv/bin/cgm audit /path/to/CGMacros

# Build the canonical tables
.venv/bin/cgm preprocess /path/to/CGMacros

# Open the dashboard
.venv/bin/cgm serve
```

`cgm preprocess` accepts either the downloaded ZIP or an extracted directory, and reads the
dataset read-only. It never writes outside `data/processed/`, which is git-ignored. The dataset
path you pass is remembered in a git-ignored `.cgm-local.yaml`, so later launches need no
arguments.

## Layout

```
web/                    the dashboard (static shell + panel script)
  index.html            four tabs: Literature Review, Analysis plan, Assets, Visualization
  static/viz-panel.js   the Visualization tab's data layer — fetches /api, draws with Plotly
  static/plotly.min.js  vendored Plotly, no CDN
  assets/figures/       figures reproduced from cited publications
  figures/extracted/    figures extracted from PubMed Central open-access articles

src/cgm_excursions/     the pipeline
  dataset.py            resolve a ZIP or a directory into participant sources
  reading.py            header normalization and frame construction
  preprocessing.py      the stages, in order, one function each
  config.py             the only place a threshold lives
  outputs.py            parquet + qc_summary.json + run manifest
  pipeline.py           sequence the stages over a cohort
  api.py                the read-only local HTTP API the dashboard reads
  audit.py              "what is actually in these files?" — reads only
  cli.py                cgm audit | preprocess | serve | summary

config/preprocessing.yaml   every threshold, documented
docs/preprocessing-spec.md  the contract the code implements
docs/dataset-shape.md       what the dataset actually is, measured
tests/                      the pipeline's test suite, including adversarial invariants
data/raw|interim|processed  git-ignored; outputs land in data/processed/<run-id>/

replication/                detection method replications on CGMacros
                            (see replication/README.md)
```

## The dataset, measured rather than assumed

`docs/dataset-shape.md` records what the 45 CGMacros participant files actually are. The
finding that shaped the pipeline: **the files are one row per minute, and each sensor's
reading is carried forward until it refreshes** — they are not clean 5- and 15-minute streams.
Measured across all 45 participants, 9.8–29.9 % of Dexcom readings and 4.5–46.8 % of Libre
readings are repeats of the previous reading.

So the canonical table keeps the file's own rows, and every row carries an explicit
`*_glucose_is_fresh` flag separating a new measurement from a held copy. The dashboard draws
new readings by default and can reveal the carried values. There is no bucketing and no
resampling anywhere in preprocessing.

Two more measured facts worth knowing:

- **Nine distinct header layouts** exist across the 45 files. Column order is not stable and
  exactly one participant lists `Dexcom GL` before `Libre GL`, so a positional parser silently
  swaps the two sensors for that participant. Columns are resolved by normalized name.
- **`40.0` mg/dL is a floor, not a measurement.** 13,027 of 57,519 Libre readings sit exactly at
  it. The value is retained and flagged `qc_possible_compression_low`; it is never deleted.

## The governing principle

Preprocessing prepares data. It does not analyse, detect, or clean silently.

- No glucose value is ever modified, clipped, rounded, smoothed, or interpolated.
- No row is ever dropped. A flag is added beside a questionable value, and `qc_eligible` is a
  separate, auditable mask.
- Screening flags (range, rate of change, flatline, isolated spike) **never** clear eligibility.
  A detector that wants to exclude them says so explicitly and reports it.
- Dexcom and Libre are never averaged, and neither is ever filled from the other.

`docs/preprocessing-spec.md` states the full contract, including each flag's rule and whether it
is informational or hard.

## Outputs

A run writes to `data/processed/<run-id>/`:

| File | Contents |
|---|---|
| `cgm.parquet` | one row per participant-minute, both raw streams, freshness flags, QC flags, eligibility, segment ids |
| `meals.parquet` | one row per logged meal with macronutrients exactly as observed |
| `participants.parquet` | `bio.csv` joined to the CGM cohort, plus derived per-participant facts |
| `qc_summary.json` | coverage rollups at participant, shifted-day, and contiguous-segment levels |
| `manifest.json` | dataset fingerprint, effective config and its hash, software versions, per-file SHA-256 |

The run id is derived from the config hash and a SHA-256 of the participant files, so a changed
threshold or an altered input produces a different run rather than silently different output
under the same name.

## Tests

```bash
.venv/bin/python -m pytest tests/ -q
```

The suite includes `tests/test_pipeline_integrity.py`, which tries to *falsify* the promises
above against the real dataset: row preservation, value preservation, flag containment,
eligibility derivation, freshness consistency, segment and gap integrity.

## Figure licensing

Figures are reproduced from open-access publications. Licenses were checked via Europe PMC:
11 figures are CC BY, 4 are CC BY-NC-ND, 1 is CC BY-NC-SA, and one figure's DOI
(`10.1155/2020/7103883`) does not currently resolve. Because several are licensed
**non-commercial** and **no-derivatives**, reusing those figures requires the original terms.

## Status

The evidence atlas was previously published as a self-contained static page at
`https://billchen0.github.io/cgm-glucose-excursion-atlas/`. That static release is preserved
under the git tag `legacy-static-v3.2`; this branch restructures the repository around the
pipeline and the dynamic dashboard.
