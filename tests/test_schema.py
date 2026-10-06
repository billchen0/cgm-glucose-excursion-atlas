"""Tests for the canonical schema: names, column order, and the HbA1c bands.

The band boundaries are the one place in the schema with a real clinical convention
behind them, so they are pinned against the published CGMacros cohort counts rather than
against whatever the code happens to produce.
"""

from __future__ import annotations

import pytest

from cgm_excursions import schema


# ------------------------------------------------------------------- HB A1C
@pytest.mark.parametrize(
    "value, expected",
    [
        (4.6, "normal"),
        (5.6, "normal"),
        # Exactly 5.7 is the prediabetes threshold. An exclusive lower bound would put
        # these in Normal and break the published cohort counts.
        (5.7, "prediabetes"),
        (6.0, "prediabetes"),
        (6.4, "prediabetes"),
        (6.5, "diabetes"),
        (8.5, "diabetes"),
    ],
)
def test_a1c_band_boundaries(value, expected):
    assert schema.a1c_band(value) == expected


def test_a1c_band_handles_missing_values():
    assert schema.a1c_band(None) is None
    assert schema.a1c_band(float("nan")) is None


def test_a1c_bands_reproduce_the_published_cohort_counts():
    """CGMacros v1.0.0 publishes 15 normal / 16 prediabetes / 14 diabetes.

    This is the check that caught a real off-by-one: with an exclusive lower bound the
    three participants reading exactly 5.7 land in Normal, giving 18 / 13 / 14.
    """
    from pathlib import Path

    import pandas as pd

    dataset = Path(
        "/Users/billchen/Desktop/JupyterHealth/Datasets/CGMacros/1.0.0"
        "/extracted/CGMacros/bio.csv"
    )
    if not dataset.exists():
        pytest.skip("CGMacros bio.csv is not available on this machine")

    bio = pd.read_csv(dataset)
    bio.columns = [column.strip() for column in bio.columns]
    counts: dict[str, int] = {}
    for value in bio["A1c PDL (Lab)"]:
        band = schema.a1c_band(value)
        counts[band] = counts.get(band, 0) + 1

    assert counts.get("normal") == 15
    assert counts.get("prediabetes") == 16
    assert counts.get("diabetes") == 14
    assert sum(counts.values()) == 45


# ----------------------------------------------------------------- COLUMNS
def test_canonical_columns_start_with_identity_and_time():
    columns = schema.canonical_cgm_columns()

    assert columns[:3] == [schema.SUBJECT_ID, schema.TIMESTAMP, schema.ELAPSED_MINUTES]


def test_canonical_columns_carry_both_raw_streams_and_freshness():
    columns = schema.canonical_cgm_columns()

    for name in (schema.DEXCOM_RAW, schema.LIBRE_RAW, schema.DEXCOM_FRESH, schema.LIBRE_FRESH):
        assert name in columns


def test_every_qc_flag_is_present_and_prefixed():
    columns = schema.canonical_cgm_columns()

    for flag in schema.QC_FLAGS:
        assert flag in columns
        assert flag.startswith(schema.QC_PREFIX)


def test_eligibility_is_not_a_qc_flag():
    """qc_eligible is the analysis mask, not a flag; keeping it out of QC_FLAGS means
    "which columns are flags" stays a prefix question with a stable answer."""
    assert schema.QC_ELIGIBLE not in schema.QC_FLAGS


def test_only_the_duplicate_timestamp_flag_is_hard():
    assert schema.HARD_QC_FLAGS == (schema.QC_DUPLICATE_TIMESTAMP,)


def test_screening_flags_never_clear_eligibility():
    """A threshold that is a screening guess must not silently remove physiology."""
    for flag in (schema.QC_OUT_OF_RANGE, schema.QC_RATE_OF_CHANGE,
                 schema.QC_FLATLINE, schema.QC_ISOLATED_SPIKE,
                 schema.QC_COMPRESSION_LOW):
        assert flag not in schema.HARD_QC_FLAGS


def test_raw_column_mapping_covers_every_stream():
    assert set(schema.RAW_COLUMN) == set(schema.SENSORS)
    assert set(schema.FRESH_COLUMN) == set(schema.SENSORS)


def test_streams_are_never_aliased_to_one_column():
    assert schema.RAW_COLUMN["dexcom"] != schema.RAW_COLUMN["libre"]
    assert schema.FRESH_COLUMN["dexcom"] != schema.FRESH_COLUMN["libre"]
