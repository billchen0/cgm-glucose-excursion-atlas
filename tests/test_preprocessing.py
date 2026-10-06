"""TDD suite for the preprocessing core.

Written before ``preprocessing.py`` exists; every test here was watched fail first.

The behaviours under test are the ones the project's contract actually promises:
raw values survive untouched, flags report rather than repair, held sensor values are
distinguishable from fresh readings, gaps are per-stream, and eligibility never deletes
a row.
"""

from __future__ import annotations

import pandas as pd
import pytest

from cgm_excursions import preprocessing as prep
from cgm_excursions import schema
from tests.fixtures import (
    OUTAGE_END,
    OUTAGE_START,
    make_compression_low,
    make_dexcom_outage,
    make_flatline,
    make_isolated_spike,
    make_layout_a,
    make_missing_meal_macros,
    make_out_of_range,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def write(tmp_path, text: str, name: str = "participant.csv"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


DEFAULT_CONFIG = {
    "streams": {
        "primary": "dexcom",
        "replication": "libre",
        "documented_range_mgdl": {"dexcom": [40, 400], "libre": [40, 500]},
    },
    "qc": {
        "duplicate_timestamp": {"enabled": True},
        "rate_of_change": {"enabled": True, "max_mgdl_per_min": 4.0},
        "flatline": {"enabled": True, "min_run_minutes": 20},
        "isolated_spike": {
            "enabled": True,
            "min_delta_mgdl": 50,
            "neighbour_max_delta_mgdl": 25,
        },
        "possible_compression_low": {"enabled": True, "value_mgdl": 40},
        "advanced": {"enabled": False},
    },
    "gaps": {"min_gap_seconds": 900, "segment_break_seconds": 3600},
}


def build(tmp_path, text: str, subject: str = "001") -> pd.DataFrame:
    return prep.preprocess_participant(
        write(tmp_path, text), subject_id=subject, config=DEFAULT_CONFIG
    )


# ---------------------------------------------------------------------------
# stage: type and sort
# ---------------------------------------------------------------------------
def test_one_row_per_input_row_survives(tmp_path):
    """Nothing is deduplicated, bucketed, or dropped on the way through."""
    source = make_layout_a(periods=60)
    frame = build(tmp_path, source)

    assert len(frame) == 60
    assert frame["subject_id"].nunique() == 1
    assert frame["subject_id"].iloc[0] == "001"


def test_raw_values_are_never_modified(tmp_path):
    frame = build(tmp_path, make_layout_a(periods=60))
    observed = frame["dexcom_glucose_raw"].dropna().tolist()

    assert observed[0] == pytest.approx(141.0)
    assert 144.6 in [round(v, 1) for v in observed]
    # the exact float from the file is preserved, not re-derived or smoothed
    assert frame["dexcom_glucose_raw"].iloc[:5].tolist() == [141.0] * 5


def test_elapsed_minutes_starts_at_zero(tmp_path):
    frame = build(tmp_path, make_layout_a(periods=60))

    assert frame["elapsed_minutes"].iloc[0] == 0.0
    assert frame["elapsed_minutes"].iloc[-1] == pytest.approx(59.0)


def test_timestamps_are_preserved_not_reinterpreted(tmp_path):
    frame = build(tmp_path, make_layout_a(periods=60))

    expected_first = pd.Timestamp("2020-05-01 11:39:00")
    assert frame["timestamp_shifted"].iloc[0] == expected_first


# ---------------------------------------------------------------------------
# stage: mark fresh observations  (the finding that shaped the design)
# ---------------------------------------------------------------------------
def test_held_values_are_distinguishable_from_fresh_readings(tmp_path):
    """Dexcom refreshes once per 5 minutes here, so 1 in 5 rows is fresh."""
    frame = build(tmp_path, make_layout_a(periods=60))
    fresh = frame["dexcom_glucose_is_fresh"]

    assert fresh.iloc[0] is True or bool(fresh.iloc[0]) is True
    assert int(fresh.sum()) == 12          # 60 minutes / 5-minute refresh
    assert int((~fresh).sum()) == 48       # the carried values


def test_first_reading_in_each_stream_is_fresh(tmp_path):
    frame = build(tmp_path, make_layout_a(periods=60))

    assert bool(frame["libre_glucose_is_fresh"].iloc[0]) is True
    assert bool(frame["dexcom_glucose_is_fresh"].iloc[0]) is True


def test_freshness_is_per_stream_not_shared(tmp_path):
    """Libre refreshes on its own clock; it must not inherit Dexcom's boundary."""
    frame = build(tmp_path, make_layout_a(periods=60))

    dexcom_fresh = frame["dexcom_glucose_is_fresh"]
    libre_fresh = frame["libre_glucose_is_fresh"]
    assert not dexcom_fresh.equals(libre_fresh)


def test_a_null_does_not_make_the_next_value_fresh(tmp_path):
    """Freshness compares against the previous *observation*, across intervening nulls."""
    text = (
        "Timestamp,Dexcom GL,Libre GL\n"
        "2020-01-01 00:00:00,100.0,90.0\n"
        "2020-01-01 00:01:00,100.0,90.0\n"
        "2020-01-01 00:02:00,,90.0\n"
        "2020-01-01 00:03:00,100.0,90.0\n"
    )
    frame = build(tmp_path, text)

    assert frame["dexcom_glucose_is_fresh"].tolist() == [True, False, False, False]


# ---------------------------------------------------------------------------
# stage: value integrity
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value_row, expected_max",
    [(2, 40.0), (5, 400.0)],
)
def test_out_of_documented_range_is_flagged_and_kept(tmp_path, value_row, expected_max):
    frame = build(tmp_path, make_out_of_range())
    flagged = frame.loc[frame["qc_out_of_documented_range"]]

    assert len(flagged) == 2
    assert frame["dexcom_glucose_raw"].iloc[value_row] == pytest.approx(38.0 if value_row == 2 else 412.0)
    # the out-of-range value survives in the raw column
    assert frame["dexcom_glucose_raw"].max() == pytest.approx(412.0)


def test_compression_low_sentinel_is_flagged_not_deleted(tmp_path):
    frame = build(tmp_path, make_compression_low())
    flagged = frame.loc[frame["qc_possible_compression_low"]]

    assert len(flagged) == 2
    assert frame["dexcom_glucose_raw"].iloc[1] == pytest.approx(40.0)


def test_libre_range_is_applied_to_libre_not_dexcom(tmp_path):
    """405 is in range for Libre's documented 40-500 and must not be flagged."""
    text = (
        "Timestamp,Dexcom GL,Libre GL\n"
        "2021-06-01 00:00:00,100.0,405.0\n"
        "2021-06-01 00:01:00,101.0,405.0\n"
    )
    frame = build(tmp_path, text)

    assert not frame["qc_out_of_documented_range"].any()
    assert frame["libre_glucose_raw"].iloc[0] == pytest.approx(405.0)


# ---------------------------------------------------------------------------
# stage: per-stream QC
# ---------------------------------------------------------------------------
def test_flatline_run_is_flagged_over_its_whole_length(tmp_path):
    frame = build(tmp_path, make_flatline(periods=40))
    flagged = frame.loc[frame["qc_flatline"]]

    assert len(flagged) >= 20
    assert flagged["timestamp_shifted"].iloc[0] == pd.Timestamp("2021-01-01 00:00:00")


def test_short_constant_run_is_not_a_flatline(tmp_path):
    """A genuine 5-minute plateau is normal CGM behaviour, not an artefact."""
    rows = [f"2021-01-01 00:{m:02d}:00,150.0,100.0" for m in range(5)]
    text = "Timestamp,Dexcom GL,Libre GL\n" + "\n".join(rows) + "\n"
    frame = build(tmp_path, text)

    assert not frame["qc_flatline"].any()


def test_isolated_spike_flags_only_the_outlier(tmp_path):
    frame = build(tmp_path, make_isolated_spike())
    flagged = frame.loc[frame["qc_isolated_spike"]]

    assert len(flagged) == 1
    assert flagged["dexcom_glucose_raw"].iloc[0] == pytest.approx(300.0)


def test_rate_of_change_flags_the_arrival_row(tmp_path):
    """The rate belongs to the later sample; the earlier one is not implicated."""
    text = (
        "Timestamp,Dexcom GL,Libre GL\n"
        "2021-07-01 00:00:00,100.0,90.0\n"
        "2021-07-01 00:01:00,120.0,90.0\n"
        "2021-07-01 00:02:00,122.0,90.0\n"
    )
    frame = build(tmp_path, text)

    assert frame["qc_rate_of_change"].tolist() == [False, True, False]
    assert frame["dexcom_glucose_raw"].iloc[1] == pytest.approx(120.0)


def test_slow_physiological_change_is_not_flagged(tmp_path):
    rows = [f"2021-08-01 00:{m:02d}:00,{100.0 + m},90.0" for m in range(10)]
    text = "Timestamp,Dexcom GL,Libre GL\n" + "\n".join(rows) + "\n"
    frame = build(tmp_path, text)

    assert not frame["qc_rate_of_change"].any()


# ---------------------------------------------------------------------------
# stage: eligibility and segments
# ---------------------------------------------------------------------------
def test_out_of_range_does_not_clear_eligibility(tmp_path):
    """A screening threshold must not silently remove physiology."""
    frame = build(tmp_path, make_out_of_range())
    flagged = frame.loc[frame["qc_out_of_documented_range"]]

    assert flagged["qc_eligible"].all()


def test_null_primary_value_clears_eligibility(tmp_path):
    frame = build(tmp_path, make_dexcom_outage(periods=600))
    during = frame.iloc[200:300]          # inside the Dexcom outage

    assert frame["dexcom_glucose_raw"].isna().sum() > 0
    assert not during["qc_eligible"].any()


def test_ineligible_rows_are_retained_not_dropped(tmp_path):
    frame = build(tmp_path, make_dexcom_outage(periods=600))

    assert len(frame) == 600
    assert int((~frame["qc_eligible"]).sum()) > 0


def test_segment_id_resets_per_participant_and_breaks_on_long_gap(tmp_path):
    frame = build(tmp_path, make_dexcom_outage(periods=600))
    eligible = frame.loc[frame["qc_eligible"]]
    segments = eligible["segment_id"].dropna().unique()

    assert len(segments) >= 2
    assert frame.loc[~frame["qc_eligible"], "segment_id"].isna().all()


# ---------------------------------------------------------------------------
# stage: gaps
# ---------------------------------------------------------------------------
def test_gap_detection_is_per_stream(tmp_path):
    """A minute where only Libre reported is not a Dexcom gap in the file."""
    frame = build(tmp_path, make_dexcom_outage(periods=600))
    gaps = prep.detect_gaps(frame, DEFAULT_CONFIG)

    dexcom_gaps = [g for g in gaps if g["stream"] == "dexcom"]
    libre_gaps = [g for g in gaps if g["stream"] == "libre"]

    assert any(g["duration_seconds"] >= 3600 for g in dexcom_gaps)
    assert not any(g["duration_seconds"] >= 900 for g in libre_gaps)


def test_gap_records_carry_their_bounds(tmp_path):
    frame = build(tmp_path, make_dexcom_outage(periods=600))
    gaps = prep.detect_gaps(frame, DEFAULT_CONFIG)
    longest = max((g for g in gaps if g["stream"] == "dexcom"),
                  key=lambda g: g["duration_seconds"])

    # The gap runs from the last observation before the outage to the first after it.
    assert longest["duration_seconds"] == pytest.approx((OUTAGE_END - OUTAGE_START + 1) * 60)
    assert longest["start"] == pd.Timestamp("2022-03-02 08:59:00")
    assert longest["end"] == pd.Timestamp("2022-03-02 13:00:00")
    assert pd.Timestamp(longest["start"]) < pd.Timestamp(longest["end"])


# ---------------------------------------------------------------------------
# stage: coverage rollups
# ---------------------------------------------------------------------------
def test_coverage_rollup_covers_participant_day_and_segment_levels(tmp_path):
    frame = build(tmp_path, make_dexcom_outage(periods=600))
    summary = prep.roll_up_coverage({"001": frame}, {"001": prep.detect_gaps(frame, DEFAULT_CONFIG)})

    assert set(summary) == {"participants", "days", "segments"}
    assert len(summary["participants"]) == 1
    assert summary["participants"][0]["subject_id"] == "001"
    assert len(summary["segments"]) == 2
    assert summary["participants"][0]["rows"] == 600


def test_participant_summary_reports_held_fraction(tmp_path):
    frame = build(tmp_path, make_layout_a(periods=60))
    summary = prep.roll_up_coverage({"001": frame}, {"001": []})
    record = summary["participants"][0]

    assert record["dexcom"]["fresh_count"] == 12
    assert record["dexcom"]["held_count"] == 48

def test_stream_with_a_single_observation_reports_no_gap(tmp_path):
    """One reading cannot bound a gap, and must not raise."""
    text = (
        "Timestamp,Dexcom GL,Libre GL\n"
        "2021-09-01 00:00:00,100.0,90.0\n"
        "2021-09-01 00:01:00,,\n"
        "2021-09-01 00:02:00,,90.0\n"
    )
    frame = build(tmp_path, text)
    gaps = prep.detect_gaps(frame, DEFAULT_CONFIG)

    assert [g for g in gaps if g["stream"] == "dexcom"] == []


# ---------------------------------------------------------------------------
# meals
# ---------------------------------------------------------------------------
def test_meals_are_extracted_from_the_canonical_frame(tmp_path):
    """Regression: the pipeline hands extract_meals the canonical frame, so meal
    extraction must read canonical column names rather than the internal ones."""
    frame = build(tmp_path, make_layout_a(periods=120))
    meals = prep.extract_meals(frame)

    assert len(meals) == 1, "the fixture logs exactly one meal"
    meal = meals.iloc[0]
    assert meal[schema.SUBJECT_ID] == "001"
    assert meal[schema.MEAL_TYPE] == "Lunch"
    assert meal[schema.MEAL_TIMESTAMP] == frame.loc[frame[schema.MEAL_TYPE] == "Lunch", schema.TIMESTAMP].iloc[0]


def test_meal_macros_survive_extraction(tmp_path):
    frame = build(tmp_path, make_layout_a(periods=120))
    meal = prep.extract_meals(frame).iloc[0]

    assert meal[schema.MEAL_CARBS] == pytest.approx(78)
    assert meal[schema.MEAL_CALORIES] == pytest.approx(620)
    assert bool(meal[schema.MEAL_HAS_COMPLETE_MACROS]) is True


def test_incomplete_meal_macros_are_flagged_not_filled(tmp_path):
    """A meal logged with only carbs present must not be padded with zeros."""
    frame = build(tmp_path, make_missing_meal_macros())
    meal = prep.extract_meals(frame).iloc[0]

    assert meal[schema.MEAL_CARBS] == pytest.approx(15)
    assert pd.isna(meal[schema.MEAL_CALORIES])
    assert bool(meal[schema.MEAL_HAS_COMPLETE_MACROS]) is False


def test_canonical_frame_carries_the_meal_columns(tmp_path):
    frame = build(tmp_path, make_layout_a(periods=60))

    for column in (schema.MEAL_TYPE, schema.MEAL_CALORIES, schema.MEAL_CARBS,
                   schema.MEAL_PROTEIN, schema.MEAL_FAT, schema.MEAL_FIBER):
        assert column in frame.columns
