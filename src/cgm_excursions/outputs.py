"""Writing a preprocessing run to disk, and the manifest that identifies it.

A run is reproducible when its manifest matches: the manifest records the dataset
identity, the effective configuration and its hash, the pipeline version, the exact
software versions, and a SHA-256 of every file written. Nothing in this module decides
anything about the data; it records what the pipeline decided.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from . import __version__, schema
from .config import config_hash
from .dataset import DatasetSource, open_participant

CGM_FILENAME = "cgm.parquet"
MEALS_FILENAME = "meals.parquet"
PARTICIPANTS_FILENAME = "participants.parquet"
QC_SUMMARY_FILENAME = "qc_summary.json"
MANIFEST_FILENAME = "manifest.json"

# Written by the manifest; excluded from the file digest list because a file cannot
# contain its own hash.
_DIGEST_EXCLUDED = {MANIFEST_FILENAME}


@dataclass(frozen=True)
class RunOutputs:
    """Where a run's artifacts live, and what identifies it."""

    run_id: str
    directory: Path

    @property
    def cgm_path(self) -> Path:
        return self.directory / CGM_FILENAME

    @property
    def meals_path(self) -> Path:
        return self.directory / MEALS_FILENAME

    @property
    def participants_path(self) -> Path:
        return self.directory / PARTICIPANTS_FILENAME

    @property
    def qc_summary_path(self) -> Path:
        return self.directory / QC_SUMMARY_FILENAME

    @property
    def manifest_path(self) -> Path:
        return self.directory / MANIFEST_FILENAME

    def paths(self) -> dict[str, Path]:
        return {
            "cgm": self.cgm_path,
            "meals": self.meals_path,
            "participants": self.participants_path,
            "qc_summary": self.qc_summary_path,
        }


def dataset_fingerprint(source: DatasetSource, *, full: bool = True) -> str:
    """A digest of the participant files actually read.

    Hashing every participant costs a full read of the dataset, so it is the honest
    choice rather than a shortcut: a silently altered input then changes the run id
    instead of quietly producing different outputs under the same name. Pass
    ``full=False`` for a cheap structural fingerprint when only a cache key is needed.
    """
    digest = hashlib.sha256()
    for participant in source.participants:
        digest.update(participant.subject_id.encode("utf-8"))
        if full:
            with open_participant(participant) as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
        else:
            digest.update(str(participant.csv_path).encode("utf-8"))
            digest.update(str(participant.archive_member).encode("utf-8"))
    return digest.hexdigest()


def run_id_for(config: dict[str, Any], fingerprint: str) -> str:
    """A run id that changes when either the data or any threshold changes."""
    combined = hashlib.sha256(
        f"{config_hash(config)}:{fingerprint}".encode("utf-8")
    ).hexdigest()
    return f"run-{combined[:16]}"


def package_versions() -> dict[str, str]:
    """Software versions recorded so a run can be reproduced or ruled out."""
    versions = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cgm_excursions": __version__,
    }
    for module_name in ("pandas", "numpy", "pyarrow"):
        try:
            module = __import__(module_name)
            versions[module_name] = getattr(module, "__version__", "unknown")
        except ImportError:  # pragma: no cover - a partial environment
            versions[module_name] = "not installed"
    return versions


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_run(
    outputs: RunOutputs,
    *,
    cgm: pd.DataFrame,
    meals: pd.DataFrame,
    participants: pd.DataFrame,
    qc_summary: dict[str, list[dict[str, Any]]],
    config: dict[str, Any],
    source: DatasetSource,
    dataset_fingerprint_value: str,
    stage_timings: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Write every artifact for a run and return the manifest.

    Outputs are written unconditionally, including a participant whose every row carries
    a flag. Preprocessing never removes data; a consumer filters on ``qc_eligible``.
    """
    outputs.directory.mkdir(parents=True, exist_ok=True)

    cgm.to_parquet(outputs.cgm_path, index=False)
    meals.to_parquet(outputs.meals_path, index=False)
    participants.to_parquet(outputs.participants_path, index=False)

    manifest = build_manifest(
        outputs=outputs,
        cgm=cgm,
        meals=meals,
        participants=participants,
        config=config,
        source=source,
        dataset_fingerprint_value=dataset_fingerprint_value,
        stage_timings=stage_timings or {},
    )

    summary_payload = {
        "manifest": {key: value for key, value in manifest.items() if key != "files"},
        "participants": qc_summary.get("participants", []),
        "days": qc_summary.get("days", []),
        "segments": qc_summary.get("segments", []),
    }
    _write_json(outputs.qc_summary_path, summary_payload)

    # The file digests include qc_summary.json, so the manifest is written last and its
    # own digest is deliberately absent.
    manifest["files"] = {
        name: {"bytes": path.stat().st_size, "sha256": file_sha256(path)}
        for name, path in sorted(outputs.paths().items())
        if path.name not in _DIGEST_EXCLUDED
    }
    _write_json(outputs.manifest_path, manifest)
    return manifest


def build_manifest(
    *,
    outputs: RunOutputs,
    cgm: pd.DataFrame,
    meals: pd.DataFrame,
    participants: pd.DataFrame,
    config: dict[str, Any],
    source: DatasetSource,
    dataset_fingerprint_value: str,
    stage_timings: dict[str, float],
) -> dict[str, Any]:
    """The run manifest: what was read, how it was configured, and what was produced."""
    return {
        "run_id": outputs.run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_version": __version__,
        "dataset": {
            "root": str(source.root),
            "kind": source.kind,
            "fingerprint_sha256": dataset_fingerprint_value,
            "participant_count": len(source.participants),
            "subject_ids": list(source.subject_ids),
            "bio_available": source.bio_path is not None,
        },
        "config": {
            "sha256": config_hash(config),
            "effective": config,
        },
        "counts": {
            "cgm_rows": int(len(cgm)),
            "meal_rows": int(len(meals)),
            "participant_rows": int(len(participants)),
            "eligible_rows": int(cgm[schema.QC_ELIGIBLE].sum()),
        },
        "cohort": {
            "rows_per_subject": {
                str(subject): int(count)
                for subject, count in cgm[schema.SUBJECT_ID].value_counts().sort_index().items()
            },
        },
        "software": package_versions(),
        "stage_seconds": {name: round(value, 3) for name, value in stage_timings.items()},
        "conventions": {
            "time_axis": "elapsed_minutes",
            "timestamp_shifted": (
                "Upstream shifted every participant's dates by a private offset of 365-720 "
                "days. The value is an ordering key and is never presented as a real date."
            ),
            "interpolation": "none; the canonical outputs never interpolate or fill",
            "smoothing": "none; a detector owns any smoothing it requires",
            "sensor_handling": (
                f"{config['streams']['primary']} is primary, "
                f"{config['streams']['replication']} replicates. The streams are never "
                "averaged and never filled from one another."
            ),
            "freshness_rule": (
                "A value is fresh when it differs from that stream's previous non-null "
                "value; the first reading in a stream is always fresh. A genuine "
                "re-reading of an identical value is therefore marked held, which is a "
                "known and stated limitation of reconstructing observation times from a "
                "carried-forward snapshot."
            ),
            "eligibility": (
                "qc_eligible = primary value present AND no hard flag. Screening flags "
                "(range, rate of change, flatline, spike) never clear eligibility."
            ),
            "timestamps": "stored timezone-naive; the upstream clock carries no zone",
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """JSON with a stable key order and predictable formatting, so diffs stay readable."""
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=False, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _json_default(value: Any):
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, (set, tuple)):
        return list(value)
    if isinstance(value, float) and pd.isna(value):
        return None
    raise TypeError(f"cannot serialize {type(value).__name__} to JSON")


def latest_run(directory: Path) -> RunOutputs | None:
    """The most recently written run in a processed-data directory."""
    if not directory.is_dir():
        return None
    candidates = [
        child for child in directory.iterdir()
        if child.is_dir() and (child / MANIFEST_FILENAME).exists()
    ]
    if not candidates:
        return None
    newest = max(candidates, key=lambda child: (child / MANIFEST_FILENAME).stat().st_mtime)
    return RunOutputs(run_id=newest.name, directory=newest)


def load_manifest(outputs: RunOutputs) -> dict[str, Any]:
    return json.loads(outputs.manifest_path.read_text(encoding="utf-8"))


def load_qc_summary(outputs: RunOutputs) -> dict[str, Any]:
    return json.loads(outputs.qc_summary_path.read_text(encoding="utf-8"))


def load_tables(outputs: RunOutputs) -> dict[str, pd.DataFrame]:
    """Read the run's tables back. Used by the API and by tests."""
    return {
        "cgm": pd.read_parquet(outputs.cgm_path),
        "meals": pd.read_parquet(outputs.meals_path),
        "participants": pd.read_parquet(outputs.participants_path),
    }


def summarize_for_stdout(manifest: dict[str, Any]) -> str:
    """A short, human-readable run summary for the command line."""
    counts = manifest["counts"]
    lines = [
        f"run        {manifest['run_id']}",
        f"dataset    {manifest['dataset']['participant_count']} participants "
        f"({manifest['dataset']['kind']})",
        f"rows       {counts['cgm_rows']:,} cgm | {counts['meal_rows']:,} meals | "
        f"{counts['participant_rows']:,} participants",
        f"eligible   {counts['eligible_rows']:,} rows "
        f"({_percentage(counts['eligible_rows'], counts['cgm_rows'])})",
    ]
    files = manifest.get("files") or {}
    if files:
        total = sum(entry["bytes"] for entry in files.values())
        lines.append(f"wrote      {len(files)} files, {_human_bytes(total)}")
    return "\n".join(lines)


def _percentage(numerator: int, denominator: int) -> str:
    if not denominator:
        return "n/a"
    return f"{100.0 * numerator / denominator:.1f}%"


def _human_bytes(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} GB"
