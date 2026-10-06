"""Header normalization — the layer that must not be fooled by the five real layouts.

These tests encode the traps found in the actual CGMacros files. In particular
`CGMacros-004` lists Dexcom before Libre; a positional parser silently swaps the two
sensors and produces a plausible, wrong result, so the assertions here are about
*identity of the stream*, never about column order.
"""

from __future__ import annotations

import pytest

from cgm_excursions.reading import (
    MEAL_COLUMNS,
    MissingColumnsError,
    normalize_headers,
    resolve_columns,
)
from tests.fixtures import (
    make_layout_a,
    make_layout_b_swapped_sensors,
    make_layout_c_steps_index,
)


@pytest.mark.parametrize(
    "make_csv, expected_dexcom, expected_libre",
    [
        (make_layout_a, "Dexcom GL", "Libre GL"),
        (make_layout_b_swapped_sensors, "Dexcom GL", "Libre GL"),
        (make_layout_c_steps_index, "Dexcom GL", "Libre GL"),
    ],
)
def test_sensor_columns_resolve_by_name_not_position(
    make_csv, expected_dexcom, expected_libre, tmp_path
):
    path = tmp_path / "participant.csv"
    path.write_text(make_csv(), encoding="utf-8")

    columns = resolve_columns(path)

    assert columns.timestamp == "Timestamp"
    assert columns.dexcom == expected_dexcom
    assert columns.libre == expected_libre
    # The two streams must never be aliased to the same source column.
    assert columns.dexcom != columns.libre


def test_trailing_whitespace_in_header_is_tolerated(tmp_path):
    path = tmp_path / "participant.csv"
    path.write_text(make_layout_a(), encoding="utf-8")

    columns = resolve_columns(path)

    # The real files spell this column "Amount Consumed " with a trailing space.
    assert columns.of("amount_consumed") == "Amount Consumed "


def test_activity_column_accepts_mets_or_intensity(tmp_path):
    with_mets = tmp_path / "a.csv"
    with_mets.write_text(make_layout_a(), encoding="utf-8")
    with_intensity = tmp_path / "b.csv"
    with_intensity.write_text(
        make_layout_a().replace(",METs,", ",Intensity,"), encoding="utf-8"
    )

    assert normalize_headers(resolve_columns(with_mets).all_headers())["mets"]
    assert normalize_headers(resolve_columns(with_intensity).all_headers())["mets"]


def test_leading_unnamed_index_column_is_not_treated_as_data(tmp_path):
    path = tmp_path / "participant.csv"
    path.write_text(make_layout_a(), encoding="utf-8")

    columns = resolve_columns(path)

    assert "Unnamed: 0" not in columns.required_sources()


def test_missing_sensor_column_raises_with_the_column_name(tmp_path):
    path = tmp_path / "participant.csv"
    broken = make_layout_a().replace("Dexcom GL", "DexcomXYZ")
    path.write_text(broken, encoding="utf-8")

    with pytest.raises(MissingColumnsError) as excinfo:
        resolve_columns(path)

    assert "dexcom" in str(excinfo.value).lower()


def test_meal_columns_are_all_optional(tmp_path):
    """A file with no meal columns at all is still readable."""
    path = tmp_path / "participant.csv"
    header = "Timestamp,Libre GL,Dexcom GL\n"
    body = "\n".join(
        f"2020-05-01 11:{minute:02d}:00,100.0,120.0" for minute in range(5)
    )
    path.write_text(header + body + "\n", encoding="utf-8")

    columns = resolve_columns(path)

    assert columns.of("meal_type") is None
    for name in MEAL_COLUMNS:
        assert columns.of(name) is None


def test_normalize_headers_is_idempotent_and_case_insensitive():
    raw = ["Timestamp", "Dexcom GL ", "LIBRE GL", "Meal Type", "Amount Consumed "]

    once = normalize_headers(raw)
    twice = normalize_headers(raw)

    assert once == twice
    assert once["dexcom"] == "Dexcom GL "
    assert once["libre"] == "LIBRE GL"
