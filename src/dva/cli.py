"""Data Validation Accelerator CLI."""

from __future__ import annotations

from pathlib import Path

import duckdb
import typer

from dva.config import ConfigValidationError, load_config, validate_config
from dva.engine.orchestrator import Orchestrator

app = typer.Typer(help="Config-driven data validation accelerator for migration and ETL testing.")


@app.command()
def version() -> None:
    """Display the version of the Data Validation Accelerator."""
    typer.echo("Data Validation Accelerator v0.1.0")


@app.command("validate-config")
def validate_config_command(
    config: str = typer.Option(..., "--config", help="Path to the YAML validation project file"),
) -> None:
    """Validate a configuration file without running it."""
    try:
        loaded = load_config(config)
        validate_config(loaded)
    except (ConfigValidationError, Exception) as exc:  # noqa: BLE001
        typer.echo(f"Configuration file {config} is invalid: {exc}")
        raise typer.Exit(code=1) from exc
    typer.echo(f"Configuration file {config} is valid.")


@app.command()
def run(
    config: str = typer.Option(..., "--config", help="Path to the YAML validation project file"),
    output_path: str = typer.Option(
        None, "--output-path", help="Override the project's output_path"
    ),
) -> None:
    """Run validation using the specified configuration and print a summary."""
    try:
        loaded = load_config(config)
        validate_config(loaded)
        orchestrator = Orchestrator(loaded, output_path)
        run_summary = orchestrator.run_validation()
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Validation failed: {exc}")
        raise typer.Exit(code=1) from exc

    typer.echo(f"Run ID: {run_summary.run_id}")
    typer.echo(f"Status: {run_summary.status}")
    typer.echo(
        f"Datasets: {run_summary.dataset_count} total, "
        f"{run_summary.passed_count} passed, "
        f"{run_summary.failed_count} failed, "
        f"{run_summary.error_count} errored"
    )
    resolved_output = output_path or loaded.project.output_path
    typer.echo(
        f"Reports written to: {resolved_output}/{loaded.project.name}/run_id={run_summary.run_id}"
    )
    if run_summary.status in ("FAIL", "ERROR"):
        raise typer.Exit(code=1)


def _read_parquet(con: duckdb.DuckDBPyConnection, path: Path) -> list[dict]:
    if not path.exists():
        return []
    return con.execute(f"SELECT * FROM read_parquet('{path.as_posix()}')").to_arrow_table().to_pylist()


def _print_rows(title: str, rows: list[dict], columns: list[str] | None = None) -> None:
    typer.echo(f"\n-- {title} " + "-" * max(1, 40 - len(title)))
    if not rows:
        typer.echo("  (none)")
        return
    for row in rows:
        keys = columns or list(row.keys())
        typer.echo("  " + " | ".join(f"{k}={row.get(k)}" for k in keys))


def _print_detail(con: duckdb.DuckDBPyConnection, run_dir: Path, dataset_name: str | None) -> None:
    def _filtered(filename: str) -> list[dict]:
        rows = _read_parquet(con, run_dir / filename)
        if dataset_name:
            rows = [r for r in rows if r.get("dataset_name") == dataset_name]
        return rows

    _print_rows(
        "Schema contract checks",
        [r for r in _filtered("schema_results.parquet") if r["status"] != "PASS"],
        ["dataset_name", "check_name", "status", "details"],
    )
    _print_rows(
        "Count",
        _filtered("count_results.parquet"),
        ["dataset_name", "source_count", "target_count", "difference", "pct_difference", "status"],
    )
    _print_rows(
        "Duplicate keys",
        _filtered("duplicate_keys.parquet"),
        ["dataset_name", "side", "primary_key", "duplicate_count"],
    )
    _print_rows(
        "Missing records (in source, not target)",
        _filtered("missing_records.parquet"),
        ["dataset_name", "primary_key", "record"],
    )
    _print_rows(
        "Extra records (in target, not source)",
        _filtered("extra_records.parquet"),
        ["dataset_name", "primary_key", "record"],
    )
    _print_rows(
        "Row hash mismatches",
        _filtered("hash_mismatches.parquet"),
        ["dataset_name", "primary_key", "source_hash", "target_hash", "source_record", "target_record"],
    )
    _print_rows(
        "Aggregate mismatches",
        [r for r in _filtered("aggregate_results.parquet") if r["status"] != "PASS"],
        ["dataset_name", "group_key", "column", "metric", "source_value", "target_value",
         "pct_difference", "status"],
    )
    _print_rows(
        "Statistical mismatches",
        [r for r in _filtered("statistical_results.parquet") if r["status"] != "PASS"],
        ["dataset_name", "column", "metric", "source_value", "target_value", "pct_difference", "status"],
    )
    _print_rows(
        "Data quality failures",
        [r for r in _filtered("dq_results.parquet") if r["status"] != "PASS"],
        ["dataset_name", "rule_name", "rule_type", "side", "failed_count", "severity"],
    )
    _print_rows(
        "Validation issues",
        _filtered("validation_issues.parquet"),
        ["dataset_name", "rule_name", "issue_type", "severity", "failed_count", "sample_values"],
    )


@app.command()
def results(
    project: str = typer.Option(..., "--project", help="Project name"),
    output_path: str = typer.Option("./validation_runs", "--output-path"),
    failed_only: bool = typer.Option(False, "--failed-only", help="Only show FAIL/ERROR datasets"),
    detail: bool = typer.Option(
        False, "--detail", help="Show row/column-level detail (mismatches, missing/extra records, "
        "DQ failures, aggregate/statistical drift) for the latest run"
    ),
    dataset: str = typer.Option(
        None, "--dataset", help="Limit --detail output to a single dataset name"
    ),
) -> None:
    """Show dataset-level results for the most recent run of a project, via DuckDB."""
    project_dir = Path(output_path) / project
    if not project_dir.exists():
        typer.echo(f"No runs found for project '{project}' under {output_path}")
        raise typer.Exit(code=1)

    con = duckdb.connect(":memory:")
    latest_run_id = con.execute(
        f"""
        SELECT run_id FROM read_parquet('{project_dir.as_posix()}/run_id=*/run_summary.parquet')
        ORDER BY start_time DESC LIMIT 1
        """
    ).fetchone()
    if latest_run_id is None:
        typer.echo("No completed runs found.")
        raise typer.Exit(code=1)
    run_id = latest_run_id[0]

    typer.echo(f"Latest run: {run_id}")
    rows = con.execute(
        f"""
        SELECT dataset_name, status, source_count, target_count,
               missing_count, extra_count, mismatch_count
        FROM read_parquet('{project_dir.as_posix()}/run_id=*/dataset_summary.parquet')
        WHERE run_id = '{run_id}'
        {"AND status IN ('FAIL', 'ERROR')" if failed_only else ""}
        ORDER BY dataset_name
        """
    ).fetchall()
    columns = [
        "dataset_name", "status", "source_count", "target_count",
        "missing_count", "extra_count", "mismatch_count",
    ]
    for row in rows:
        typer.echo(" | ".join(f"{c}={v}" for c, v in zip(columns, row)))

    if detail:
        run_dir = project_dir / f"run_id={run_id}"
        _print_detail(con, run_dir, dataset)


if __name__ == "__main__":
    app()
