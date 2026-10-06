"""An audit must report the cadence TAIL, not only the median.

A median-only cadence summary is actively misleading. Every one of the 45 CGMacros
participants has a median row-to-row interval of exactly 60 s, so reporting the median
alone reads as "uniform 60 s cadence" while 1,155 real intervals exceed it across 10
participants. The median cannot see a tail by construction, so these tests pin the tail
explicitly -- both the common case (isolated skipped minutes) and the unique case of
participant 018, whose 15-row block at 15-hour spacing spans 8.8 days.
"""

from __future__ import annotations

import io
import pathlib

import pandas as pd
import pytest

from cgm_excursions.audit import _summarize_cohort, audit_participant_csv
from cgm_excursions.reading import read_participant_bytes

HEADERS = [
    "Timestamp", "Dexcom GL", "Libre GL", "HR", "Calories (Activity)", "METs",
    "Meal Type", "Calories", "Carbs", "Protein", "Fat", "Fiber",
    "Amount Consumed", "Image path",
]


def _participant_csv(start: str, offsets_minutes: list[int]) -> bytes:
    """A minimal participant file whose rows sit at explicit minute offsets."""
    base = pd.Timestamp(start)
    rows = [
        [
            (base + pd.Timedelta(minutes=offset)).strftime("%Y-%m-%d %H:%M:%S"),
            100.0 + index, 100.0 + index,
            60, 7, 1.0, None, None, None, None, None, None, None, None,
        ]
        for index, offset in enumerate(offsets_minutes)
    ]
    frame = pd.DataFrame(rows, columns=HEADERS)
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")


# offsets 0..4 then 34..37: six 60 s steps and one 1,800 s step (a 30-minute skip).
GAPPY_OFFSETS = [0, 1, 2, 3, 4, 34, 35, 36, 37]


def test_audit_reports_the_skipped_minute_tail_not_only_the_median():
    payload = _participant_csv("2024-01-01 00:00:00", GAPPY_OFFSETS)

    record = audit_participant_csv(payload, "synthetic-skip.csv")

    # The median is blind to the skipped minutes -- that is precisely the trap.
    assert record["median_interval_seconds"] == 60.0
    # The tail is what proves the cadence is not uniform.
    assert record["base_interval_seconds"] == 60.0
    assert record["max_interval_seconds"] == 1800.0
    assert record["intervals_above_base"] == 1


def test_cohort_summary_reports_skipped_minutes_and_the_longest_gap():
    clean = audit_participant_csv(_participant_csv("2024-01-01 00:00:00", [0, 1, 2, 3]), "001.csv")
    clean["subject_id"] = "001"
    gappy = audit_participant_csv(_participant_csv("2024-01-01 00:00:00", GAPPY_OFFSETS), "002.csv")
    gappy["subject_id"] = "002"

    cohort = _summarize_cohort([clean, gappy])

    assert cohort["base_interval_seconds"] == 60.0
    assert cohort["longest_interval_seconds"] == 1800.0
    assert cohort["intervals_above_base"] == 1
    assert cohort["participants_with_skipped_minutes"] == 1
    # Guard the exact regression: the old summary exposed ONLY this median-derived list,
    # which reads as "uniform 60 s" and hides the 1,800 s hole completely. The assertion
    # documents why the median was insufficient, while the keys above carry the truth.
    assert cohort["cadences_seconds"] == [60.0]


def test_uniform_cadence_still_reports_zero_skipped_minutes():
    """The tail reporting must not fire on genuinely uniform input."""
    clean = audit_participant_csv(_participant_csv("2024-01-01 00:00:00", [0, 1, 2, 3]), "001.csv")
    clean["subject_id"] = "001"

    cohort = _summarize_cohort([clean])

    assert cohort["intervals_above_base"] == 0
    assert cohort["participants_with_skipped_minutes"] == 0
    assert cohort["longest_interval_seconds"] == 60.0


# ------------------------------- real dataset: the one participant whose cadence breaks
CG_MACROS_PARTICIPANTS = pathlib.Path(
    "/Users/billchen/Desktop/JupyterHealth/Datasets/CGMacros/1.0.0/extracted/CGMacros"
)


@pytest.mark.skipif(
    not CG_MACROS_PARTICIPANTS.exists(),
    reason="local CGMacros dataset not present",
)
def test_participant_018_is_a_sparse_BLOCK_not_a_single_hole():
    """Participant 018 is the only file with a RUN of long steps, not one isolated jump.

    Its middle regime is 15 consecutive rows at ~15-hour spacing spanning 8.8 days, with
    Dexcom absent from every one. Anyone describing this as "a 15-hour hole" is wrong:
    the hole is 15 rows wide. Pinning the shape keeps docs/dataset-shape.md honest.
    """
    payload = (CG_MACROS_PARTICIPANTS / "CGMacros-018" / "CGMacros-018.csv").read_bytes()

    record = audit_participant_csv(payload, "CGMacros-018.csv")

    assert record["rows"] == 14085
    assert record["base_interval_seconds"] == 60.0
    assert record["max_interval_seconds"] == 54060.0
    # 15 intervals above the 60 s base -- a contiguous block, not one spike.
    assert record["intervals_above_base"] == 15


@pytest.mark.skipif(
    not CG_MACROS_PARTICIPANTS.exists(),
    reason="local CGMacros dataset not present",
)
def test_only_one_participant_has_a_run_of_long_steps():
    """Exactly one file in the cohort contains consecutive long steps; all other long
    steps are isolated single skips. This is what separates 'skipped minutes' (common)
    from 'recording regime change' (unique to 018)."""
    files = sorted(CG_MACROS_PARTICIPANTS.glob("CGMacros-*/CGMacros-*.csv"))
    assert len(files) == 45

    with_runs = []
    for path in files:
        frame, _ = read_participant_bytes(path.read_bytes(), source_name=path.name)
        steps = frame["timestamp"].diff().dt.total_seconds() / 60
        long = steps >= 60
        # a run is at least two CONSECUTIVE long steps
        consecutive = long & long.shift(1)
        if bool(consecutive.any()):
            with_runs.append(path.name)

    assert with_runs == ["CGMacros-018.csv"]
