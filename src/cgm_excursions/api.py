"""The local HTTP API the dashboard reads from.

The dashboard used to ship each participant's glucose arrays as generated JavaScript, so
the browser never asked for anything. This module replaces that: the processed run is
loaded once into memory, indexed by participant, and served as JSON slices on request.

The server is read-only. Nothing here writes, and nothing leaves the machine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import schema
from .outputs import RunOutputs, load_manifest, load_qc_summary

WEB_ROOT = Path(__file__).resolve().parents[2] / "web"

# Hard ceiling on points returned in one series response. A caller may ask for fewer;
# asking for more is clamped rather than refused, and the clamp is reported back so a
# chart can never silently misrepresent how much of the record it is showing.
MAX_POINTS_PER_SERIES = 20000


@dataclass
class RunStore:
    """One processed run, held in memory for fast slicing.

    A 45-participant run is ~690k rows; the frame is held once and indexed by row range
    per participant, so a viewport change is a slice rather than a re-read.
    """

    run_id: str
    directory: Path
    cgm: pd.DataFrame
    meals: pd.DataFrame
    participants: pd.DataFrame
    manifest: dict[str, Any]
    qc_summary: dict[str, Any]
    # Row bounds per participant, computed once at construction. The frame is already
    # grouped by participant, so a viewport change is an iloc slice rather than a scan.
    row_ranges: dict[str, tuple[int, int]] = field(init=False, repr=False, default_factory=dict)

    def __post_init__(self) -> None:
        positions = self.cgm.groupby(schema.SUBJECT_ID, sort=False).indices
        self.row_ranges = {
            str(subject): (int(index[0]), int(index[-1]) + 1)
            for subject, index in positions.items()
        }

    @property
    def primary_stream(self) -> str:
        return str(self.manifest["config"]["effective"]["streams"]["primary"])

    @property
    def replication_stream(self) -> str:
        return str(self.manifest["config"]["effective"]["streams"]["replication"])

    def participant_count(self) -> int:
        return int(self.cgm[schema.SUBJECT_ID].nunique())

    def subject_or_404(self, subject_id: str) -> str:
        padded = subject_id.strip().zfill(3)
        if padded not in self.row_ranges:
            raise HTTPException(status_code=404, detail=f"unknown participant {subject_id!r}")
        return padded

    def slice_subject(self, subject_id: str) -> pd.DataFrame:
        start, stop = self.row_ranges[subject_id]
        return self.cgm.iloc[start:stop]

    def meals_for(self, subject_id: str) -> pd.DataFrame:
        if self.meals.empty:
            return self.meals
        return self.meals.loc[self.meals[schema.SUBJECT_ID] == subject_id]

    def metadata_for(self, subject_id: str) -> dict[str, Any]:
        if self.participants.empty:
            return {}
        match = self.participants.loc[self.participants[schema.SUBJECT_ID] == subject_id]
        if match.empty:
            return {}
        return _clean(match.iloc[0].to_dict())


def load_run(run: Path | RunOutputs) -> RunStore:
    """Load a processed run into memory.

    Accepts either the run directory or a ``RunOutputs`` handle, because the CLI resolves
    a run to a handle while tests and scripts usually have a plain path.
    """
    outputs = run if isinstance(run, RunOutputs) else RunOutputs(run_id=run.name, directory=run)
    directory = outputs.directory
    manifest = load_manifest(outputs)
    return RunStore(
        run_id=outputs.run_id,
        directory=directory,
        cgm=pd.read_parquet(directory / "cgm.parquet"),
        meals=pd.read_parquet(directory / "meals.parquet"),
        participants=pd.read_parquet(directory / "participants.parquet"),
        manifest=manifest,
        qc_summary=load_qc_summary(outputs),
    )


def create_app(store: RunStore, *, web_root: Path | None = None) -> FastAPI:
    """Build the dashboard server for one processed run."""
    app = FastAPI(
        title="CGM Excursion Detection",
        version=str(store.manifest.get("pipeline_version", "unknown")),
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.store = store

    # ------------------------------------------------------------------ meta
    @app.get("/api/meta")
    def get_meta() -> dict[str, Any]:
        manifest = store.manifest
        effective = manifest["config"]["effective"]
        return {
            "run_id": store.run_id,
            "pipeline_version": manifest.get("pipeline_version"),
            "generated_at": manifest.get("generated_at"),
            "dataset": {
                "kind": manifest["dataset"]["kind"],
                "participant_count": manifest["dataset"]["participant_count"],
                "root": manifest["dataset"]["root"],
            },
            "counts": manifest["counts"],
            "streams": {
                "primary": store.primary_stream,
                "replication": store.replication_stream,
                "documented_range_mgdl": effective["streams"]["documented_range_mgdl"],
            },
            "thresholds": {
                "max_mgdl_per_min": effective["qc"]["rate_of_change"]["max_mgdl_per_min"],
                "flatline_min_run_minutes": effective["qc"]["flatline"]["min_run_minutes"],
                "min_gap_seconds": effective["gaps"]["min_gap_seconds"],
                "segment_break_seconds": effective["gaps"]["segment_break_seconds"],
                "compression_low_mgdl": effective["qc"]["possible_compression_low"]["value_mgdl"],
            },
            "conventions": manifest.get("conventions", {}),
        }

    # ---------------------------------------------------------- participants
    @app.get("/api/participants")
    def get_participants() -> dict[str, Any]:
        summary_by_subject = {
            record["subject_id"]: record
            for record in store.qc_summary.get("participants", [])
        }
        metadata_by_subject = {}
        if not store.participants.empty:
            metadata_by_subject = {
                str(row[schema.SUBJECT_ID]): row for _, row in store.participants.iterrows()
            }

        meal_counts: dict[str, int] = {}
        if not store.meals.empty:
            meal_counts = (
                store.meals[schema.SUBJECT_ID].value_counts().to_dict()
            )

        items: list[dict[str, Any]] = []
        for subject_id in sorted(store.row_ranges):
            summary = summary_by_subject.get(subject_id, {})
            metadata = metadata_by_subject.get(subject_id, {})
            items.append({
                "subject_id": subject_id,
                "label": f"CGMacros-{subject_id}",
                "a1c_percent": _finite(metadata.get("a1c_percent")),
                "a1c_band": metadata.get("a1c_band"),
                "age": _finite(metadata.get("age")),
                "gender": metadata.get("gender"),
                "bmi": _finite(metadata.get("bmi")),
                "rows": summary.get("rows", 0),
                "eligible_rows": summary.get("eligible_rows", 0),
                "meal_count": int(meal_counts.get(subject_id, 0)),
                "first_timestamp": summary.get("first_timestamp"),
                "last_timestamp": summary.get("last_timestamp"),
                "span_minutes": summary.get("span_minutes"),
                "streams": {
                    stream: summary.get(stream, {}) for stream in ("dexcom", "libre")
                },
            })
        return {"run_id": store.run_id, "count": len(items), "participants": items}

    # ----------------------------------------------------------------- series
    @app.get("/api/series/{subject_id}")
    def get_series(
        subject_id: str,
        start: float = Query(0.0, description="Start of the window, in elapsed minutes."),
        end: float | None = Query(None, description="End of the window, in elapsed minutes."),
        streams: str = Query("dexcom,libre", description="Comma-separated stream names."),
        include_held: bool = Query(
            True,
            description=(
                "Include carried-forward readings. The chart hides them by default "
                "because they are not new measurements."
            ),
        ),
        max_points: int = Query(
            4000, ge=2, description="Upper bound on points per stream in the response."
        ),
    ) -> dict[str, Any]:
        subject = store.subject_or_404(subject_id)
        frame = store.slice_subject(subject)
        if frame.empty:
            raise HTTPException(status_code=404, detail=f"no rows for participant {subject}")

        requested = [name.strip() for name in streams.split(",") if name.strip()]
        unknown = [name for name in requested if name not in schema.SENSORS]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"unknown stream(s) {unknown}; known streams are {list(schema.SENSORS)}",
            )

        elapsed = frame[schema.ELAPSED_MINUTES].to_numpy()
        window = (elapsed >= start) & (elapsed <= end if end is not None else True)
        positions = np.nonzero(window)[0]
        if positions.size == 0:
            return _empty_series(subject, start, end, requested)

        clamped = min(int(max_points), MAX_POINTS_PER_SERIES)
        stride = max(1, int(math.ceil(positions.size / clamped)))
        # Always keep the window's first and last sample so the drawn span is truthful.
        selected = positions[::stride]
        if selected[-1] != positions[-1]:
            selected = np.append(selected, positions[-1])

        timestamps = frame[schema.TIMESTAMP].to_numpy()[selected]
        payload: dict[str, Any] = {
            "subject_id": subject,
            "window": {
                "start": float(elapsed[selected[0]]),
                "end": float(elapsed[selected[-1]]),
                "requested_start": start,
                "requested_end": end,
                "rows_in_window": int(positions.size),
                "points_returned": int(selected.size),
                "stride": int(stride),
                "decimated": bool(stride > 1),
            },
            "time": [pd.Timestamp(value).isoformat() for value in timestamps],
            "elapsed_minutes": [float(value) for value in elapsed[selected]],
            "streams": {},
        }

        for stream in requested:
            raw = frame[schema.RAW_COLUMN[stream]].to_numpy()[selected]
            fresh = frame[schema.FRESH_COLUMN[stream]].to_numpy()[selected]
            payload["streams"][stream] = {
                "glucose_mgdl": [None if pd.isna(value) else float(value) for value in raw],
                "is_fresh": [bool(value) for value in fresh],
                "observed_count": int(np.count_nonzero(~pd.isna(raw))),
                "fresh_count": int(np.count_nonzero(fresh)),
                "include_held": bool(include_held),
            }

        payload["segments"] = _segments_in_window(frame, elapsed, selected)
        breaks = _gap_breaks_in_window(frame, elapsed, selected)
        min_gap = _configured_min_gap_minutes(store)
        payload["gap_breaks"] = _drawn_breaks(breaks, min_gap)
        payload["gap_report"] = _gap_report(breaks, min_gap)
        return payload

    # ------------------------------------------------------------------ meals
    @app.get("/api/meals/{subject_id}")
    def get_meals(subject_id: str) -> dict[str, Any]:
        subject = store.subject_or_404(subject_id)
        meals = store.meals_for(subject)
        return {
            "subject_id": subject,
            "count": int(len(meals)),
            "meals": [_clean(record) for record in meals.to_dict(orient="records")],
        }

    # --------------------------------------------------------------- quality
    @app.get("/api/qc/{subject_id}")
    def get_qc(subject_id: str) -> dict[str, Any]:
        subject = store.subject_or_404(subject_id)
        record = next(
            (item for item in store.qc_summary.get("participants", [])
             if item["subject_id"] == subject),
            None,
        )
        if record is None:
            raise HTTPException(status_code=404, detail=f"no QC summary for {subject}")
        segments = [
            item for item in store.qc_summary.get("segments", [])
            if item["subject_id"] == subject
        ]
        days = [
            item for item in store.qc_summary.get("days", [])
            if item["subject_id"] == subject
        ]
        return {
            "subject_id": subject,
            "summary": record,
            "segments": segments,
            "days": days,
            "metadata": store.metadata_for(subject),
        }

    @app.get("/api/qc")
    def get_qc_overview() -> dict[str, Any]:
        return {
            "run_id": store.run_id,
            "participants": store.qc_summary.get("participants", []),
            "segment_count": len(store.qc_summary.get("segments", [])),
            "day_count": len(store.qc_summary.get("days", [])),
        }

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "run_id": store.run_id, "rows": int(len(store.cgm))}

    # ---------------------------------------------------------------- static
    @app.middleware("http")
    async def _revalidate_assets(request: Request, call_next: Any) -> Any:
        """Require revalidation for static assets.

        Starlette serves them with only an ETag and Last-Modified, which a browser may reuse
        from cache without asking. An edited viz-panel.js then appears not to have taken
        effect until a hard reload -- the change looks lost. This is a local research app,
        so a 304 round-trip costs nothing next to silently stale UI.
        """
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    root = web_root or WEB_ROOT
    if root.is_dir():
        app.mount("/static", StaticFiles(directory=str(root / "static")), name="static")

        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            return FileResponse(root / "index.html")

        @app.get("/{path:path}", include_in_schema=False)
        def static_or_404(path: str, request: Request) -> Any:
            candidate = (root / path).resolve()
            try:
                candidate.relative_to(root.resolve())
            except ValueError:
                raise HTTPException(status_code=404, detail="not found")
            if candidate.is_file():
                return FileResponse(candidate)
            if path.startswith("api/"):
                raise HTTPException(status_code=404, detail="unknown endpoint")
            # Serve the shell only for a genuine navigation. A missing asset must be a
            # real 404: falling back to index.html with HTTP 200 makes a broken asset
            # path look healthy and hides the failure until the chart is silently blank.
            if _looks_like_navigation(request):
                return FileResponse(root / "index.html")
            raise HTTPException(status_code=404, detail=f"no such file: {path}")

    else:
        @app.get("/", include_in_schema=False)
        def missing_web_root() -> JSONResponse:
            return JSONResponse(
                status_code=500,
                content={"detail": f"dashboard assets not found at {root}"},
            )

    return app


def _looks_like_navigation(request: Request) -> bool:
    """Whether a request for a missing path should receive the app shell.

    A path whose last segment carries a file extension is an asset request, and returns
    404 when it is missing. Only extensionless HTML navigations fall back to the shell.
    """
    last_segment = str(request.url.path).rsplit("/", 1)[-1]
    if "." in last_segment:
        return False
    accept = request.headers.get("accept", "")
    return "text/html" in accept or "*/*" in accept


def _segments_in_window(
    frame: pd.DataFrame, elapsed: np.ndarray, selected: np.ndarray
) -> list[dict[str, Any]]:
    """Eligible segments overlapping the returned points, so the chart can shade them."""
    segment_ids = frame[schema.SEGMENT_ID].to_numpy()
    window_ids = {value for value in segment_ids[selected] if value is not None and not pd.isna(value)}
    if not window_ids:
        return []

    window_elapsed = elapsed[selected]
    segments: list[dict[str, Any]] = []
    for segment_id in sorted(window_ids):
        mask = segment_ids == segment_id
        if not mask.any():
            continue
        segment_elapsed = elapsed[mask]
        start = max(float(segment_elapsed.min()), float(window_elapsed[0]))
        end = min(float(segment_elapsed.max()), float(window_elapsed[-1]))
        if end >= start:
            segments.append({
                "segment_id": int(segment_id),
                "start_elapsed_minutes": start,
                "end_elapsed_minutes": end,
                "rows": int(mask.sum()),
            })
    return segments


def _configured_min_gap_minutes(store: RunStore) -> float:
    """The configured gap threshold in minutes, so the chart shades what the run calls a gap."""
    try:
        seconds = float(store.manifest["config"]["effective"]["gaps"]["min_gap_seconds"])
    except (KeyError, TypeError, ValueError):
        return 15.0
    return seconds / 60.0


def _gap_breaks_in_window(
    frame: pd.DataFrame, elapsed: np.ndarray, selected: np.ndarray
) -> dict[str, list[list[float]]]:
    """Per-stream intervals the chart must visibly break instead of connecting.

    ``elapsed`` is measured in MINUTES. A break is any interval longer than the dataset's
    own base cadence, because the file simply holds no sample in between and joining
    across it would draw data that was never recorded.

    This previously compared minutes against a ``60.0`` constant -- a 60x unit error that
    set the threshold to one hour. Every gap shorter than an hour was therefore silently
    connected: participant 007 skips 870 minutes and yielded zero breaks, so its 23-minute
    holes were drawn as continuous data. The base cadence is now measured from the window
    itself, so the rule adapts instead of hard-coding an assumption.
    """
    steps = np.diff(elapsed)
    positive = steps[steps > 0]
    base = float(positive.min()) if positive.size else 1.0
    tolerance = base + 1e-9

    breaks: dict[str, list[list[float]]] = {}
    for stream in schema.SENSORS:
        observed = frame[schema.RAW_COLUMN[stream]].notna().to_numpy()
        last: float | None = None
        spans: list[list[float]] = []
        for position in range(len(elapsed)):
            if not observed[position]:
                continue
            if last is not None and elapsed[position] - last > tolerance:
                spans.append([float(last), float(elapsed[position])])
            last = float(elapsed[position])
        window_start, window_end = float(elapsed[selected[0]]), float(elapsed[selected[-1]])
        breaks[stream] = [
            [max(start, window_start), min(end, window_end)]
            for start, end in spans
            if end >= window_start and start <= window_end
        ]
    return breaks


def _drawn_breaks(
    breaks: dict[str, list[list[float]]], major_minutes: float
) -> dict[str, list[list[float]]]:
    """Keep only the spans long enough to be drawn.

    The raw discontinuity list is every step above the base cadence, which includes
    single absent minutes. Breaking the trace at those dissolves a curve into fragments --
    participant 007 has 870 of them and became unreadable. The project's own configuration
    already defines a gap as a run of at least ``gaps.min_gap_seconds``, so that is the
    threshold the chart draws at, and the shorter absences are disclosed in the readout
    rather than drawn. Nothing is hidden; the granularity is simply stated.
    """
    return {
        stream: [span for span in spans if span[1] - span[0] >= major_minutes]
        for stream, spans in breaks.items()
    }


def _gap_report(
    breaks: dict[str, list[list[float]]], major_minutes: float
) -> dict[str, Any]:
    """Window-level summary of unsampled stretches, for the chart's completeness readout."""
    spans = [span for stream in breaks for span in breaks[stream]]
    durations = [end - start for start, end in spans]
    drawn = [value for value in durations if value >= major_minutes]
    return {
        "count": len(drawn),
        "short_count": len(durations) - len(drawn),
        "per_stream": {
            stream: sum(1 for span in spans_ if span[1] - span[0] >= major_minutes)
            for stream, spans_ in breaks.items()
        },
        "longest_minutes": float(max(durations)) if durations else 0.0,
        "major_minutes": float(major_minutes),
    }


def _empty_series(
    subject: str, start: float, end: float | None, streams: list[str]
) -> dict[str, Any]:
    return {
        "subject_id": subject,
        "window": {
            "start": None,
            "end": None,
            "requested_start": start,
            "requested_end": end,
            "rows_in_window": 0,
            "points_returned": 0,
            "stride": 1,
            "decimated": False,
        },
        "time": [],
        "elapsed_minutes": [],
        "streams": {
            stream: {
                "glucose_mgdl": [], "is_fresh": [],
                "observed_count": 0, "fresh_count": 0, "include_held": True,
            }
            for stream in streams
        },
        "segments": [],
        "gap_breaks": {stream: [] for stream in schema.SENSORS},
    }


def _clean(record: dict[str, Any]) -> dict[str, Any]:
    """JSON-safe values: NaN and pandas scalars do not survive serialization."""
    cleaned: dict[str, Any] = {}
    for key, value in record.items():
        if value is None or (isinstance(value, float) and math.isnan(value)):
            cleaned[key] = None
        elif isinstance(value, (np.integer,)):
            cleaned[key] = int(value)
        elif isinstance(value, (np.floating,)):
            cleaned[key] = None if math.isnan(float(value)) else float(value)
        elif isinstance(value, (np.bool_,)):
            cleaned[key] = bool(value)
        elif isinstance(value, pd.Timestamp):
            cleaned[key] = value.isoformat()
        elif isinstance(value, float) and math.isnan(value):
            cleaned[key] = None
        else:
            cleaned[key] = value
    return cleaned


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number
