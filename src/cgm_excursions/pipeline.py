"""Running the whole pipeline over a dataset, and reporting what happened.

This is the only module that knows about both the dataset on disk and the artifacts on
disk. Every stage it calls is independently tested; the job here is to sequence them,
time them, and hand the results to the writer.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from . import preprocessing, schema
from .config import load_config
from .dataset import DatasetSource, ParticipantSource, open_participant, resolve_dataset
from .outputs import (
    RunOutputs,
    dataset_fingerprint,
    run_id_for,
    write_run,
)
from .reading import read_bio, read_participant, read_participant_bytes


@dataclass
class RunResult:
    """What a completed run produced, plus the manifest that identifies it."""

    outputs: RunOutputs
    manifest: dict[str, Any]

    @property
    def counts(self) -> dict[str, int]:
        return self.manifest["counts"]


def read_participant_frame(participant: ParticipantSource) -> pd.DataFrame:
    """Read one participant's frame, from a directory on disk or from inside an archive."""
    if participant.archive_member is None:
        frame, _columns = read_participant(participant.csv_path)
        return frame

    with open_participant(participant) as handle:
        data = handle.read()
    frame, _columns = read_participant_bytes(data, source_name=participant.archive_member)
    return frame


def preprocess_dataset(
    dataset_path: Path,
    *,
    config_path: Path | None = None,
    config: dict[str, Any] | None = None,
    output_root: Path | None = None,
    fingerprint_full: bool = True,
    on_progress=None,
) -> RunResult:
    """Preprocess every participant in a dataset and write the run artifacts.

    ``on_progress`` is called once per participant with ``(index, total, subject_id)`` so
    a caller can report progress without this module knowing how output is displayed.
    """
    resolved_config = config if config is not None else load_config(config_path)

    started = time.perf_counter()
    source = resolve_dataset(dataset_path)
    resolve_seconds = time.perf_counter() - started

    stage_seconds: dict[str, float] = {"resolve_dataset": resolve_seconds}

    started = time.perf_counter()
    fingerprint = dataset_fingerprint(source, full=fingerprint_full)
    stage_seconds["fingerprint"] = time.perf_counter() - started

    run_id = run_id_for(resolved_config, fingerprint)
    directory = (output_root or Path("data/processed")) / run_id
    outputs = RunOutputs(run_id=run_id, directory=directory)

    frames: dict[str, pd.DataFrame] = {}
    meals: list[pd.DataFrame] = []
    gaps_by_subject: dict[str, list[dict[str, Any]]] = {}

    started = time.perf_counter()
    total = len(source.participants)
    for index, participant in enumerate(source.participants, start=1):
        if on_progress is not None:
            on_progress(index, total, participant.subject_id)

        raw = read_participant_frame(participant)
        processed = preprocessing.preprocess_from_frame(
            raw, subject_id=participant.subject_id, config=resolved_config
        )
        frames[participant.subject_id] = processed
        gaps_by_subject[participant.subject_id] = preprocessing.detect_gaps(
            processed, resolved_config
        )
        participant_meals = preprocessing.extract_meals(processed)
        if not participant_meals.empty:
            meals.append(participant_meals)
    stage_seconds["participants"] = time.perf_counter() - started

    started = time.perf_counter()
    cgm = pd.concat(frames.values(), ignore_index=True) if frames else pd.DataFrame(
        columns=schema.canonical_cgm_columns()
    )
    meal_table = (
        pd.concat(meals, ignore_index=True)
        if meals
        else preprocessing.extract_meals(cgm)
    )
    participant_table = build_participant_table(source, frames)
    stage_seconds["assemble"] = time.perf_counter() - started

    started = time.perf_counter()
    qc_summary = preprocessing.roll_up_coverage(frames, gaps_by_subject)
    stage_seconds["rollup"] = time.perf_counter() - started

    started = time.perf_counter()
    manifest = write_run(
        outputs,
        cgm=cgm,
        meals=meal_table,
        participants=participant_table,
        qc_summary=qc_summary,
        config=resolved_config,
        source=source,
        dataset_fingerprint_value=fingerprint,
        stage_timings=stage_seconds,
    )
    stage_seconds["write"] = time.perf_counter() - started

    return RunResult(outputs=outputs, manifest=manifest)


def build_participant_table(
    source: DatasetSource,
    frames: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Join ``bio.csv`` to the CGM cohort, with derived per-participant CGM facts.

    The join is explicit and left-anchored on the participants that actually have CGM
    data, so a metadata row without a CGM folder (``gut_health_test.csv`` carries two)
    cannot enter the analysis cohort silently.
    """
    rows: list[dict[str, Any]] = []

    bio = _load_bio(source)
    by_subject = (
        bio.set_index("subject").to_dict(orient="index") if not bio.empty else {}
    )

    for subject_id in sorted(frames):
        cgm = frames[subject_id]
        numeric_subject = _to_int(subject_id)
        metadata = by_subject.get(numeric_subject, {})

        a1c = metadata.get("a1c_percent")
        record: dict[str, Any] = {
            schema.SUBJECT_ID: subject_id,
            "age": metadata.get("age"),
            "gender": metadata.get("gender"),
            "bmi": metadata.get("bmi"),
            "body_weight_kg": metadata.get("body_weight_kg"),
            "height_cm": metadata.get("height_cm"),
            "self_identified_ethnicity": metadata.get("self_identified_ethnicity"),
            "a1c_percent": a1c,
            "a1c_band": schema.a1c_band(a1c if pd.notna(a1c) else None),
            "fasting_glucose_mgdl": metadata.get("fasting_glucose_mgdl"),
            "insulin": metadata.get("insulin"),
            "triglycerides": metadata.get("triglycerides"),
            "cholesterol": metadata.get("cholesterol"),
            "hdl": metadata.get("hdl"),
            "non_hdl": metadata.get("non_hdl"),
            "ldl_cal": metadata.get("ldl_cal"),
            "vldl_cal": metadata.get("vldl_cal"),
            "cho_hdl_ratio": metadata.get("cho_hdl_ratio"),
            "collection_time": metadata.get("collection_time"),
            "has_cgm_data": True,
            "cgm_row_count": int(len(cgm)),
            "cgm_first_ts": cgm[schema.TIMESTAMP].iloc[0] if len(cgm) else pd.NaT,
            "cgm_last_ts": cgm[schema.TIMESTAMP].iloc[-1] if len(cgm) else pd.NaT,
        }
        rows.append(record)

    # Metadata rows with no CGM data are carried explicitly, flagged, and never dropped.
    for numeric_subject, metadata in sorted(by_subject.items()):
        subject_id = f"{numeric_subject:03d}"
        if subject_id in frames:
            continue
        a1c = metadata.get("a1c_percent")
        rows.append({
            schema.SUBJECT_ID: subject_id,
            "age": metadata.get("age"),
            "gender": metadata.get("gender"),
            "bmi": metadata.get("bmi"),
            "body_weight_kg": metadata.get("body_weight_kg"),
            "height_cm": metadata.get("height_cm"),
            "self_identified_ethnicity": metadata.get("self_identified_ethnicity"),
            "a1c_percent": a1c,
            "a1c_band": schema.a1c_band(a1c if pd.notna(a1c) else None),
            "fasting_glucose_mgdl": metadata.get("fasting_glucose_mgdl"),
            "insulin": metadata.get("insulin"),
            "triglycerides": metadata.get("triglycerides"),
            "cholesterol": metadata.get("cholesterol"),
            "hdl": metadata.get("hdl"),
            "non_hdl": metadata.get("non_hdl"),
            "ldl_cal": metadata.get("ldl_cal"),
            "vldl_cal": metadata.get("vldl_cal"),
            "cho_hdl_ratio": metadata.get("cho_hdl_ratio"),
            "collection_time": metadata.get("collection_time"),
            "has_cgm_data": False,
            "cgm_row_count": 0,
            "cgm_first_ts": pd.NaT,
            "cgm_last_ts": pd.NaT,
        })

    table = pd.DataFrame(rows)
    # list(), not the bare tuple: pandas reads a tuple index as a single column key.
    return (
        table[list(schema.PARTICIPANT_COLUMNS)]
        .sort_values(schema.SUBJECT_ID)
        .reset_index(drop=True)
    )


def _load_bio(source: DatasetSource) -> pd.DataFrame:
    from .dataset import read_bio_member
    import io

    payload = read_bio_member(source)
    if payload is None:
        return pd.DataFrame()
    return read_bio(io.BytesIO(payload))


def _to_int(subject_id: str) -> int:
    try:
        return int(subject_id)
    except ValueError:
        return -1
