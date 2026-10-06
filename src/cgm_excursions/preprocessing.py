"""The CGM preprocessing pipeline, in the order it runs.

Read this file top to bottom and you have read the whole pipeline. Each stage is one
function, does one thing, and returns a frame that the next stage can consume. Nothing
here deletes, clips, smooths, interpolates, or repairs a glucose value: questionable
data gets a named flag and stays in place, and the analysis mask is a separate column so
that an exclusion is always an explicit, auditable choice made later.

The one non-obvious stage is ``mark_fresh_observations``. See ``docs/dataset-shape.md``:
the CGMacros files are one row per minute, and each sensor's reading is carried forward
until it refreshes. Without marking freshness, a consumer cannot tell a new measurement
from a held copy, and a fixed grid would invent a sampling pattern the file does not have.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import schema
from .reading import MEAL_COLUMNS, read_participant

# ===========================================================================
# Stage 1 — type and sort
# ===========================================================================
def type_and_sort(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize dtypes and put rows in time order.

    Duplicate timestamps are *not* resolved here. They are flagged downstream so that the
    conflict is visible rather than silently collapsed.
    """
    out = frame.sort_values("timestamp", kind="stable").reset_index(drop=True)
    # From here on the timestamp column carries its canonical name, so no later stage
    # has to remember which of two names is current.
    out = out.rename(columns={"timestamp": "timestamp"})
    out["timestamp"] = pd.to_datetime(out["timestamp"])
    for stream in schema.SENSORS:
        out[stream] = pd.to_numeric(out[stream], errors="coerce").astype("float64")
    for meal_field in MEAL_COLUMNS:
        if meal_field in out.columns and meal_field != "meal_type":
            out[meal_field] = pd.to_numeric(out[meal_field], errors="coerce")
    if "meal_type" in out.columns:
        out["meal_type"] = out["meal_type"].astype("object")
    return out


def add_elapsed_minutes(frame: pd.DataFrame) -> pd.DataFrame:
    """Minutes since the participant's first sample — the primary time axis.

    Upstream shifted every participant's dates, so the calendar values are not real and
    are never used as an axis.
    """
    out = frame.copy()
    origin = out["timestamp"].iloc[0]
    out[schema.ELAPSED_MINUTES] = (
        (out["timestamp"] - origin).dt.total_seconds() / 60.0
    ).astype("float64")
    return out


# ===========================================================================
# Stage 2 — value integrity
# ===========================================================================
def flag_values(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Flag values outside a stream's documented analog range, plus the low sentinel.

    Both flags are informational. Neither removes the value, and neither clears
    eligibility: a range rule is a screen, not a correction.
    """
    out = frame.copy()
    ranges = config["streams"]["documented_range_mgdl"]
    qc = config["qc"]

    out[schema.QC_OUT_OF_RANGE] = False
    for stream in schema.SENSORS:
        low, high = ranges[stream]
        values = out[stream]
        outside = values.notna() & ((values < low) | (values > high))
        out[schema.QC_OUT_OF_RANGE] |= outside.fillna(False).astype(bool)

    low_marker = qc.get("possible_compression_low", {})
    if low_marker.get("enabled", True):
        sentinel = float(low_marker.get("value_mgdl", 40))
        out[schema.QC_COMPRESSION_LOW] = False
        for stream in schema.SENSORS:
            out[schema.QC_COMPRESSION_LOW] |= (out[stream] == sentinel).fillna(False)
        out[schema.QC_COMPRESSION_LOW] = out[schema.QC_COMPRESSION_LOW].astype(bool)
    else:
        out[schema.QC_COMPRESSION_LOW] = False

    return out


# ===========================================================================
# Stage 3 — per-stream quality control
# ===========================================================================
def flag_duplicate_timestamps(frame: pd.DataFrame) -> pd.DataFrame:
    """Flag a timestamp that repeats within the same stream.

    Never observed in CGMacros (0 in 687,580 rows), kept as a guard so a future export
    cannot quietly introduce a conflict. This is a **hard** flag: a genuine duplicate
    timestamp means two different values claim the same instant, and a downstream
    detector cannot resolve that on its own.
    """
    out = frame.copy()
    out[schema.QC_DUPLICATE_TIMESTAMP] = False
    for stream in schema.SENSORS:
        observed = out[out[stream].notna()]
        repeated = observed["timestamp"].duplicated(keep=False)
        if repeated.any():
            out.loc[observed.index[repeated], schema.QC_DUPLICATE_TIMESTAMP] = True
    return out


def flag_rate_of_change(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Flag a sample whose change since the previous observation is physiologically fast.

    The rate is attributed to the **later** sample only, so one rapid transition raises
    one flag rather than two.
    """
    settings = config["qc"].get("rate_of_change", {})
    out = frame.copy()
    out[schema.QC_RATE_OF_CHANGE] = False
    if not settings.get("enabled", True):
        return out

    limit = float(settings.get("max_mgdl_per_min", 4.0))
    for stream in schema.SENSORS:
        values = out[stream]
        observed = values.notna()
        previous = values.where(observed).ffill().shift(1)
        # Time must be measured between the *same* two observations the value change is
        # measured between. Dividing by the previous *row* instead of the previous
        # *observation* understates the interval across an intervening null and inflates
        # the rate, flagging a genuinely slow change as physiologically fast.
        previous_time = out["timestamp"].where(observed).ffill().shift(1)
        delta_value = (values - previous).abs()
        delta_minutes = (out["timestamp"] - previous_time).dt.total_seconds() / 60.0
        rate = delta_value / delta_minutes
        fired = (rate > limit) & observed & previous.notna()
        out[schema.QC_RATE_OF_CHANGE] |= fired.fillna(False).astype(bool)
    return out


def flag_flatline(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Flag a run of identical consecutive readings long enough to be a stuck sensor.

    A run's length is converted to minutes using the participant's own sampling interval,
    so the threshold means the same thing in a 1-minute file and any future 5-minute file.
    """
    settings = config["qc"].get("flatline", {})
    out = frame.copy()
    out[schema.QC_FLATLINE] = False
    if not settings.get("enabled", True):
        return out

    min_minutes = float(settings.get("min_run_minutes", 20))
    cadence = _typical_cadence_minutes(out)
    min_samples = max(1, int(round(min_minutes / cadence)))

    for stream in schema.SENSORS:
        values = out[stream]
        observed = values.notna()
        breaks = values.ne(values.shift()) | ~observed
        run_id = breaks.cumsum()
        run_length = values.groupby(run_id).transform("size")
        out[schema.QC_FLATLINE] |= observed & (run_length >= min_samples)
    return out


def flag_isolated_spike(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Flag a single sample far from its neighbours while the neighbours agree.

    Requiring the neighbours to be close to each other is what separates an isolated
    spike from a genuine fast excursion, which moves the whole neighbourhood.
    """
    settings = config["qc"].get("isolated_spike", {})
    out = frame.copy()
    out[schema.QC_ISOLATED_SPIKE] = False
    if not settings.get("enabled", True):
        return out

    min_delta = float(settings.get("min_delta_mgdl", 50))
    neighbour_max = float(settings.get("neighbour_max_delta_mgdl", 25))

    for stream in schema.SENSORS:
        values = out[stream]
        previous = values.shift(1)
        following = values.shift(-1)
        neighbours_agree = (following - previous).abs() <= neighbour_max
        deviates = ((values - previous).abs() >= min_delta) & (
            (values - following).abs() >= min_delta
        )
        fired = values.notna() & previous.notna() & following.notna() & neighbours_agree & deviates
        out[schema.QC_ISOLATED_SPIKE] |= fired
    return out


def _typical_cadence_minutes(frame: pd.DataFrame) -> float:
    """Median sampling interval in minutes, falling back to 1.0 for degenerate frames."""
    if len(frame) < 2:
        return 1.0
    deltas = frame["timestamp"].diff().dt.total_seconds().dropna() / 60.0
    deltas = deltas[deltas > 0]
    if deltas.empty:
        return 1.0
    return float(deltas.median())


# ===========================================================================
# Stage 4 — freshness
# ===========================================================================
def mark_fresh_observations(frame: pd.DataFrame) -> pd.DataFrame:
    """Mark whether each sensor value is a new measurement or a carried-forward copy.

    A reading is fresh when it differs from that stream's previous non-null reading; the
    first reading in a stream is always fresh. This is a reconstruction, not a record:
    if a sensor genuinely re-reads the same value, that reading is marked held. The
    limitation is stated in the manifest so a consumer can weigh it.
    """
    out = frame.copy()
    for stream in schema.SENSORS:
        values = out[stream]
        observed = values.notna()
        previous_observation = values.where(observed).ffill().shift(1)
        changed = observed & values.ne(previous_observation)
        first = observed & previous_observation.isna()
        out[schema.FRESH_COLUMN[stream]] = (changed | first)
    return out


# ===========================================================================
# Stage 5 — analysis view, eligibility, segments
# ===========================================================================
def derive_analysis_columns(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Project the primary stream into the analysis columns, plus the eligibility mask.

    ``analysis_glucose`` is a *view* of the primary stream, never a fusion of the two.
    Dexcom and Libre are never averaged, and one is never back-filled from the other.
    """
    out = frame.copy()
    primary = config["streams"]["primary"]
    replication = config["streams"]["replication"]

    if primary not in schema.SENSORS or replication not in schema.SENSORS:
        raise ValueError(
            f"config must name two known streams; got primary={primary!r}, "
            f"replication={replication!r}, known={schema.SENSORS}"
        )

    out[schema.ANALYSIS_GLUCOSE] = out[primary].astype("float64")
    out[schema.ANALYSIS_ON_GRID] = out[primary].notna()

    hard_flags = np.zeros(len(out), dtype=bool)
    for flag in schema.HARD_QC_FLAGS:
        if flag in out.columns:
            hard_flags |= out[flag].to_numpy(dtype=bool)
    out[schema.QC_ELIGIBLE] = (
        out[schema.ANALYSIS_GLUCOSE].notna().to_numpy() & ~hard_flags
    )

    out[schema.SEGMENT_ID] = _segment_ids(out, config)
    return out


def _segment_ids(frame: pd.DataFrame, config: dict[str, Any] | None = None) -> pd.Series:
    """Number contiguous eligible runs, restarting at 1 for each participant.

    A run ends at an ineligible row, or across a gap at least ``segment_break_seconds``.
    """
    break_seconds = float(config["gaps"]["segment_break_seconds"]) if config else 3600.0

    eligible = frame[schema.QC_ELIGIBLE].to_numpy(dtype=bool)
    seconds = frame["timestamp"].diff().dt.total_seconds().to_numpy()

    ids = np.full(len(frame), np.nan, dtype="float64")
    current = 0
    for position in range(len(frame)):
        if not eligible[position]:
            continue
        starts_new = (
            position == 0
            or not eligible[position - 1]
            or (np.isfinite(seconds[position]) and seconds[position] >= break_seconds)
        )
        if starts_new:
            current += 1
        ids[position] = current
    return pd.Series(ids, index=frame.index, dtype="Float64")


# ===========================================================================
# Stage 6 — gaps
# ===========================================================================
def detect_gaps(frame: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Find missing runs in each stream's own observation series.

    Gaps are per-stream by construction: a minute where only Libre reported is a refresh
    boundary for Dexcom, not a gap introduced by the file.
    """
    min_gap_seconds = float(config["gaps"]["min_gap_seconds"])
    break_seconds = float(config["gaps"]["segment_break_seconds"])
    subject = str(frame[schema.SUBJECT_ID].iloc[0])

    gaps: list[dict[str, Any]] = []
    for stream in schema.SENSORS:
        present = frame[schema.RAW_COLUMN[stream]].notna()
        # Compare consecutive *observations*, not consecutive rows. A run of nulls is
        # exactly what a gap looks like, so adjacent rows are always one interval apart
        # and would never reveal it.
        observation_times = frame.loc[present, schema.TIMESTAMP]
        if len(observation_times) < 2:
            continue

        seconds = observation_times.diff().dt.total_seconds().to_numpy()
        for offset in np.nonzero(seconds >= min_gap_seconds)[0]:
            gaps.append({
                "subject_id": subject,
                "stream": stream,
                "start": observation_times.iloc[offset - 1],
                "end": observation_times.iloc[offset],
                "duration_seconds": float(seconds[offset]),
                "is_segment_break": bool(seconds[offset] >= break_seconds),
            })
    return gaps


# ===========================================================================
# Stage 7 — coverage rollups
# ===========================================================================
def roll_up_coverage(
    frames: dict[str, pd.DataFrame],
    gaps_by_subject: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Summarize coverage at participant, calendar-day, and contiguous-segment levels.

    "Day" is a *shifted* calendar day, so it orders the record relative to itself and is
    labelled as such in the output.
    """
    participants: list[dict[str, Any]] = []
    days: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []

    for subject, frame in sorted(frames.items()):
        record: dict[str, Any] = {
            "subject_id": subject,
            "rows": int(len(frame)),
            "first_timestamp": _iso(frame[schema.TIMESTAMP].iloc[0]),
            "last_timestamp": _iso(frame[schema.TIMESTAMP].iloc[-1]),
            "span_minutes": float(frame[schema.ELAPSED_MINUTES].iloc[-1]),
            "eligible_rows": int(frame[schema.QC_ELIGIBLE].sum()),
            "gaps": gaps_by_subject.get(subject, []),
        }
        for stream in schema.SENSORS:
            observed = frame[schema.RAW_COLUMN[stream]]
            fresh = frame[schema.FRESH_COLUMN[stream]]
            record[stream] = {
                "observed_count": int(observed.notna().sum()),
                "missing_count": int(observed.isna().sum()),
                "fresh_count": int(fresh.sum()),
                "held_count": int((observed.notna() & ~fresh).sum()),
                "held_fraction": _safe_ratio(
                    int((observed.notna() & ~fresh).sum()), int(observed.notna().sum())
                ),
                "min_mgdl": _nullable_float(observed.min()),
                "max_mgdl": _nullable_float(observed.max()),
            }
            record[stream]["longest_gap_seconds"] = max(
                (g["duration_seconds"] for g in record["gaps"] if g["stream"] == stream),
                default=0.0,
            )
        for flag in schema.QC_FLAGS:
            record[flag] = int(frame[flag].sum())
        participants.append(record)
        days.extend(_day_records(subject, frame))
        segments.extend(_segment_records(subject, frame))

    return {"participants": participants, "days": days, "segments": segments}


def _day_records(subject: str, frame: pd.DataFrame) -> list[dict[str, Any]]:
    working = frame.copy()
    working["_day"] = working[schema.TIMESTAMP].dt.date
    records: list[dict[str, Any]] = []
    for day, group in working.groupby("_day", sort=True):
        record: dict[str, Any] = {
            "subject_id": subject,
            "shifted_date": str(day),
            "rows": int(len(group)),
            "eligible_rows": int(group[schema.QC_ELIGIBLE].sum()),
            "eligible_fraction": _safe_ratio(
                int(group[schema.QC_ELIGIBLE].sum()), int(len(group))
            ),
        }
        for stream in schema.SENSORS:
            record[f"{stream}_observed"] = int(
                group[schema.RAW_COLUMN[stream]].notna().sum()
            )
            record[f"{stream}_fresh"] = int(group[schema.FRESH_COLUMN[stream]].sum())
        records.append(record)
    return records


def _segment_records(subject: str, frame: pd.DataFrame) -> list[dict[str, Any]]:
    eligible = frame.loc[frame[schema.QC_ELIGIBLE]]
    if eligible.empty:
        return []
    records: list[dict[str, Any]] = []
    for segment_id, group in eligible.groupby(schema.SEGMENT_ID, sort=True):
        records.append({
            "subject_id": subject,
            "segment_id": int(segment_id),
            "start": _iso(group[schema.TIMESTAMP].iloc[0]),
            "end": _iso(group[schema.TIMESTAMP].iloc[-1]),
            "rows": int(len(group)),
            "duration_minutes": float(
                group[schema.ELAPSED_MINUTES].iloc[-1] - group[schema.ELAPSED_MINUTES].iloc[0]
            ),
        })
    return records


# ===========================================================================
# Orchestration
# ===========================================================================
def preprocess_participant(
    path: Path,
    subject_id: str,
    config: dict[str, Any],
) -> pd.DataFrame:
    """Run every stage for one participant read from a file.

    Order matters: flags are computed on the raw observations, freshness before the
    analysis view, and segments last because they depend on eligibility.
    """
    frame, _columns = read_participant(path)
    return preprocess_from_frame(frame, subject_id=subject_id, config=config)


def preprocess_from_frame(
    frame: pd.DataFrame,
    subject_id: str,
    config: dict[str, Any],
) -> pd.DataFrame:
    """Run every stage on an already-read frame, returning the canonical frame.

    Split from ``preprocess_participant`` so a caller that already holds the frame — for
    instance one read from inside a ZIP archive — does not have to write it to disk first.
    """
    frame = type_and_sort(frame)
    frame = add_elapsed_minutes(frame)
    frame = flag_values(frame, config)
    frame = flag_duplicate_timestamps(frame)
    frame = flag_rate_of_change(frame, config)
    frame = flag_flatline(frame, config)
    frame = flag_isolated_spike(frame, config)
    frame = mark_fresh_observations(frame)
    frame = derive_analysis_columns(frame, config)
    frame[schema.SUBJECT_ID] = subject_id
    return to_canonical_frame(frame)


def to_canonical_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Rename an internal frame to the canonical written schema, in canonical order.

    This is the single boundary between the pipeline's readable internal names and the
    explicit `*_glucose_raw` names a consumer reads. Nothing downstream of this call
    should need to know the internal spelling.
    """
    renamed = frame.rename(columns={
        "timestamp": schema.TIMESTAMP,
        "dexcom": schema.DEXCOM_RAW,
        "libre": schema.LIBRE_RAW,
        "meal_type": schema.MEAL_TYPE,
        "calories": schema.MEAL_CALORIES,
        "carbs": schema.MEAL_CARBS,
        "protein": schema.MEAL_PROTEIN,
        "fat": schema.MEAL_FAT,
        "fiber": schema.MEAL_FIBER,
        "amount_consumed": schema.MEAL_AMOUNT,
    })
    for column in schema.canonical_cgm_columns():
        if column not in renamed.columns:
            renamed[column] = pd.NA
    return renamed[schema.canonical_cgm_columns()]


MEAL_MACRO_FIELDS: tuple[tuple[str, str], ...] = (
    # (the name read_participant uses internally, the canonical written column)
    ("calories", schema.MEAL_CALORIES),
    ("carbs", schema.MEAL_CARBS),
    ("protein", schema.MEAL_PROTEIN),
    ("fat", schema.MEAL_FAT),
    ("fiber", schema.MEAL_FIBER),
)


def extract_meals(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per logged meal, taken from the canonical frame's own rows.

    A meal is a row carrying a meal label. Macronutrients are preserved exactly as
    observed, including their absence: ``has_complete_macros`` records whether all four
    were present rather than filling any of them. Accepts either the internal frame (from
    ``read_participant``) or the canonical frame, because both carry the meal label and
    the pipeline hands it the canonical one.
    """
    columns = [
        schema.SUBJECT_ID, schema.MEAL_TIMESTAMP, schema.ELAPSED_MINUTES,
        schema.MEAL_TYPE, schema.MEAL_CALORIES, schema.MEAL_CARBS,
        schema.MEAL_PROTEIN, schema.MEAL_FAT, schema.MEAL_FIBER,
        schema.MEAL_AMOUNT, schema.MEAL_HAS_COMPLETE_MACROS,
    ]
    label_column = schema.MEAL_TYPE if schema.MEAL_TYPE in frame.columns else "meal_type"
    if label_column not in frame.columns:
        return pd.DataFrame(columns=columns)

    meals = frame.loc[frame[label_column].notna()].copy()
    if meals.empty:
        return pd.DataFrame(columns=columns)

    out = pd.DataFrame({
        schema.SUBJECT_ID: meals[schema.SUBJECT_ID],
        schema.MEAL_TIMESTAMP: meals[schema.TIMESTAMP],
        schema.ELAPSED_MINUTES: meals[schema.ELAPSED_MINUTES],
        schema.MEAL_TYPE: meals[label_column].astype("string").str.strip(),
    })

    for internal, canonical in MEAL_MACRO_FIELDS:
        source = canonical if canonical in meals.columns else internal
        out[canonical] = pd.to_numeric(
            meals[source] if source in meals.columns else pd.NA, errors="coerce"
        )

    if schema.MEAL_AMOUNT in meals.columns:
        out[schema.MEAL_AMOUNT] = meals[schema.MEAL_AMOUNT]
    elif "amount_consumed" in meals.columns:
        out[schema.MEAL_AMOUNT] = meals["amount_consumed"]
    else:
        out[schema.MEAL_AMOUNT] = pd.NA

    out[schema.MEAL_HAS_COMPLETE_MACROS] = out[list(schema.MACRO_COLUMNS)].notna().all(axis=1)
    return out.reset_index(drop=True)


def _iso(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()


def _nullable_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _safe_ratio(numerator: int, denominator: int) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0