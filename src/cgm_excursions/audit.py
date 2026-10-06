"""Auditing a dataset before analysing it.

The point of this module is to answer "what is actually in these files?" from the data
itself, rather than from documentation. It reads only; it writes nothing and changes
nothing. Run it before trusting any assumption baked into analysis code — the two
streams in CGMacros turned out to be carried-forward snapshots rather than the clean
5- and 15-minute streams the documentation implies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .dataset import DatasetSource, open_participant, resolve_dataset
from .reading import read_participant, read_participant_bytes


def audit_participant_csv(data: bytes, source_name: str) -> dict[str, Any]:
    """One participant's shape facts, derived from the file rather than assumed."""
    frame, columns = read_participant_bytes(data, source_name=source_name)
    timestamps = frame["timestamp"]

    deltas = timestamps.diff().dt.total_seconds().dropna()
    positive = deltas[deltas > 0]
    # The base cadence is the smallest observed interval. Any interval ABOVE it means the
    # file skips minutes, and that tail must be reported explicitly: a median-only summary
    # hides it completely, because every participant's median here is 60.0 s. Reporting
    # the median alone reads as "uniform 60 s cadence" even though 1,155 intervals across
    # 10 participants exceed it, including a 15-hour hole in participant 018.
    base = float(positive.min()) if len(positive) else None
    record: dict[str, Any] = {
        "source": source_name,
        "rows": int(len(frame)),
        "base_interval_seconds": base,
        "median_interval_seconds": float(positive.median()) if len(positive) else None,
        "min_interval_seconds": base,
        "max_interval_seconds": float(positive.max()) if len(positive) else None,
        "intervals_above_base": int((positive > base).sum()) if base is not None else 0,
        "duplicate_timestamps": int(timestamps.duplicated().sum()),
        "is_time_ordered": bool(timestamps.is_monotonic_increasing),
        "first_timestamp": _iso(timestamps.iloc[0]) if len(frame) else None,
        "last_timestamp": _iso(timestamps.iloc[-1]) if len(frame) else None,
        "headers": list(columns.raw_headers),
        "meal_rows": int(frame["meal_type"].notna().sum()) if "meal_type" in frame else 0,
    }

    for stream_name in ("dexcom", "libre"):
        values = frame[stream_name]
        observed = values.dropna()
        if observed.empty:
            record[stream_name] = {"observed": 0}
            continue
        # A reading identical to the previous reading is a carried-forward value, not a
        # new measurement: that is how a snapshot file represents a slower sensor.
        successive = observed.diff()
        held = int((successive == 0).sum())
        record[stream_name] = {
            "observed": int(observed.size),
            "missing": int(values.isna().sum()),
            "distinct_values": int(observed.nunique()),
            "held_readings": held,
            "held_fraction": round(held / float(observed.size), 4),
            "min_mgdl": float(observed.min()),
            "max_mgdl": float(observed.max()),
        }

    both_missing = int((frame["dexcom"].isna() & frame["libre"].isna()).sum())
    record["rows_with_no_sensor_value"] = both_missing
    return record


def audit_dataset(
    dataset_path: Path | None = None,
    source: DatasetSource | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Audit every participant (or the first ``limit``) and summarize the cohort."""
    resolved = source or resolve_dataset(dataset_path)
    participants = resolved.participants[:limit] if limit else resolved.participants

    per_participant: list[dict[str, Any]] = []
    for participant in participants:
        if participant.archive_member is None:
            payload = participant.csv_path.read_bytes()
        else:
            with open_participant(participant) as handle:
                payload = handle.read()
        record = audit_participant_csv(payload, participant.archive_member or participant.csv_path.name)
        record["subject_id"] = participant.subject_id
        per_participant.append(record)

    return {
        "dataset": {
            "root": str(resolved.root),
            "kind": resolved.kind,
            "participant_count": len(resolved.participants),
            "audited_count": len(per_participant),
            "subject_ids": list(resolved.subject_ids),
            "bio_available": resolved.bio_path is not None,
        },
        "participants": per_participant,
        "cohort": _summarize_cohort(per_participant),
        "header_layouts": _header_layouts(per_participant),
    }


def _summarize_cohort(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {}

    frame = pd.DataFrame([
        {
            "subject_id": record["subject_id"],
            "rows": record["rows"],
            "base": record.get("base_interval_seconds"),
            "cadence": record["median_interval_seconds"],
            "longest": record.get("max_interval_seconds"),
            "skipped": record.get("intervals_above_base", 0),
            "duplicates": record["duplicate_timestamps"],
            "ordered": record["is_time_ordered"],
            "dexcom_held": record.get("dexcom", {}).get("held_fraction"),
            "libre_held": record.get("libre", {}).get("held_fraction"),
            "rows_with_no_sensor_value": record["rows_with_no_sensor_value"],
        }
        for record in records
    ])

    return {
        "total_rows": int(frame["rows"].sum()),
        # The base cadence is the smallest row-to-row interval seen anywhere. It is NOT a
        # claim that every interval equals it: ``intervals_above_base`` counts the skipped
        # minutes, and reporting the base alone is what previously produced the false
        # "uniform 60 s cadence" reading.
        "base_interval_seconds": float(frame["base"].min()) if frame["base"].notna().any() else None,
        "cadences_seconds": sorted(frame["cadence"].dropna().unique().tolist()),
        "longest_interval_seconds": float(frame["longest"].max()) if frame["longest"].notna().any() else None,
        "intervals_above_base": int(frame["skipped"].fillna(0).sum()),
        "participants_with_skipped_minutes": int((frame["skipped"].fillna(0) > 0).sum()),
        "participants_with_duplicate_timestamps": int((frame["duplicates"] > 0).sum()),
        "participants_out_of_time_order": int((~frame["ordered"].astype(bool)).sum()),
        "rows_with_no_sensor_value": int(frame["rows_with_no_sensor_value"].sum()),
        "dexcom_held_fraction": {
            "median": round(float(frame["dexcom_held"].median()), 4),
            "min": round(float(frame["dexcom_held"].min()), 4),
            "max": round(float(frame["dexcom_held"].max()), 4),
        },
        "libre_held_fraction": {
            "median": round(float(frame["libre_held"].median()), 4),
            "min": round(float(frame["libre_held"].min()), 4),
            "max": round(float(frame["libre_held"].max()), 4),
        },
    }


def _header_layouts(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group participants by their header signature, so a layout variant is visible.

    Sensor order is part of the signature: a file listing Dexcom before Libre must be
    distinguishable, because a positional parser would silently swap the two streams.
    """
    grouped: dict[tuple, list[str]] = {}
    for record in records:
        signature = tuple(record.get("headers") or [])
        grouped.setdefault(signature, []).append(record["subject_id"])

    layouts: list[dict[str, Any]] = []
    for signature, subject_ids in sorted(grouped.items(), key=lambda item: -len(item[1])):
        headers = list(signature)
        layouts.append({
            "participant_count": len(subject_ids),
            "subject_ids": subject_ids,
            "has_leading_index_column": bool(headers) and headers[0].strip().lower().startswith("unnamed"),
            "sensor_order": _sensor_order(headers),
            "activity_column": (
                "METs" if "METs" in headers else "Intensity" if "Intensity" in headers else None
            ),
            "has_steps": "Steps" in headers,
            "has_record_index": any(h.strip().lower() == "recordindex" for h in headers),
            "headers_with_surrounding_space": [
                h for h in headers if h != h.strip()
            ],
        })
    return layouts


def _sensor_order(headers: list[str]) -> str:
    normalised = [h.strip().lower() for h in headers]
    dexcom = next((i for i, h in enumerate(normalised) if h.startswith("dexcom")), None)
    libre = next((i for i, h in enumerate(normalised) if h.startswith("libre")), None)
    if dexcom is None or libre is None:
        return "unknown"
    return "dexcom_first" if dexcom < libre else "libre_first"


def _iso(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()
