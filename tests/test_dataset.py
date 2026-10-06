"""Resolving the CGMacros dataset, from an extracted tree or from the ZIP.

The published archive is large and, on top of the participant files, holds thousands of
meal photographs. So the resolver has to enumerate participants *without* extracting
anything to disk, tolerate both the flat layout (``.../CGMacros/CGMacros-001/``) and the
hand-extracted nested one (``.../CGMacros/CGMacros-001/`` under a wrapper), and read a
participant straight out of the archive.

Every layout below is built under ``tmp_path``. Nothing in this module writes to, or
depends on, the real dataset.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from cgm_excursions.dataset import (
    BIO_FILENAME,
    PARTICIPANT_DIR_PREFIX,
    DatasetNotFoundError,
    open_participant,
    read_bio_member,
    resolve_dataset,
)

PARTICIPANT_CSV = (
    "Timestamp,Dexcom GL,Libre GL\n"
    "2020-05-01 11:39:00,141.0,94.4\n"
    "2020-05-01 11:40:00,141.0,94.4\n"
)
BIO_BYTES = b"subject,A1c PDL (Lab)\n1,5.1\n4,5.4\n"

REAL_ZIP = Path(
    "/Users/billchen/Desktop/JupyterHealth/Datasets/CGMacros/1.0.0/source/"
    "CGMacros_dateshifted365.zip"
)
REAL_DIR = Path(
    "/Users/billchen/Desktop/JupyterHealth/Datasets/CGMacros/1.0.0/extracted/CGMacros"
)


# --------------------------------------------------------------------------- helpers
def _write_participant(root: Path, number: str, text: str = PARTICIPANT_CSV) -> Path:
    """Create ``root/CGMacros-<number>/CGMacros-<number>.csv`` and return the folder."""
    folder = root / f"{PARTICIPANT_DIR_PREFIX}{number}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{PARTICIPANT_DIR_PREFIX}{number}.csv").write_text(text, encoding="utf-8")
    return folder


def _write_bio(root: Path, subjects) -> Path:
    path = root / BIO_FILENAME
    body = "\n".join(f"{subject},5.{subject}" for subject in subjects)
    path.write_text(f"subject,A1c PDL (Lab)\n{body}\n", encoding="utf-8")
    return path


def _make_archive(path: Path, members: dict[str, object]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as handle:
        for name, payload in members.items():
            if isinstance(payload, str):
                payload = payload.encode("utf-8")
            handle.writestr(name, payload)
    return path


# ------------------------------------------------------------------ 1. flat directory
def test_directory_source_reports_sorted_subject_ids_and_finds_bio(tmp_path):
    root = tmp_path / "CGMacros"
    root.mkdir()
    # Deliberately created out of order: the resolver, not the filesystem, must sort.
    for number in ("007", "001", "004"):
        _write_participant(root, number)
    bio = _write_bio(root, [1, 4, 7])

    source = resolve_dataset(root)

    assert source.kind == "directory"
    assert source.subject_ids == ("001", "004", "007")
    assert list(source.subject_ids) == sorted(source.subject_ids)
    assert len(source) == 3
    assert source.bio_path == bio
    assert source.bio_path is not None and source.bio_path.exists()
    assert source.describe()  # never empty, and naming the source is cheap


# ----------------------------------------------------------------- 2. nested directory
def test_nested_directory_layout_is_tolerated(tmp_path):
    """A hand-extracted archive may unpack to ``extracted/CGMacros/CGMacros-001/...``."""
    extracted = tmp_path / "extracted"
    wrapper = extracted / "CGMacros"  # not itself a participant folder
    wrapper.mkdir(parents=True)
    for number in ("002", "001"):
        _write_participant(wrapper, number)
    bio = _write_bio(wrapper, [1, 2])

    source = resolve_dataset(extracted)

    assert source.kind == "directory"
    assert source.subject_ids == ("001", "002")
    assert source.bio_path == bio


# ----------------------------------------------------------------------- 3. ZIP archive
def test_archive_source_reads_participants_without_extraction(tmp_path):
    archive = _make_archive(
        tmp_path / "cgmacros.zip",
        {
            "CGMacros-001/CGMacros-001.csv": PARTICIPANT_CSV,
            "CGMacros-004/CGMacros-004.csv": PARTICIPANT_CSV,
            "bio.csv": BIO_BYTES,
            "CGMacros-001/photos/0001-PHOTO.jpg": b"\xff\xd8\xff\xe0meal",
            "CGMacros-004/photos/0002-PHOTO.jpg": b"\xff\xd8\xff\xe0meal",
        },
    )

    source = resolve_dataset(archive)

    assert source.kind == "archive"
    assert source.subject_ids == ("001", "004")
    assert len(source) == 2
    # The meal photos must not be mistaken for participants.
    assert all(p.subject_id != "photos" for p in source.participants)

    participant = source.participants[0]
    assert participant.archive_member == "CGMacros-001/CGMacros-001.csv"
    with open_participant(participant) as handle:
        assert handle.read().decode("utf-8") == PARTICIPANT_CSV


# ------------------------------------------------- 4. ZIP with no participant CSVs
def test_archive_without_participant_csvs_raises_helpfully(tmp_path):
    archive = _make_archive(
        tmp_path / "empty.zip",
        {
            "readme.txt": "not the dataset",
            "bio.csv": BIO_BYTES,
            "photos/0001-PHOTO.jpg": b"\xff\xd8\xff\xe0",
        },
    )

    with pytest.raises(DatasetNotFoundError) as excinfo:
        resolve_dataset(archive)

    message = str(excinfo.value)
    assert str(archive) in message
    assert "participant" in message.lower()


# --------------------------------------------------------------- 5. nonexistent path
def test_missing_path_raises_dataset_not_found(tmp_path):
    missing = tmp_path / "does-not-exist"

    with pytest.raises(DatasetNotFoundError) as excinfo:
        resolve_dataset(missing)

    assert str(missing) in str(excinfo.value)
    assert not missing.exists()


# -------------------------------------------------- 6. archive never extracted to disk
def test_archive_resolution_extracts_nothing_to_disk(tmp_path):
    archive = _make_archive(
        tmp_path / "cgmacros.zip",
        {
            "CGMacros-001/CGMacros-001.csv": PARTICIPANT_CSV,
            "CGMacros-001/photos/0001-PHOTO.jpg": b"\xff\xd8\xff\xe0",
            "bio.csv": BIO_BYTES,
        },
    )
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    resolve_dataset(archive)

    after = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
    assert after == before, f"resolution wrote files: {sorted(after - before)}"


# ------------------------------------------ 7. CSV chosen by matching the folder name
def test_archive_csv_is_matched_by_folder_name_not_any_csv(tmp_path):
    archive = _make_archive(
        tmp_path / "cgmacros.zip",
        {
            "CGMacros-001/CGMacros-001.csv": PARTICIPANT_CSV,
            "CGMacros-001/notes.csv": "note\nthis is not the participant data\n",
        },
    )

    source = resolve_dataset(archive)

    assert source.subject_ids == ("001",)
    assert len(source.participants) == 1
    assert source.participants[0].archive_member == "CGMacros-001/CGMacros-001.csv"


# ------------------------------------------------------------- 8. read_bio_member()
def test_read_bio_member_returns_bytes_for_directory_and_archive(tmp_path):
    # Directory source.
    root = tmp_path / "CGMacros"
    root.mkdir()
    _write_participant(root, "001")
    bio = _write_bio(root, [1])
    directory_source = resolve_dataset(root)
    assert read_bio_member(directory_source) == bio.read_bytes()

    # Archive source with the real, nested layout (CGMacros/bio.csv).
    nested = _make_archive(
        tmp_path / "nested.zip",
        {
            "CGMacros/CGMacros-001/CGMacros-001.csv": PARTICIPANT_CSV,
            "CGMacros/bio.csv": BIO_BYTES,
        },
    )
    nested_source = resolve_dataset(nested)
    assert nested_source.subject_ids == ("001",)
    assert read_bio_member(nested_source) == BIO_BYTES

    # Archive source with bio.csv at the archive root.
    root_level = _make_archive(
        tmp_path / "root.zip",
        {
            "CGMacros-001/CGMacros-001.csv": PARTICIPANT_CSV,
            "bio.csv": BIO_BYTES,
        },
    )
    root_source = resolve_dataset(root_level)
    assert read_bio_member(root_source) == BIO_BYTES


def test_archive_reports_bio_available_wherever_bio_csv_lives(tmp_path):
    """``DatasetSource.bio_path`` is how the run manifest reports ``bio_available``."""
    nested = resolve_dataset(
        _make_archive(
            tmp_path / "nested.zip",
            {
                "CGMacros/CGMacros-001/CGMacros-001.csv": PARTICIPANT_CSV,
                "CGMacros/bio.csv": BIO_BYTES,
            },
        )
    )
    assert nested.bio_path is not None

    root_level = resolve_dataset(
        _make_archive(
            tmp_path / "root.zip",
            {
                "CGMacros-001/CGMacros-001.csv": PARTICIPANT_CSV,
                "bio.csv": BIO_BYTES,
            },
        )
    )
    assert read_bio_member(root_level) == BIO_BYTES
    assert root_level.bio_path is not None


# --------------------------------------------------- real dataset, read-only integration
@pytest.mark.skipif(not REAL_ZIP.exists(), reason="real CGMacros archive not present")
def test_real_archive_resolves_45_participants_read_only():
    source = resolve_dataset(REAL_ZIP)

    assert source.kind == "archive"
    assert len(source) == 45
    assert list(source.subject_ids) == sorted(source.subject_ids)
    assert source.bio_path is not None
    with open_participant(source.participants[0]) as handle:
        head = handle.read(128).decode("utf-8", "replace")
    assert "timestamp" in head.lower()


@pytest.mark.skipif(not REAL_DIR.exists(), reason="real extracted tree not present")
def test_real_extracted_directory_resolves_45_participants_read_only():
    source = resolve_dataset(REAL_DIR)

    assert source.kind == "directory"
    assert len(source) == 45
    assert list(source.subject_ids) == sorted(source.subject_ids)
    assert source.bio_path is not None and source.bio_path.name == BIO_FILENAME
