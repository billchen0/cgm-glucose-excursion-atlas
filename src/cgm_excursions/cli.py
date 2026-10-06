"""Command line entry points.

Three verbs, in the order a user needs them:

    cgm audit       what is actually in these files?
    cgm preprocess  turn the dataset into the canonical tables
    cgm serve       open the dashboard against the processed run

``audit`` and ``preprocess`` read the dataset; only ``preprocess`` writes, and only into
``data/processed`` (git-ignored). ``serve`` is read-only apart from remembering the
dataset path in a local, ignored config file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .audit import audit_dataset
from .config import load_config
from .dataset import DatasetNotFoundError, resolve_dataset
from .outputs import latest_run, load_qc_summary, summarize_for_stdout

app = typer.Typer(
    add_completion=False,
    help="Local-first CGM preprocessing and dashboard.",
    no_args_is_help=True,
)

DEFAULT_PROCESSED_ROOT = Path("data/processed")
LOCAL_CONFIG_FILENAME = ".cgm-local.yaml"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"cgm-excursions {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Local-first CGM preprocessing and dashboard."""


@app.command()
def audit(
    dataset: Path = typer.Argument(
        ..., help="Path to the CGMacros ZIP or its extracted directory."
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", help="Audit only the first N participants."
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit the full report as JSON instead of a summary."
    ),
) -> None:
    """Report what the dataset actually contains, reading only."""
    try:
        report = audit_dataset(dataset, limit=limit)
    except DatasetNotFoundError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    if as_json:
        typer.echo(json.dumps(report, indent=2, default=str))
        return

    cohort = report["cohort"]
    info = report["dataset"]
    typer.echo(f"dataset        {info['root']}")
    typer.echo(f"layout         {info['kind']}, {info['participant_count']} participants "
               f"({info['audited_count']} audited)")
    typer.echo(f"rows           {cohort['total_rows']:,}")
    base = cohort.get("base_interval_seconds")
    longest = cohort.get("longest_interval_seconds")
    typer.echo(f"cadence        base {base:.0f} s, longest {longest:,.0f} s")
    typer.echo(
        f"skipped mins   {cohort['intervals_above_base']:,} intervals above base across "
        f"{cohort['participants_with_skipped_minutes']} participants"
    )
    typer.echo(f"dup timestamps {cohort['participants_with_duplicate_timestamps']} participants")
    typer.echo(f"out of order   {cohort['participants_out_of_time_order']} participants")
    typer.echo(f"no sensor      {cohort['rows_with_no_sensor_value']:,} rows")
    for stream in ("dexcom", "libre"):
        held = cohort[f"{stream}_held_fraction"]
        typer.echo(
            f"{stream:<14} held {held['median']:.1%} of readings "
            f"(min {held['min']:.1%}, max {held['max']:.1%})"
        )
    typer.echo("")
    typer.echo("header layouts")
    for layout in report["header_layouts"]:
        parts = [
            f"{layout['participant_count']}x",
            layout["sensor_order"],
            f"activity={layout['activity_column']}",
        ]
        if layout["has_leading_index_column"]:
            parts.append("leading-index")
        if layout["has_steps"]:
            parts.append("steps")
        if layout["has_record_index"]:
            parts.append("record-index")
        if layout["headers_with_surrounding_space"]:
            parts.append(f"padded={layout['headers_with_surrounding_space']}")
        typer.echo(f"  {'  '.join(parts)}")
        typer.echo(f"    e.g. {', '.join(layout['subject_ids'][:6])}")


@app.command()
def preprocess(
    dataset: Path = typer.Argument(
        ..., help="Path to the CGMacros ZIP or its extracted directory."
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", help="Preprocessing config (defaults to config/preprocessing.yaml)."
    ),
    output: Path = typer.Option(
        DEFAULT_PROCESSED_ROOT, "--output", help="Where to write run artifacts."
    ),
    quick_fingerprint: bool = typer.Option(
        False, "--quick-fingerprint",
        help="Skip hashing participant contents. Fast, but cannot detect an altered input.",
    ),
) -> None:
    """Preprocess the dataset into the canonical tables.

    Writes nothing outside the output directory, and never modifies the dataset.
    """
    from .pipeline import preprocess_dataset

    try:
        resolved_config = load_config(config)
    except ValueError as error:
        typer.secho(f"config error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    def report(index: int, total: int, subject_id: str) -> None:
        typer.echo(f"  [{index:>3}/{total}] participant {subject_id}", err=True)

    try:
        result = preprocess_dataset(
            dataset,
            config=resolved_config,
            output_root=output,
            fingerprint_full=not quick_fingerprint,
            on_progress=report,
        )
    except DatasetNotFoundError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    typer.echo("")
    typer.echo(summarize_for_stdout(result.manifest))
    typer.echo(f"output     {result.outputs.directory}")
    _remember_dataset_path(dataset)


@app.command()
def serve(
    dataset: Path = typer.Option(
        None, "--data", help="Dataset path to preprocess if no run exists yet."
    ),
    processed: Path = typer.Option(
        DEFAULT_PROCESSED_ROOT, "--processed", help="Directory holding processed runs."
    ),
    run: Optional[str] = typer.Option(
        None, "--run", help="Run id to serve (defaults to the most recent)."
    ),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port"),
    reload: bool = typer.Option(False, "--reload", help="Reload on code changes."),
) -> None:
    """Serve the dashboard against a processed run.

    If no processed run exists, ``--data`` is preprocessed first. The dataset path is
    remembered in a git-ignored local config file so later launches need no arguments.
    """
    import uvicorn

    from .api import create_app, load_run

    resolved_run = _resolve_run(processed, run, dataset)
    if resolved_run is None:
        typer.secho(
            f"no processed run found in {processed}. Run `cgm preprocess <dataset>` "
            "first, or pass --data <dataset> to preprocess now.",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=2)

    store = load_run(resolved_run)
    typer.echo(f"serving run {store.run_id} ({store.participant_count()} participants)")
    typer.echo(f"  http://{host}:{port}/")
    application = create_app(store)
    uvicorn.run(application, host=host, port=port, reload=reload, log_level="info")


def _resolve_run(processed: Path, run_id: str | None, dataset: Path | None):
    """Find the run to serve, preprocessing the dataset first if one is not available."""
    if run_id:
        from .outputs import RunOutputs

        directory = processed / run_id
        if not (directory / "manifest.json").exists():
            return None
        return RunOutputs(run_id=run_id, directory=directory)

    existing = latest_run(processed)
    if existing is not None:
        return existing

    remembered = dataset or _remembered_dataset_path()
    if remembered is None:
        return None

    from .pipeline import preprocess_dataset

    typer.echo(f"no processed run yet; preprocessing {remembered}")
    result = preprocess_dataset(remembered, output_root=processed)
    typer.echo(summarize_for_stdout(result.manifest))
    return result.outputs


def _local_config_path() -> Path:
    return Path.cwd() / LOCAL_CONFIG_FILENAME


def _remember_dataset_path(dataset: Path) -> None:
    """Record the dataset path locally so a later launch needs no arguments."""
    path = _local_config_path()
    resolved = str(dataset.expanduser().resolve())
    path.write_text(
        "# Written by `cgm`; git-ignored. Records the dataset this checkout uses.\n"
        f"dataset: {resolved}\n",
        encoding="utf-8",
    )


def _remembered_dataset_path() -> Path | None:
    import yaml

    path = _local_config_path()
    if not path.exists():
        return None
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    value = payload.get("dataset")
    if not value:
        return None
    candidate = Path(value).expanduser()
    return candidate if candidate.exists() else None


@app.command()
def summary(
    processed: Path = typer.Option(DEFAULT_PROCESSED_ROOT, "--processed"),
    run: Optional[str] = typer.Option(None, "--run"),
) -> None:
    """Print the coverage summary of a processed run."""
    from .outputs import RunOutputs

    if run:
        outputs = RunOutputs(run_id=run, directory=processed / run)
    else:
        outputs = latest_run(processed)
    if outputs is None or not outputs.manifest_path.exists():
        typer.secho(f"no processed run in {processed}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    payload = load_qc_summary(outputs)
    manifest = payload["manifest"]
    typer.echo(summarize_for_stdout({**manifest, "files": {}}))
    typer.echo("")
    typer.echo(f"{'subject':<9}{'rows':>8}{'eligible':>10}{'dexcom':>9}{'libre':>9}"
               f"{'held%':>8}{'segments':>10}{'longest gap':>13}")
    segments_by_subject: dict[str, int] = {}
    for segment in payload["segments"]:
        segments_by_subject[segment["subject_id"]] = (
            segments_by_subject.get(segment["subject_id"], 0) + 1
        )
    for record in payload["participants"]:
        longest = max(record["dexcom"]["longest_gap_seconds"],
                      record["libre"]["longest_gap_seconds"])
        typer.echo(
            f"{record['subject_id']:<9}{record['rows']:>8,}{record['eligible_rows']:>10,}"
            f"{record['dexcom']['observed_count']:>9,}{record['libre']['observed_count']:>9,}"
            f"{100 * record['dexcom']['held_fraction']:>7.1f}%"
            f"{segments_by_subject.get(record['subject_id'], 0):>10}"
            f"{longest / 60:>10.0f} min"
        )


if __name__ == "__main__":  # pragma: no cover
    app()
