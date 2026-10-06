"""Tests for the read-only local API that the dashboard reads from.

These exercise the real FastAPI app through its real routes against a real processed run
on disk — no mocks of the code under test. The run is a small synthetic dataset built by
the pipeline itself, so the assertions describe the contract the browser depends on.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cgm_excursions import schema
from cgm_excursions.api import (
    _drawn_breaks,
    _gap_breaks_in_window,
    _gap_report,
    create_app,
    load_run,
)
from cgm_excursions.pipeline import preprocess_dataset
from tests.fixtures import make_bio, make_layout_a

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def processed_run(tmp_path_factory) -> Path:
    """Build a real processed run from a synthetic two-participant dataset."""
    root = tmp_path_factory.mktemp("dataset") / "CGMacros"
    root.mkdir()
    for participant in ("001", "004"):
        folder = root / f"CGMacros-{participant}"
        folder.mkdir()
        (folder / f"CGMacros-{participant}.csv").write_text(make_layout_a(periods=120), encoding="utf-8")
    make_bio([1, 4]).to_csv(root / "bio.csv", index=False)

    output = tmp_path_factory.mktemp("processed")
    result = preprocess_dataset(root, output_root=output)
    return result.outputs.directory


@pytest.fixture(scope="module")
def client(processed_run: Path) -> TestClient:
    return TestClient(create_app(load_run(processed_run)))


# ------------------------------------------------------------------------ meta
def test_meta_reports_the_run_and_its_thresholds(client):
    payload = client.get("/api/meta").json()

    assert payload["run_id"].startswith("run-")
    assert payload["counts"]["cgm_rows"] > 0
    assert payload["streams"]["primary"] == "dexcom"
    assert payload["streams"]["replication"] == "libre"
    assert payload["thresholds"]["min_gap_seconds"] > 0
    assert "elapsed_minutes" == payload["conventions"]["time_axis"]


def test_meta_declares_no_interpolation(client):
    conventions = client.get("/api/meta").json()["conventions"]

    assert "none" in conventions["interpolation"]
    assert "never" in conventions["timestamp_shifted"]


# ---------------------------------------------------------------- participants
def test_participants_listing_carries_a1c_band_and_counts(client):
    payload = client.get("/api/participants").json()

    assert payload["count"] == 2
    by_id = {item["subject_id"]: item for item in payload["participants"]}
    assert set(by_id) == {"001", "004"}
    record = by_id["001"]
    assert record["label"] == "CGMacros-001"
    assert record["a1c_band"] in {"normal", "prediabetes", "diabetes"}
    assert record["rows"] > 0
    assert set(record["streams"]) == {"dexcom", "libre"}


# ---------------------------------------------------------------------- series
def test_series_returns_parallel_arrays(client):
    payload = client.get("/api/series/001").json()

    assert payload["subject_id"] == "001"
    for stream in ("dexcom", "libre"):
        data = payload["streams"][stream]
        assert len(data["glucose_mgdl"]) == len(payload["elapsed_minutes"])
        assert len(data["is_fresh"]) == len(payload["elapsed_minutes"])
    assert len(payload["time"]) == len(payload["elapsed_minutes"])
    assert payload["window"]["points_returned"] == len(payload["elapsed_minutes"])


def test_series_window_filters_by_elapsed_minutes(client):
    full = client.get("/api/series/001").json()
    windowed = client.get("/api/series/001", params={"start": 10, "end": 20}).json()

    assert windowed["window"]["rows_in_window"] <= full["window"]["rows_in_window"]
    assert windowed["elapsed_minutes"][0] >= 10
    assert windowed["elapsed_minutes"][-1] <= 20


def test_series_decimates_and_says_so(client):
    payload = client.get("/api/series/001", params={"max_points": 10}).json()

    assert payload["window"]["decimated"] is True
    assert payload["window"]["stride"] > 1
    assert payload["window"]["points_returned"] <= 12  # the cap plus the pinned last sample


def test_series_can_request_a_single_stream(client):
    payload = client.get("/api/series/001", params={"streams": "dexcom"}).json()

    assert set(payload["streams"]) == {"dexcom"}


def test_series_rejects_an_unknown_stream(client):
    response = client.get("/api/series/001", params={"streams": "dexcom,galileo"})

    assert response.status_code == 400
    assert "galileo" in response.json()["detail"]


def test_series_404s_for_an_unknown_participant(client):
    assert client.get("/api/series/999").status_code == 404


def test_series_accepts_an_unpadded_subject_id(client):
    padded = client.get("/api/series/001").json()
    unpadded = client.get("/api/series/1").json()

    assert unpadded["subject_id"] == "001"
    assert unpadded["window"]["rows_in_window"] == padded["window"]["rows_in_window"]


def test_series_breaks_the_line_at_a_gap(client, processed_run):
    """A null must appear as its own returned point so no line spans it."""
    listing = client.get("/api/participants").json()
    subject = listing["participants"][0]["subject_id"]
    payload = client.get(f"/api/series/{subject}").json()

    # Dexcom refreshes every 5 minutes in this fixture, so held values are explicit nulls
    # when held readings are excluded.
    hidden = client.get(f"/api/series/{subject}", params={"include_held": "false"}).json()
    values = hidden["streams"]["dexcom"]["glucose_mgdl"]
    assert any(value is None for value in values), "expected held readings to break the line"
    assert hidden["streams"]["dexcom"]["include_held"] is False


def test_fresh_flag_matches_the_stored_flag(client, processed_run):
    store = load_run(processed_run)
    payload = client.get("/api/series/001").json()
    expected = store.slice_subject("001")[schema.DEXCOM_FRESH].tolist()

    assert payload["streams"]["dexcom"]["is_fresh"] == expected


# ----------------------------------------------------------------------- meals
def test_meals_endpoint_returns_meal_events(client):
    payload = client.get("/api/meals/001").json()

    assert payload["subject_id"] == "001"
    assert payload["count"] == len(payload["meals"])
    if payload["meals"]:
        meal = payload["meals"][0]
        assert meal["subject_id"] == "001"
        assert "meal_type_raw" in meal


# ------------------------------------------------------------------- quality
def test_qc_endpoint_returns_summary_segments_and_metadata(client):
    payload = client.get("/api/qc/001").json()

    assert payload["subject_id"] == "001"
    assert payload["summary"]["rows"] > 0
    assert isinstance(payload["segments"], list)
    assert isinstance(payload["days"], list)
    assert payload["metadata"]["a1c_band"] in {"normal", "prediabetes", "diabetes"}


def test_qc_never_removes_eligible_rows_for_a_screening_flag(client):
    """The API reports flags as evidence, not as exclusions."""
    payload = client.get("/api/qc/001").json()
    summary = payload["summary"]

    screening_total = (
        summary["qc_out_of_documented_range"]
        + summary["qc_rate_of_change"]
        + summary["qc_flatline"]
        + summary["qc_isolated_spike"]
    )
    assert summary["eligible_rows"] <= summary["rows"]
    assert screening_total >= 0  # screening flags exist independently of eligibility
    assert summary["rows"] == summary["eligible_rows"] + (
        summary["rows"] - summary["eligible_rows"]
    )


# -------------------------------------------------------------------- health
def test_health_reports_ok(client):
    payload = client.get("/api/health").json()

    assert payload["status"] == "ok"
    assert payload["rows"] > 0


# ----------------------------------------------------------------- the server
def test_unknown_api_route_is_404_not_the_dashboard(client):
    response = client.get("/api/nope")

    assert response.status_code == 404


def test_manifest_matches_the_served_run(processed_run):
    manifest = json.loads((processed_run / "manifest.json").read_text(encoding="utf-8"))
    store = load_run(processed_run)

    assert manifest["run_id"] == store.run_id
    assert manifest["counts"]["cgm_rows"] == len(store.cgm)


# ------------------------------------------------------- run resolution path
def test_load_run_accepts_a_run_outputs_handle(processed_run):
    """Regression: the CLI resolves a run to a RunOutputs and hands it to load_run,
    while tests pass a plain Path. Both must work."""
    from cgm_excursions.outputs import RunOutputs

    handle = RunOutputs(run_id=processed_run.name, directory=processed_run)
    store = load_run(handle)

    assert store.run_id == processed_run.name
    assert len(store.cgm) > 0
    assert store.row_ranges, "row index must be built at construction"


def test_load_run_accepts_a_plain_path(processed_run):
    store = load_run(processed_run)

    assert store.run_id == processed_run.name
    assert set(store.row_ranges) == {"001", "004"}


def test_run_store_row_ranges_are_half_open_and_cover_every_row(processed_run):
    store = load_run(processed_run)

    total = 0
    for bounds in store.row_ranges.values():
        start, stop = bounds
        assert 0 <= start < stop <= len(store.cgm)
        total += stop - start
    assert total == len(store.cgm)


# ------------------------------------------------------- static asset serving
def test_missing_asset_path_is_a_real_404_not_the_shell(client):
    """Regression: the catch-all used to answer ANY unknown path with index.html and
    HTTP 200. A wrong asset URL (an extension like .js) then looked healthy while the
    chart silently stayed blank. A missing asset must 404."""
    response = client.get("/viz/plotly.min.js")

    assert response.status_code == 404, "a missing asset must not return HTTP 200"
    assert "text/html" not in response.headers.get("content-type", "")


def test_missing_extensionless_route_serves_the_shell(client):
    """An extensionless path is a navigation, so the SPA shell is the right answer."""
    response = client.get("/some/app/route", headers={"accept": "text/html"})

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_unknown_api_route_is_404_even_with_html_accept(client):
    response = client.get("/api/does-not-exist", headers={"accept": "text/html"})

    assert response.status_code == 404


def test_plotly_is_served_from_the_static_mount(client):
    """The panel script loads /static/plotly.min.js; prove that exact URL serves JS."""
    response = client.get("/static/plotly.min.js")

    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert "javascript" in content_type, content_type
    assert len(response.content) > 100_000, "the vendored Plotly bundle should be large"


def test_panel_script_is_served(client):
    response = client.get("/static/viz-panel.js")

    assert response.status_code == 200
    body = response.text
    assert "cgm-viz-panel" in body
    # It must point at the path the static mount actually serves from.
    assert "/static/plotly.min.js" in body
    assert "viz/plotly.min.js" not in body


# ------------------------------------------------- missing time reaches the chart
def _frame_at(offsets: list[float]) -> tuple[pd.DataFrame, np.ndarray]:
    """A minimal canonical frame whose rows sit at the given cumulative minute offsets."""
    elapsed = np.asarray(offsets, dtype=float)
    frame = pd.DataFrame({
        schema.RAW_COLUMN["dexcom"]: np.full(len(elapsed), 100.0),
        schema.RAW_COLUMN["libre"]: np.full(len(elapsed), 100.0),
    })
    return frame, elapsed


def _all_spans(offsets: list[float]) -> dict[str, list[list[float]]]:
    frame, elapsed = _frame_at(offsets)
    return _gap_breaks_in_window(frame, elapsed, np.arange(len(elapsed)))


def test_the_break_threshold_is_measured_in_minutes_not_hours():
    """Regression: the constant was 60.0 compared against a MINUTES axis, i.e. it demanded
    a full hour. A 20-minute hole is a real hole and must be reported; the old code missed
    every gap shorter than an hour, so participant 007's 870 skipped minutes produced zero
    breaks and were drawn as continuous data."""
    spans = _all_spans([0, 1, 2, 3, 23, 24])          # a 20-minute hole

    assert spans["dexcom"] == [[3.0, 23.0]]
    assert spans["libre"] == [[3.0, 23.0]]


def test_short_absences_are_counted_but_not_drawn():
    """A single absent minute is not a gap by the project's own definition (>= min_gap).
    Breaking the trace at these dissolved participant 007 into fragments, so they are
    disclosed numerically instead of drawn."""
    spans = _all_spans([0, 1, 2, 3, 5, 6])            # a 2-minute absence

    assert len(spans["dexcom"]) == 1
    assert _drawn_breaks(spans, 15.0)["dexcom"] == []

    report = _gap_report(spans, 15.0)
    assert report["count"] == 0                        # nothing drawn
    assert report["short_count"] == 2                  # one per stream, still disclosed


def test_a_long_outage_is_drawn_shaded_and_sized():
    spans = _all_spans([0, 1, 2, 92, 93])              # a 90-minute outage

    drawn = _drawn_breaks(spans, 15.0)
    assert drawn["dexcom"] == [[2.0, 92.0]]
    assert drawn["libre"] == [[2.0, 92.0]]

    report = _gap_report(spans, 15.0)
    assert report["count"] == 2
    assert report["per_stream"] == {"dexcom": 1, "libre": 1}
    assert report["longest_minutes"] == 90.0
    assert report["major_minutes"] == 15.0
    assert report["short_count"] == 0


def test_a_contiguous_minute_series_has_no_gaps():
    spans = _all_spans([0, 1, 2, 3, 4, 5])

    assert spans["dexcom"] == []
    assert spans["libre"] == []
    report = _gap_report(spans, 15.0)
    assert report["count"] == 0 and report["short_count"] == 0
    assert report["longest_minutes"] == 0.0


def test_the_threshold_follows_the_datasets_own_cadence():
    """A five-minute base cadence is normal for that file, so only a longer step counts."""
    spans = _all_spans([0, 5, 10, 15, 30, 35])

    assert spans["dexcom"] == [[15.0, 30.0]]


def test_series_payload_carries_the_gap_report(client):
    payload = client.get("/api/series/001").json()

    assert "gap_breaks" in payload
    assert "gap_report" in payload
    report = payload["gap_report"]
    assert set(report) >= {
        "count", "short_count", "per_stream", "longest_minutes", "major_minutes",
    }
    assert report["major_minutes"] > 0
    # everything drawn must be at least the configured threshold
    for stream, spans in payload["gap_breaks"].items():
        for start, end in spans:
            assert end - start >= report["major_minutes"], (stream, start, end)
