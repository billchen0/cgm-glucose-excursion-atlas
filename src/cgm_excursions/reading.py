"""Resolving a raw CGMacros participant file into named columns, then into a frame.

The only interesting work here is surviving the dataset's real header variation. Column
*order* differs between participant files and one file lists the two sensors in the
opposite order, so every column is resolved by normalized name. A positional parser
would silently swap Dexcom and Libre for that participant and produce a plausible,
wrong analysis, so that rule is enforced and tested rather than assumed.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import schema

# Canonical field -> the raw header spellings that mean it. Spellings are compared after
# normalisation, so case and surrounding whitespace never matter.
HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "timestamp": ("timestamp", "time", "datetime", "date_time"),
    "dexcom": ("dexcom gl", "dexcom glucose", "dexcom_gl", "dexcom"),
    "libre": ("libre gl", "libre glucose", "libre_gl", "libre"),
    "hr": ("hr", "heart rate"),
    "calories_activity": ("calories (activity)", "calories activity", "activity calories"),
    "mets": ("mets", "intensity"),
    "steps": ("steps",),
    "record_index": ("recordindex", "record index"),
    "meal_type": ("meal type",),
    "calories": ("calories",),
    "carbs": ("carbs", "carbohydrates"),
    "protein": ("protein",),
    "fat": ("fat",),
    "fiber": ("fiber",),
    "amount_consumed": ("amount consumed",),
    "image_path": ("image path",),
}

# Fields a participant file must provide. Everything else is optional: a file without a
# meal column is readable, it simply contributes no meals.
REQUIRED_FIELDS: tuple[str, ...] = ("timestamp", "dexcom", "libre")

# Canonical meal fields, and the schema column each one becomes.
MEAL_COLUMNS: dict[str, str] = {
    "meal_type": schema.MEAL_TYPE,
    "calories": schema.MEAL_CALORIES,
    "carbs": schema.MEAL_CARBS,
    "protein": schema.MEAL_PROTEIN,
    "fat": schema.MEAL_FAT,
    "fiber": schema.MEAL_FIBER,
    "amount_consumed": schema.MEAL_AMOUNT,
}

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# Column prefixes that carry no analyte: an index pandas writes when a frame is saved.
_IGNORABLE_PREFIXES = ("unnamed:", "index")


class MissingColumnsError(ValueError):
    """A participant file does not provide a column the pipeline requires."""


def canonical_key(raw_header: str) -> str:
    """Fold a raw header to a comparable key: case, surrounding space, and separators."""
    lowered = raw_header.strip().lower()
    return " ".join(lowered.replace("_", " ").replace("(", " (").split())


def normalize_headers(raw_headers) -> dict[str, str]:
    """Map canonical field names to the raw header spelling actually present.

    Idempotent and case-insensitive. A field is absent (rather than mapped to None) when
    the file does not carry it, so callers can use ``"dexcom" in mapping``.
    """
    lookup: dict[str, str] = {}
    for raw in raw_headers:
        key = canonical_key(str(raw))
        if not key:
            continue
        # First spelling wins, so a file with two matching headers is deterministic.
        lookup.setdefault(key, str(raw))
    # Alias spellings collapse onto the canonical key.
    for fieldname, spellings in HEADER_ALIASES.items():
        for spelling in spellings:
            key = canonical_key(spelling)
            if key in lookup:
                lookup.setdefault(fieldname, lookup[key])
                break
    # An index-like column is not an analyte, so it never becomes a mapped field.
    return {
        name: value
        for name, value in lookup.items()
        if not value.strip().lower().startswith(_IGNORABLE_PREFIXES)
    }


@dataclass(frozen=True)
class ColumnMap:
    """The raw column names that supply each canonical field."""

    mapping: dict[str, str]
    raw_headers: tuple[str, ...] = field(default_factory=tuple)

    def of(self, canonical_field: str) -> str | None:
        """The raw column name for a canonical field, or None when absent."""
        return self.mapping.get(canonical_field)

    @property
    def timestamp(self) -> str:
        return self.require("timestamp")

    @property
    def dexcom(self) -> str:
        return self.require("dexcom")

    @property
    def libre(self) -> str:
        return self.require("libre")

    def require(self, canonical_field: str) -> str:
        value = self.mapping.get(canonical_field)
        if value is None:
            raise MissingColumnsError(
                f"participant file is missing the required '{canonical_field}' column; "
                f"available headers: {list(self.raw_headers)}"
            )
        return value

    def all_headers(self) -> list[str]:
        return list(self.raw_headers)

    def required_sources(self) -> list[str]:
        """Raw columns the pipeline reads. Excludes index-like columns by construction."""
        return [self.mapping[name] for name in REQUIRED_FIELDS if name in self.mapping]

    def meal_sources(self) -> dict[str, str]:
        """Canonical meal field -> raw column, for the meal fields the file provides."""
        return {name: self.mapping[name] for name in MEAL_COLUMNS if name in self.mapping}


def detect_delimiter(sample: str) -> str:
    """Comma everywhere in practice; sniffed so a stray semicolon file still reads."""
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except csv.Error:
        return ","


def resolve_columns(path: Path) -> ColumnMap:
    """Read only the header row of a participant file and resolve its columns."""
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(8192)
    return resolve_columns_from_text(sample, path.name)


def resolve_columns_from_text(text: str, source_name: str = "<text>") -> ColumnMap:
    """Resolve columns from the leading text of a participant file.

    Split out from ``resolve_columns`` so archive members can be resolved without being
    written to disk; the header reading logic is identical either way.
    """
    if not text.strip():
        raise MissingColumnsError(f"{source_name} is empty")

    delimiter = detect_delimiter(text)
    raw_headers = next(csv.reader(text.splitlines(), delimiter=delimiter))
    mapping = normalize_headers(raw_headers)

    missing = [name for name in REQUIRED_FIELDS if name not in mapping]
    if missing:
        raise MissingColumnsError(
            f"{source_name} is missing required column(s): {', '.join(missing)}; "
            f"found headers: {raw_headers}"
        )
    return ColumnMap(mapping=mapping, raw_headers=tuple(raw_headers))


def read_participant(path: Path) -> tuple[pd.DataFrame, ColumnMap]:
    """Read one participant file from disk into a frame named by canonical field.

    Values are read as-is: no rounding, no unit conversion, no filling. The returned
    frame has a ``timestamp`` column plus one column per canonical field the file
    provides, and nothing else.
    """
    return read_participant_bytes(path.read_bytes(), source_name=path.name)


def read_participant_bytes(data: bytes, source_name: str = "<bytes>") -> tuple[pd.DataFrame, ColumnMap]:
    """Read one participant file from raw bytes, for members inside a ZIP archive.

    The dataset ships a ZIP holding thousands of meal photographs, so participants are
    read straight out of the archive rather than extracted to disk.
    """
    text = data.decode("utf-8-sig")
    columns = resolve_columns_from_text(text, source_name)
    frame = pd.read_csv(io.StringIO(text), low_memory=False)

    renamed: dict[str, str] = {}
    for canonical_field, raw in columns.mapping.items():
        if canonical_field in REQUIRED_FIELDS or canonical_field in MEAL_COLUMNS:
            renamed[raw] = canonical_field
    frame = frame.rename(columns=renamed)

    frame = frame[[name for name in renamed.values()]]

    frame["timestamp"] = pd.to_datetime(
        frame["timestamp"], format=TIMESTAMP_FORMAT, errors="raise"
    )
    for canonical_field in ("dexcom", "libre"):
        frame[canonical_field] = pd.to_numeric(frame[canonical_field], errors="coerce")
    for canonical_field in MEAL_COLUMNS:
        if canonical_field in frame.columns and canonical_field != "meal_type":
            frame[canonical_field] = pd.to_numeric(frame[canonical_field], errors="coerce")

    return frame, columns


BIO_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "subject": ("subject",),
    "age": ("age",),
    "gender": ("gender",),
    "bmi": ("bmi",),
    "body_weight_kg": ("body weight",),
    "height_cm": ("height",),
    "self_identified_ethnicity": ("self-identify", "self identify"),
    "a1c_percent": ("a1c pdl (lab)",),
    "fasting_glucose_mgdl": ("fasting glu - pdl (lab)",),
    "insulin": ("insulin",),
    "triglycerides": ("triglycerides",),
    "cholesterol": ("cholesterol",),
    "hdl": ("hdl",),
    "non_hdl": ("non hdl",),
    "ldl_cal": ("ldl (cal)",),
    "vldl_cal": ("vldl (cal)",),
    "cho_hdl_ratio": ("cho/hdl ratio",),
    "collection_time": ("collection time pdl (lab)",),
}

BIO_NUMERIC_FIELDS: tuple[str, ...] = (
    "age", "bmi", "body_weight_kg", "height_cm", "a1c_percent", "fasting_glucose_mgdl",
    "insulin", "triglycerides", "cholesterol", "hdl", "non_hdl", "ldl_cal", "vldl_cal",
    "cho_hdl_ratio",
)


def read_bio(path: Path | io.IOBase) -> pd.DataFrame:
    """Read ``bio.csv`` into canonical participant columns.

    Accepts a path or an open binary handle, so the archive path and the directory path
    share one implementation. The published dictionary labels the HbA1c range as
    ``mmol/mol``; the values and the cohort's own band counts show they are percent. The
    code carries percent and does not propagate the dictionary's unit label.
    """
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    mapping = normalize_headers(frame.columns)

    resolved: dict[str, str] = {}
    for field_name, spellings in BIO_FIELD_ALIASES.items():
        for spelling in spellings:
            if spelling in mapping:
                resolved[field_name] = mapping[spelling]
                break

    missing = [name for name in ("subject", "a1c_percent") if name not in resolved]
    if missing:
        raise MissingColumnsError(
            f"bio.csv is missing required column(s): {', '.join(missing)}; "
            f"found headers: {list(frame.columns)}"
        )

    out = pd.DataFrame()
    for field_name, raw in resolved.items():
        out[field_name] = frame[raw]

    out["subject"] = out["subject"].astype(int)
    for field_name in BIO_NUMERIC_FIELDS:
        if field_name in out.columns:
            out[field_name] = pd.to_numeric(out[field_name], errors="coerce")
    if "self_identified_ethnicity" in out.columns:
        out["self_identified_ethnicity"] = (
            out["self_identified_ethnicity"].astype("string").str.strip()
        )
    return out
