"""Finding the dataset on disk and enumerating its participants.

The dataset is never vendored into the repository: it is large, its licence is upstream's,
and the code should work against whatever copy a user already has. This module accepts
either the downloaded ZIP or an extracted directory, and reports what it found clearly
enough that a wrong path is diagnosed rather than silently producing an empty run.
"""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path

PARTICIPANT_DIR_PREFIX = "CGMacros-"
BIO_FILENAME = "bio.csv"
ARCHIVE_SHA_FILENAME = "SHA256SUMS.txt"


class DatasetNotFoundError(FileNotFoundError):
    """No usable CGMacros dataset at the given location."""


@dataclass(frozen=True)
class ParticipantSource:
    """One participant's time-series file, and the metadata table for the cohort."""

    subject_id: str
    csv_path: Path
    archive_member: str | None = None


@dataclass(frozen=True)
class DatasetSource:
    """A resolved dataset: where it came from, and what it contains."""

    root: Path
    kind: str  # "directory" or "archive"
    participants: tuple[ParticipantSource, ...]
    bio_path: Path | None
    archive_path: Path | None = None

    @property
    def subject_ids(self) -> tuple[str, ...]:
        return tuple(p.subject_id for p in self.participants)

    def __len__(self) -> int:
        return len(self.participants)

    def describe(self) -> str:
        return (
            f"{len(self.participants)} participants from a {self.kind} at {self.root}"
        )


def _subject_id_from_dirname(name: str) -> str | None:
    if not name.startswith(PARTICIPANT_DIR_PREFIX):
        return None
    suffix = name[len(PARTICIPANT_DIR_PREFIX):]
    return suffix or None


def _participant_dirs(location: Path) -> list[Path]:
    """Participant folders, searching one level deeper for the nested layout.

    A hand-extracted archive may unpack to ``CGMacros/CGMacros-001/...`` rather than
    straight into ``CGMacros-001/...``, so both depths are accepted.
    """
    direct = sorted(
        d for d in location.iterdir()
        if d.is_dir() and _subject_id_from_dirname(d.name)
    )
    if direct:
        return direct
    nested: list[Path] = []
    for child in sorted(location.iterdir()):
        if not child.is_dir():
            continue
        nested.extend(
            d for d in sorted(child.iterdir())
            if d.is_dir() and _subject_id_from_dirname(d.name)
        )
    return nested


def _locate_bio(location: Path) -> Path | None:
    candidate = location / BIO_FILENAME
    if candidate.exists():
        return candidate
    for child in sorted(location.iterdir()):
        if child.is_dir() and (child / BIO_FILENAME).exists():
            return child / BIO_FILENAME
    return None


def resolve_dataset(path: Path) -> DatasetSource:
    """Resolve a ZIP archive or an extracted directory into participant sources."""
    candidate = Path(path).expanduser()
    if not candidate.exists():
        raise DatasetNotFoundError(
            f"no dataset at {candidate}. Download CGMacros from "
            "https://physionet.org/content/cgmacros/1.0.0/ and pass either the ZIP or "
            "the extracted folder."
        )

    if candidate.is_file():
        return _resolve_archive(candidate)
    if candidate.is_dir():
        return _resolve_directory(candidate)
    raise DatasetNotFoundError(f"{candidate} is neither a file nor a directory")


def _resolve_directory(location: Path) -> DatasetSource:
    participants: list[ParticipantSource] = []
    for folder in _participant_dirs(location):
        subject_id = _subject_id_from_dirname(folder.name)
        if subject_id is None:
            continue
        csv_path = folder / f"{folder.name}.csv"
        if not csv_path.exists():
            # Some exports keep the CSV under a differently named file in the folder.
            candidates = sorted(folder.glob("*.csv"))
            if not candidates:
                continue
            csv_path = candidates[0]
        participants.append(ParticipantSource(subject_id=subject_id, csv_path=csv_path))

    if not participants:
        raise DatasetNotFoundError(
            f"no participant folders named '{PARTICIPANT_DIR_PREFIX}*' under {location}. "
            "Point at the folder that directly contains them, such as "
            ".../CGMacros/1.0.0/extracted/CGMacros"
        )
    return DatasetSource(
        root=location,
        kind="directory",
        participants=tuple(participants),
        bio_path=_locate_bio(location),
    )


def _resolve_archive(archive: Path) -> DatasetSource:
    """Read participants straight out of the ZIP.

    The archive also holds thousands of meal photographs that the pipeline never reads,
    so nothing is extracted to disk: member paths are resolved inside the archive and
    read on demand.
    """
    try:
        with zipfile.ZipFile(archive) as handle:
            names = handle.namelist()
    except zipfile.BadZipFile as error:
        raise DatasetNotFoundError(f"{archive} is not a readable ZIP archive") from error

    participants: list[ParticipantSource] = []
    bio_member: str | None = None
    for name in sorted(names):
        parts = name.split("/")
        # bio.csv is recognised at any depth, including the archive root, before the
        # participant check: a top-level member has no folder part to inspect.
        if parts[-1] == BIO_FILENAME:
            bio_member = name
            continue
        if len(parts) < 2:
            continue
        folder = parts[-2]
        subject_id = _subject_id_from_dirname(folder)
        if subject_id and name.lower().endswith(".csv") and name.lower().endswith(
            f"{folder.lower()}.csv"
        ):
            participants.append(ParticipantSource(
                subject_id=subject_id,
                csv_path=archive,
                archive_member=name,
            ))

    if not participants:
        raise DatasetNotFoundError(
            f"{archive} contains no participant CSVs. Expected folders named "
            f"'{PARTICIPANT_DIR_PREFIX}*/' each holding a matching CSV."
        )
    return DatasetSource(
        root=archive,
        kind="archive",
        participants=tuple(participants),
        bio_path=archive if bio_member else None,
        archive_path=archive,
    )


def read_bio_member(source: DatasetSource) -> bytes | None:
    """The raw bytes of ``bio.csv``, from disk or from inside the archive."""
    if source.kind == "archive":
        if source.archive_path is None:
            return None
        with zipfile.ZipFile(source.archive_path) as handle:
            for name in handle.namelist():
                if name.endswith(f"/{BIO_FILENAME}") or name == BIO_FILENAME:
                    return handle.read(name)
        return None
    if source.bio_path is None:
        return None
    return source.bio_path.read_bytes()


def open_participant(participant: ParticipantSource):
    """A readable binary handle for one participant CSV, from disk or from the archive."""
    if participant.archive_member is None:
        return open(participant.csv_path, "rb")
    return zipfile.ZipFile(participant.csv_path).open(participant.archive_member)


def sha256_of(path: Path) -> str:
    """Streaming SHA-256, used to identify the dataset in the run manifest."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
