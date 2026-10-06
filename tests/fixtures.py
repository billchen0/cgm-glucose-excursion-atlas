"""Synthetic CGMacros-shaped fixtures.

These deliberately reproduce the *messy* parts of the real dataset so the pipeline is
tested against the shapes that actually occur, not a tidy idealisation:

* five header layouts, including a trailing-space column and a swapped sensor pair
* one row per minute, with each sensor's value carried forward between refreshes
* a participant whose Dexcom stream stops for hours while Libre keeps reporting
* a meal row, including one with incomplete macronutrients
"""

from __future__ import annotations

import io
import textwrap

import pandas as pd
import pytest


def minute_range(start: str, count: int) -> pd.DatetimeIndex:
    return pd.date_range(start=start, periods=count, freq="60s")


def _csv(columns: list[str], rows: list[list]) -> str:
    frame = pd.DataFrame(rows, columns=columns)
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False)
    return buffer.getvalue()


def _dexcom_values(readings: list[float]) -> list[float]:
    """Expand one reading per 5 minutes onto a true 1-minute grid."""
    out: list[float] = []
    for value in readings:
        out.extend([value] * 5)
    return out


def _libre_values(readings: list[float]) -> list[float]:
    """Expand one reading per 15 minutes onto a true 1-minute grid."""
    out: list[float] = []
    for value in readings:
        out.extend([value] * 15)
    return out


# ---------------------------------------------------------------------------
# Layout A — the common case: unnamed index, Libre before Dexcom, METs
# ---------------------------------------------------------------------------
def make_layout_a(periods: int = 60) -> str:
    timestamps = minute_range("2020-05-01 11:39:00", periods)
    dexcom = _dexcom_values([141.0, 144.6, 148.2]) * 4
    libre = _libre_values([94.4, 95.3, 96.3, 97.2]) * 1
    rows = []
    for i, ts in enumerate(timestamps):
        rows.append([
            i,
            ts.strftime("%Y-%m-%d %H:%M:%S"),
            libre[i] if i < len(libre) else None,
            dexcom[i] if i < len(dexcom) else None,
            72, 1.5, 1.2,
            "Lunch" if i == 30 else None,
            620, 78, 32, 22, 9, "1 serving" if i == 30 else None,
            "images/001/00000075-9-48.jpg" if i == 30 else None,
        ])
    return _csv(
        [
            "Unnamed: 0", "Timestamp", "Libre GL", "Dexcom GL", "HR",
            "Calories (Activity)", "METs", "Meal Type", "Calories", "Carbs",
            "Protein", "Fat", "Fiber", "Amount Consumed ", "Image path",
        ],
        rows,
    )


# ---------------------------------------------------------------------------
# Layout B — sensors swapped (the CGMacros-004 trap) and no index column
# ---------------------------------------------------------------------------
def make_layout_b_swapped_sensors(periods: int = 30) -> str:
    timestamps = minute_range("2023-09-11 09:54:00", periods)
    rows = []
    for i, ts in enumerate(timestamps):
        rows.append([
            ts.strftime("%Y-%m-%d %H:%M:%S"),
            150.0 + (i % 3) * 0.1,   # Dexcom first  -> must still land in the Dexcom column
            90.0 + (i % 5) * 0.1,    # Libre second
            70, 1.0, 1.1, None, None, None, None, None, None, None, None,
        ])
    return _csv(
        [
            "Timestamp", "Dexcom GL", "Libre GL", "HR", "Calories (Activity)",
            "METs", "Meal Type", "Calories", "Carbs", "Protein", "Fat", "Fiber",
            "Amount Consumed", "Image path",
        ],
        rows,
    )


# ---------------------------------------------------------------------------
# Layout C — Steps + RecordIndex present, no index column, Intensity not METs
# ---------------------------------------------------------------------------
def make_layout_c_steps_index(periods: int = 20) -> str:
    timestamps = minute_range("2024-01-28 08:10:00", periods)
    rows = []
    for i, ts in enumerate(timestamps):
        rows.append([
            ts.strftime("%Y-%m-%d %H:%M:%S"),
            100.0, 120.0, 65, 7, 2.0, None, i, None, None, None, None, None, None, None,
        ])
    return _csv(
        [
            "Timestamp", "Libre GL", "Dexcom GL", "HR", "Steps", "METs",
            "Meal Type", "RecordIndex", "Calories", "Carbs", "Protein", "Fat",
            "Fiber", "Amount Consumed", "Image path",
        ],
        rows,
    )


# ---------------------------------------------------------------------------
# The irregular participant: Dexcom drops out for 4 hours, Libre keeps reporting
# ---------------------------------------------------------------------------
OUTAGE_START = 120
OUTAGE_END = 360


def make_dexcom_outage(periods: int = 600) -> str:
    """Dexcom stops reporting for rows 120-359 while Libre keeps reporting.

    ``periods`` must exceed ``OUTAGE_END`` or the frame is truncated before the outage
    and the fixture silently stops testing what it is named for.
    """
    if periods <= OUTAGE_END:
        raise ValueError(
            f"periods={periods} truncates the outage (rows {OUTAGE_START}-{OUTAGE_END - 1}); "
            f"pass at least {OUTAGE_END + 1}"
        )
    timestamps = minute_range("2022-03-02 07:00:00", periods)
    rows = []
    for i, ts in enumerate(timestamps):
        in_outage = OUTAGE_START <= i < OUTAGE_END
        rows.append([
            i,
            ts.strftime("%Y-%m-%d %H:%M:%S"),
            110.0 + (i % 4) * 0.1,
            None if in_outage else 130.0 + (i % 6) * 0.1,
            70, 1.0, 1.0, None, None, None, None, None, None, None, None,
        ])
    return _csv(
        [
            "Unnamed: 0", "Timestamp", "Libre GL", "Dexcom GL", "HR",
            "Calories (Activity)", "METs", "Meal Type", "Calories", "Carbs",
            "Protein", "Fat", "Fiber", "Amount Consumed ", "Image path",
        ],
        rows,
    )


# ---------------------------------------------------------------------------
# Flag targets, each isolated so a test can assert exactly one rule fires
# ---------------------------------------------------------------------------
def make_flatline(periods: int = 40) -> str:
    """Dexcom sits at 150.0 for 25 consecutive minutes."""
    timestamps = minute_range("2021-01-01 00:00:00", periods)
    dexcom = [150.0] * 25 + [float(160 + i) for i in range(periods - 25)]
    rows = [[i, ts.strftime("%Y-%m-%d %H:%M:%S"), 100.0, dexcom[i], 70, 1.0, 1.0,
             None, None, None, None, None, None, None, None]
            for i, ts in enumerate(timestamps)]
    return _csv(
        ["Unnamed: 0", "Timestamp", "Libre GL", "Dexcom GL", "HR",
         "Calories (Activity)", "METs", "Meal Type", "Calories", "Carbs",
         "Protein", "Fat", "Fiber", "Amount Consumed ", "Image path"],
        rows,
    )


def make_isolated_spike(periods: int = 10) -> str:
    """A single impossible jump that returns to baseline on the next sample."""
    timestamps = minute_range("2021-02-01 00:00:00", periods)
    dexcom = [120.0, 121.0, 122.0, 300.0, 123.0, 124.0, 125.0, 126.0, 127.0, 128.0]
    rows = [[i, ts.strftime("%Y-%m-%d %H:%M:%S"), 100.0, dexcom[i], 70, 1.0, 1.0,
             None, None, None, None, None, None, None, None]
            for i, ts in enumerate(timestamps)]
    return _csv(
        ["Unnamed: 0", "Timestamp", "Libre GL", "Dexcom GL", "HR",
         "Calories (Activity)", "METs", "Meal Type", "Calories", "Carbs",
         "Protein", "Fat", "Fiber", "Amount Consumed ", "Image path"],
        rows,
    )


def make_out_of_range(periods: int = 12) -> str:
    """Dexcom reports 38.0 (below range) and 412.0 (above range)."""
    timestamps = minute_range("2021-03-01 00:00:00", periods)
    dexcom = [100.0, 101.0, 38.0, 103.0, 104.0, 412.0, 106.0, 107.0, 108.0, 109.0, 110.0, 111.0]
    rows = [[i, ts.strftime("%Y-%m-%d %H:%M:%S"), 100.0, dexcom[i], 70, 1.0, 1.0,
             None, None, None, None, None, None, None, None]
            for i, ts in enumerate(timestamps)]
    return _csv(
        ["Unnamed: 0", "Timestamp", "Libre GL", "Dexcom GL", "HR",
         "Calories (Activity)", "METs", "Meal Type", "Calories", "Carbs",
         "Protein", "Fat", "Fiber", "Amount Consumed ", "Image path"],
        rows,
    )


def make_compression_low(periods: int = 8) -> str:
    timestamps = minute_range("2021-04-01 00:00:00", periods)
    dexcom = [100.0, 40.0, 40.0, 101.0, 102.0, 103.0, 104.0, 105.0]
    rows = [[i, ts.strftime("%Y-%m-%d %H:%M:%S"), 100.0, dexcom[i], 70, 1.0, 1.0,
             None, None, None, None, None, None, None, None]
            for i, ts in enumerate(timestamps)]
    return _csv(
        ["Unnamed: 0", "Timestamp", "Libre GL", "Dexcom GL", "HR",
         "Calories (Activity)", "METs", "Meal Type", "Calories", "Carbs",
         "Protein", "Fat", "Fiber", "Amount Consumed ", "Image path"],
        rows,
    )


def make_missing_meal_macros(periods: int = 6) -> str:
    timestamps = minute_range("2021-05-01 00:00:00", periods)
    rows = []
    for i, ts in enumerate(timestamps):
        is_meal = i == 2
        rows.append([
            i, ts.strftime("%Y-%m-%d %H:%M:%S"), 100.0, 120.0, 70, 1.0, 1.0,
            "Snack" if is_meal else None,
            None if is_meal else None, 15 if is_meal else None,
            None, None, None, None, None,
        ])
    return _csv(
        ["Unnamed: 0", "Timestamp", "Libre GL", "Dexcom GL", "HR",
         "Calories (Activity)", "METs", "Meal Type", "Calories", "Carbs",
         "Protein", "Fat", "Fiber", "Amount Consumed ", "Image path"],
        rows,
    )


def make_bio(subjects: list[int]) -> pd.DataFrame:
    return pd.DataFrame({
        "subject": subjects,
        "Age": [30 + s for s in subjects],
        "Gender": ["F" if s % 2 else "M" for s in subjects],
        "BMI": [24.0 + s * 0.1 for s in subjects],
        "Body weight ": [70.0 + s for s in subjects],
        "Height ": [170.0] * len(subjects),
        "Self-identify ": ["Not Hispanic/Latino"] * len(subjects),
        "A1c PDL (Lab)": [5.0 + (s % 5) * 0.4 for s in subjects],
        "Fasting GLU - PDL (Lab)": [90] * len(subjects),
        "Insulin ": [8.0] * len(subjects),
        "Triglycerides": [90] * len(subjects),
        "Cholesterol": [180] * len(subjects),
        "HDL": [55] * len(subjects),
        "Non HDL ": [125] * len(subjects),
        "LDL (Cal)": [110] * len(subjects),
        "VLDL (Cal)": [15] * len(subjects),
        "Cho/HDL Ratio": [3.3] * len(subjects),
        "Collection time PDL (Lab)": ["11:06:00 AM"] * len(subjects),
    })


@pytest.fixture
def dataset_dir(tmp_path):
    """A small but structurally faithful extracted CGMacros tree."""
    root = tmp_path / "CGMacros"
    root.mkdir()

    files = {
        "001": make_layout_a(),
        "004": make_layout_b_swapped_sensors(),
        "007": make_layout_c_steps_index(),
    }
    for participant, text in files.items():
        folder = root / f"CGMacros-{participant}"
        folder.mkdir()
        (folder / f"CGMacros-{participant}.csv").write_text(text, encoding="utf-8")

    make_bio([1, 4, 7]).to_csv(root / "bio.csv", index=False)
    return root
