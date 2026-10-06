"""Adversarial integrity tests for the preprocessing pipeline.

These tests exist to *falsify* the pipeline's central promise: no raw glucose value is
ever modified, dropped, or silently excluded, and the analysis mask is transparent.

They are deliberately written to attack the promise, not to confirm it. Every real-data
assertion reads the CGMacros CSVs directly and derives the expected number from the file
itself, so the tests stay honest if the dataset changes. Nothing mocked: the real
``preprocess_participant`` is exercised end to end.

Real-data tests use a fixed, representative subset:

    SAMPLE = 001, 004, 007, 010, 020, 030, 038, 049

``004`` is included because its Dexcom/Libre headers are swapped and ``007`` because it
carries a ``RecordIndex`` column and skips minutes.  Cheap, cohort-wide facts (row count,
cadence, duplicate timestamps, both-null rows) are derived from all 45 participants.

The dataset is read-only; nothing here writes into it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cgm_excursions import preprocessing as prep
from cgm_excursions import schema
from cgm_excursions.config import load_config
from tests.test_preprocessing import DEFAULT_CONFIG

# --------------------------------------------------------------------------- dataset
DATASET_ROOT = Path(
    os.environ.get(
        "CGMACROS_ROOT",
        "/Users/billchen/Desktop/JupyterHealth/Datasets/CGMacros/1.0.0/extracted/CGMacros",
    )
)

PARTICIPANT_PREFIX = "CGMacros-"

# The heavy loops read these eight.  004 (swapped headers) and 007 (RecordIndex, skipped
# minutes) are mandatory: they are the two files most likely to break a naive parser.
SAMPLE = ("001", "004", "007", "010", "020", "030", "038", "049")

MAIN_CONFIG = load_config()


@dataclass(frozen=True)
class Loaded:
    subject_id: str
    csv_path: Path
    raw: pd.DataFrame  # straight from the CSV, via pandas
    out: pd.DataFrame  # through the real pipeline


def _dataset_present() -> bool:
    return DATASET_ROOT.is_dir()


def _subject_ids() -> list[str]:
    return sorted(
        d.name[len(PARTICIPANT_PREFIX):]
        for d in DATASET_ROOT.iterdir()
        if d.is_dir() and d.name.startswith(PARTICIPANT_PREFIX)
    )


def _csv_path(subject_id: str) -> Path:
    folder = DATASET_ROOT / f"{PARTICIPANT_PREFIX}{subject_id}"
    return folder / f"{folder.name}.csv"


_CACHE: dict[str, Loaded] = {}


def load(subject_id: str) -> Loaded:
    """Read one participant both raw (pandas) and through the real pipeline, once."""
    if subject_id not in _CACHE:
        path = _csv_path(subject_id)
        raw = pd.read_csv(path, low_memory=False)
        out = prep.preprocess_participant(path, subject_id=subject_id, config=MAIN_CONFIG)
        _CACHE[subject_id] = Loaded(subject_id, path, raw, out)
    return _CACHE[subject_id]


def _require_dataset() -> None:
    if not _dataset_present():
        pytest.skip(f"real CGMacros dataset not present at {DATASET_ROOT}")


@pytest.fixture(scope="module")
def sample() -> dict[str, Loaded]:
    _require_dataset()
    return {subject: load(subject) for subject in SAMPLE}


@pytest.fixture(scope="module")
def cohort() -> dict[str, Loaded]:
    _require_dataset()
    return {subject: load(subject) for subject in _subject_ids()}


# --------------------------------------------------------------------------- helpers
def independent_fresh(values: pd.Series) -> list[bool]:
    """Freshness recomputed the long way: differs from the previous non-null value."""
    flags: list[bool] = []
    previous = None
    for value in values.tolist():
        if pd.isna(value):
            flags.append(False)
        else:
            flags.append(previous is None or value != previous)
            previous = value
    return flags


def independent_duplicate_flag(out: pd.DataFrame) -> np.ndarray:
    """A timestamp repeated among one stream's *observed* rows."""
    flag = np.zeros(len(out), dtype=bool)
    for stream in schema.SENSORS:
        observed = out[schema.RAW_COLUMN[stream]].notna()
        times = out.loc[observed, schema.TIMESTAMP]
        repeated = times.duplicated(keep=False)
        marker = np.zeros(len(out), dtype=bool)
        marker[out.index.get_indexer(times.index[repeated])] = True
        flag |= marker
    return flag


def independent_gaps(
    out: pd.DataFrame, stream: str, min_gap_seconds: float
) -> list[tuple[pd.Timestamp, pd.Timestamp, float]]:
    """Recompute one stream's gaps by walking its own observations."""
    observations = out.loc[
        out[schema.RAW_COLUMN[stream]].notna(), schema.TIMESTAMP
    ].reset_index(drop=True)
    gaps: list[tuple[pd.Timestamp, pd.Timestamp, float]] = []
    if len(observations) < 2:
        return gaps
    deltas = observations.diff().dt.total_seconds()
    for position in range(1, len(observations)):
        if deltas.iloc[position] >= min_gap_seconds:
            gaps.append(
                (
                    observations.iloc[position - 1],
                    observations.iloc[position],
                    float(deltas.iloc[position]),
                )
            )
    return gaps


def write_csv(tmp_path: Path, rows: list[list], name: str = "participant.csv") -> Path:
    frame = pd.DataFrame(rows, columns=["Timestamp", "Dexcom GL", "Libre GL"])
    path = tmp_path / name
    frame.to_csv(path, index=False)
    return path


def build(tmp_path: Path, rows: list[list], subject: str = "F") -> pd.DataFrame:
    return prep.preprocess_participant(
        write_csv(tmp_path, rows), subject_id=subject, config=DEFAULT_CONFIG
    )


# ===========================================================================
# 1. ROW PRESERVATION
# ===========================================================================
def test_row_count_equals_input_for_every_real_participant(cohort):
    """len(output) == number of data rows in the input CSV, for all 45 participants."""
    assert len(cohort) > 0
    offenders = {
        subject: (len(loaded.raw), len(loaded.out))
        for subject, loaded in cohort.items()
        if len(loaded.out) != len(loaded.raw)
    }
    assert offenders == {}, f"row count changed for {offenders}"


def test_row_preservation_checked_for_the_named_sample(cohort):
    assert {"004", "007"}.issubset(set(SAMPLE))
    for subject in SAMPLE:
        loaded = cohort[subject]
        assert len(loaded.out) == len(loaded.raw), f"{subject} changed row count"
        # one row per input row, and no row invented
        assert len(loaded.out) == len(loaded.raw)


# ===========================================================================
# 2. VALUE PRESERVATION
# ===========================================================================
@pytest.mark.parametrize("stream,column,raw_name", [
    ("dexcom", schema.DEXCOM_RAW, "Dexcom GL"),
    ("libre", schema.LIBRE_RAW, "Libre GL"),
])
def test_values_survive_unchanged_and_in_time_order(sample, stream, column, raw_name):
    """Every non-null input value appears unchanged, in the same order, none added."""
    for subject, loaded in sample.items():
        # Precondition for an order comparison: the file is already time-ordered.
        input_times = pd.to_datetime(loaded.raw["Timestamp"])
        assert input_times.is_monotonic_increasing, f"{subject} input not time-ordered"

        source = loaded.raw[raw_name].dropna().astype(float).tolist()
        produced = loaded.out[column].dropna().astype(float).tolist()

        assert produced == source, f"{subject}/{stream}: values changed or reordered"
        assert loaded.raw[raw_name].notna().sum() == loaded.out[column].notna().sum(), (
            f"{subject}/{stream}: observation count changed"
        )


def test_no_glucose_value_is_invented(sample):
    """Nothing is added: the output's non-null count never exceeds the input's."""
    for subject, loaded in sample.items():
        for raw_name, column in (
            ("Dexcom GL", schema.DEXCOM_RAW),
            ("Libre GL", schema.LIBRE_RAW),
        ):
            assert loaded.out[column].notna().sum() <= loaded.raw[raw_name].notna().sum(), (
                f"{subject}: a value appeared from nowhere in {column}"
            )


def test_real_cohort_has_no_out_of_range_values(cohort):
    """Documents *why* the out-of-range case must be synthetic: the cohort has none."""
    total = sum(int(loaded.out[schema.QC_OUT_OF_RANGE].sum()) for loaded in cohort.values())
    assert total == 0


def test_out_of_range_value_is_flagged_and_still_survives(tmp_path):
    """No real participant is out of range, so this is exercised synthetically."""
    frame = build(
        tmp_path,
        [["2020-01-01 00:00:00", 39.0, 90.0],
         ["2020-01-01 00:01:00", 500.0, 91.0],
         ["2020-01-01 00:02:00", 100.0, 92.0]],
    )
    flagged = frame.loc[frame[schema.QC_OUT_OF_RANGE]]
    assert len(flagged) == 2
    assert frame[schema.DEXCOM_RAW].iloc[0] == pytest.approx(39.0)
    assert frame[schema.DEXCOM_RAW].iloc[1] == pytest.approx(500.0)


# ===========================================================================
# 3. FLAG CONTAINMENT — flags are additive
# ===========================================================================
@pytest.mark.parametrize("column,raw_name", [
    (schema.DEXCOM_RAW, "Dexcom GL"),
    (schema.LIBRE_RAW, "Libre GL"),
])
def test_flags_never_rewrite_a_value_multiset(sample, column, raw_name):
    """Sort-and-compare: flagging cannot change the multiset of raw values."""
    for subject, loaded in sample.items():
        expected = sorted(loaded.raw[raw_name].dropna().astype(float).tolist())
        produced = sorted(loaded.out[column].dropna().astype(float).tolist())
        assert produced == expected, f"{subject}/{column}: value multiset altered by flags"


# ===========================================================================
# 4. ELIGIBILITY IS DERIVED, NOT ARBITRARY
# ===========================================================================
def test_qc_eligible_is_exactly_value_present_and_not_duplicate(sample):
    """qc_eligible == (analysis_glucose.notna() AND NOT qc_duplicate_timestamp)."""
    for subject, loaded in sample.items():
        out = loaded.out
        # Recompute the duplicate guard independently from the timestamps themselves.
        independent = independent_duplicate_flag(out)
        assert np.array_equal(
            out[schema.QC_DUPLICATE_TIMESTAMP].to_numpy(bool), independent
        ), f"{subject}: duplicate-timestamp flag disagrees with an independent recompute"

        expected = out[schema.ANALYSIS_GLUCOSE].notna().to_numpy(bool) & ~independent
        assert np.array_equal(
            out[schema.QC_ELIGIBLE].to_numpy(bool), expected
        ), f"{subject}: qc_eligible is not the derived mask"


def test_analysis_glucose_is_a_pure_view_of_the_primary_stream(sample):
    """The analysis value is Dexcom copied across, never a fusion with Libre."""
    for subject, loaded in sample.items():
        out = loaded.out
        equal = out[schema.ANALYSIS_GLUCOSE].fillna(-1) == out[schema.DEXCOM_RAW].fillna(-1)
        assert bool(equal.all()), f"{subject}: analysis_glucose is not the raw Dexcom value"


def test_a_screening_flag_coexists_with_eligibility_in_real_data(sample):
    """A flatline / rate flag must never silently clear the mask."""
    corroborated = 0
    for subject, loaded in sample.items():
        out = loaded.out
        screening = (
            out[schema.QC_FLATLINE]
            | out[schema.QC_RATE_OF_CHANGE]
            | out[schema.QC_OUT_OF_RANGE]
            | out[schema.QC_ISOLATED_SPIKE]
            | out[schema.QC_COMPRESSION_LOW]
        )
        corroborated += int((screening & out[schema.QC_ELIGIBLE]).sum())
    assert corroborated > 0, "no real row carries a screening flag while staying eligible"


def test_out_of_range_and_flatline_do_not_clear_eligibility_synthetic(tmp_path):
    """Synthetic corroboration for the case the real cohort does not contain."""
    frame = build(
        tmp_path,
        [["2020-01-01 00:00:00", 500.0, 90.0],
         ["2020-01-01 00:01:00", 500.0, 91.0],
         ["2020-01-01 00:02:00", 500.0, 92.0]],
    )
    assert frame[schema.QC_OUT_OF_RANGE].all()
    assert frame[schema.QC_ELIGIBLE].all()


# ===========================================================================
# 5. FRESHNESS IS TOTAL AND CONSISTENT
# ===========================================================================
@pytest.mark.parametrize("stream,column", [
    ("dexcom", schema.DEXCOM_RAW),
    ("libre", schema.LIBRE_RAW),
])
def test_fresh_rows_are_exactly_the_changed_observations(sample, stream, column):
    for subject, loaded in sample.items():
        expected = independent_fresh(loaded.out[column])
        produced = loaded.out[schema.FRESH_COLUMN[stream]].to_numpy(bool).tolist()
        assert produced == expected, f"{subject}/{stream}: freshness disagree with recompute"
        assert sum(produced) == sum(expected)


@pytest.mark.parametrize("stream,column", [
    ("dexcom", schema.DEXCOM_RAW),
    ("libre", schema.LIBRE_RAW),
])
def test_no_row_is_fresh_when_its_value_is_null(sample, stream, column):
    for subject, loaded in sample.items():
        fresh = loaded.out[schema.FRESH_COLUMN[stream]].to_numpy(bool)
        null = loaded.out[column].isna().to_numpy(bool)
        assert not bool((fresh & null).any()), f"{subject}/{stream}: a null row is marked fresh"


# ===========================================================================
# 6. SEGMENT INTEGRITY
# ===========================================================================
def test_segment_id_is_non_null_exactly_for_eligible_rows(sample):
    for subject, loaded in sample.items():
        out = loaded.out
        eligible = out[schema.QC_ELIGIBLE].to_numpy(bool)
        segment = out[schema.SEGMENT_ID]
        assert bool(segment[eligible].notna().all()), f"{subject}: eligible row without segment"
        assert bool(segment[~eligible].isna().all()), f"{subject}: ineligible row with segment"


def test_segment_ids_are_contiguous_from_one(sample):
    for subject, loaded in sample.items():
        ids = loaded.out[schema.SEGMENT_ID].dropna().astype(int)
        if len(ids) == 0:
            continue
        assert ids.min() == 1, f"{subject}: segments do not start at 1"
        assert sorted(set(ids.tolist())) == list(range(1, int(ids.max()) + 1)), (
            f"{subject}: segment ids are not contiguous"
        )


def test_no_segment_contains_a_step_at_or_above_the_break_threshold(sample):
    """Internal steps only: a segment's first row may inherit a large incoming gap."""
    break_seconds = float(MAIN_CONFIG["gaps"]["segment_break_seconds"])
    for subject, loaded in sample.items():
        out = loaded.out
        eligible = out[schema.QC_ELIGIBLE]
        segments = out.loc[eligible]
        for segment_id, group in segments.groupby(schema.SEGMENT_ID):
            internal = (
                group[schema.TIMESTAMP].sort_values().diff().dt.total_seconds().dropna()
            )
            assert (internal < break_seconds).all(), (
                f"{subject}: segment {segment_id} spans a step >= {break_seconds}s"
            )


# ===========================================================================
# 7. GAP INTEGRITY
# ===========================================================================
def test_reported_gaps_match_an_independent_recompute(cohort):
    """Recompute 007's gaps by hand and compare count, bounds and duration exactly."""
    out = cohort["007"].out
    min_gap = float(MAIN_CONFIG["gaps"]["min_gap_seconds"])
    reported = prep.detect_gaps(out, MAIN_CONFIG)
    for stream in schema.SENSORS:
        expected = independent_gaps(out, stream, min_gap)
        produced = [
            (gap["start"], gap["end"], gap["duration_seconds"])
            for gap in reported
            if gap["stream"] == stream
        ]
        assert len(produced) == len(expected), f"{stream}: gap count differs"
        for (start, end, duration), (e_start, e_end, e_duration) in zip(produced, expected):
            assert start == e_start and end == e_end
            assert duration == pytest.approx(e_duration)


def test_every_reported_gap_meets_the_minimum(sample):
    min_gap = float(MAIN_CONFIG["gaps"]["min_gap_seconds"])
    for subject, loaded in sample.items():
        for gap in prep.detect_gaps(loaded.out, MAIN_CONFIG):
            assert gap["duration_seconds"] >= min_gap, (
                f"{subject}: gap of {gap['duration_seconds']}s below {min_gap}s"
            )


def test_gaps_are_per_stream(tmp_path):
    """A Dexcom outage is a Dexcom gap; Libre keeps reporting and has none."""
    frame = build(
        tmp_path,
        [
            [ts.strftime("%Y-%m-%d %H:%M:%S"), None if 5 <= i < 40 else 120.0, 90.0]
            for i, ts in enumerate(pd.date_range("2022-03-02 07:00:00", periods=60, freq="60s"))
        ],
    )
    gaps = prep.detect_gaps(frame, DEFAULT_CONFIG)
    dexcom = [g for g in gaps if g["stream"] == "dexcom"]
    libre = [g for g in gaps if g["stream"] == "libre"]
    assert dexcom and not libre, f"gap attribution leaked across streams: {gaps}"


def test_gap_detection_uses_observations_not_rows(tmp_path):
    """A run of nulls is one gap, not one gap per adjacent row."""
    frame = prep.preprocess_participant(
        write_csv(
            tmp_path,
            [[ts.strftime("%Y-%m-%d %H:%M:%S"), (100.0 if i in (0, 30) else None), 90.0]
             for i, ts in enumerate(pd.date_range("2022-01-01 00:00:00", periods=31, freq="60s"))],
        ),
        subject_id="F",
        config=DEFAULT_CONFIG,
    )
    gaps = [g for g in prep.detect_gaps(frame, DEFAULT_CONFIG) if g["stream"] == "dexcom"]
    assert len(gaps) == 1
    assert gaps[0]["duration_seconds"] == pytest.approx(30 * 60)


# ===========================================================================
# 8. NO ROW IS EVER DROPPED BY AN EXCLUSION RULE
# ===========================================================================
def test_every_row_flagging_still_yields_the_same_row_count(tmp_path):
    """A participant whose every row is flagged (out of range + flatline) keeps all rows."""
    rows = [[f"2020-01-01 00:{m:02d}:00", 500.0, 600.0] for m in range(25)]
    frame = build(tmp_path, rows)
    assert len(frame) == 25
    assert frame[schema.QC_OUT_OF_RANGE].all()
    assert frame[schema.QC_FLATLINE].all()
    assert frame[schema.DEXCOM_RAW].iloc[0] == pytest.approx(500.0)


def test_every_row_ineligible_still_yields_the_same_row_count(tmp_path):
    """All rows share one timestamp -> every row is a hard duplicate, none is dropped."""
    rows = [["2020-01-01 00:00:00", 100.0 + m, 90.0] for m in range(20)]
    frame = build(tmp_path, rows)
    assert len(frame) == 20
    assert frame[schema.QC_DUPLICATE_TIMESTAMP].all()
    assert not frame[schema.QC_ELIGIBLE].any()
    assert frame[schema.SEGMENT_ID].isna().all()
    assert frame[schema.DEXCOM_RAW].tolist() == [100.0 + m for m in range(20)]


# ===========================================================================
# Derived cohort facts (keep the tests honest if the data changes)
# ===========================================================================
def test_cohort_row_total_is_the_sum_of_the_csvs(cohort):
    total = sum(len(loaded.raw) for loaded in cohort.values())
    assert total == sum(len(loaded.out) for loaded in cohort.values())


def test_cohort_cadence_is_never_faster_than_sixty_seconds(cohort):
    """One row per minute: no participant samples faster than 60 s."""
    for subject, loaded in cohort.items():
        smallest = loaded.out[schema.TIMESTAMP].diff().dt.total_seconds().dropna().min()
        assert smallest >= 60.0, f"{subject}: cadence {smallest}s is faster than 60s"


def test_cohort_has_no_duplicate_timestamps(cohort):
    for subject, loaded in cohort.items():
        assert not loaded.out[schema.TIMESTAMP].duplicated().any(), f"{subject}: duplicate ts"


def test_cohort_has_no_row_with_both_sensors_null(cohort):
    for subject, loaded in cohort.items():
        both_null = loaded.out[schema.DEXCOM_RAW].isna() & loaded.out[schema.LIBRE_RAW].isna()
        assert not bool(both_null.any()), f"{subject}: a row has both sensors null"


# ===========================================================================
# BUG REGRESSION — rate of change must divide by time since the previous OBSERVATION
# ===========================================================================
def test_rate_of_change_uses_time_since_the_previous_observation(tmp_path):
    """100 -> (null minute) -> 106 is 3 mg/dL/min, not 6; the gap must count."""
    frame = build(
        tmp_path,
        [["2020-01-01 00:00:00", 100.0, 90.0],
         ["2020-01-01 00:01:00", None, 91.0],
         ["2020-01-01 00:02:00", 106.0, 92.0]],
    )
    assert frame[schema.DEXCOM_RAW].iloc[2] == pytest.approx(106.0)
    assert not bool(frame[schema.QC_RATE_OF_CHANGE].any()), (
        "6 mg/dL over 2 minutes is 3 mg/dL/min and must not be flagged"
    )


def test_rate_of_change_still_flags_a_genuine_fast_change(tmp_path):
    """The rule must still fire when the change really is fast."""
    frame = build(
        tmp_path,
        [["2020-01-01 00:00:00", 100.0, 90.0],
         ["2020-01-01 00:01:00", 106.0, 92.0]],
    )
    assert frame[schema.QC_RATE_OF_CHANGE].tolist() == [False, True]
