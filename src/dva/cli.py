"""Data Validation Accelerator CLI."""

from __future__ import annotations

from dva.config.certs import configure_tls_trust

configure_tls_trust()

import psycopg
import typer

from dva.config import ConfigValidationError, load_config, validate_config
from dva.engine.orchestrator import Orchestrator
from dva.engine.run_scope import RunScope, parse_dataset_names, parse_validation_types
from dva.reporting.database import apply_schema, connect, get_database_url

app = typer.Typer(help="Config-driven data validation accelerator for migration and ETL testing.")


@app.command()
def version() -> None:
    """Display the version of the Data Validation Accelerator."""
    typer.echo("Data Validation Accelerator v0.1.0")


@app.command("init-db")
def init_db(
    database_url: str = typer.Option(
        None, "--database-url", help="Postgres URL (defaults to DVA_DATABASE_URL env var)"
    ),
) -> None:
    """Create or update the Postgres schema for validation results."""
    url = get_database_url(database_url)
    try:
        with connect(url) as conn:
            apply_schema(conn)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Failed to initialize database: {exc}")
        raise typer.Exit(code=1) from exc
    typer.echo(f"Database schema applied at {url}")


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
    datasets: str = typer.Option(
        None,
        "--datasets",
        help="Comma-separated dataset names or globs to run (default: all datasets)",
    ),
    validations: str = typer.Option(
        None,
        "--validations",
        help="Comma-separated validation types to run (aliases: hash, stats, agg, dq, duplicates)",
    ),
    skip_validations: str = typer.Option(
        None,
        "--skip-validations",
        help="Comma-separated validation types to skip (default: run all six core types)",
    ),
    allow_validation_fail: bool = typer.Option(
        False,
        "--allow-validation-fail",
        help="Exit 0 even when validation status is FAIL or ERROR (for seeding/demo scripts)",
    ),
) -> None:
    """Run validation using the specified configuration and print a summary."""
    try:
        loaded = load_config(config)
        validate_config(loaded)
        dataset_names = parse_dataset_names(
            datasets, [dataset.name for dataset in loaded.datasets]
        )
        validation_types = parse_validation_types(validations, skip=skip_validations)
        scope = RunScope(
            dataset_names=tuple(dataset_names) if dataset_names else None,
            validation_types=validation_types,
        )
        orchestrator = Orchestrator(loaded, output_path, scope=scope)
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
    db_url = get_database_url(loaded.project.results_database_url)
    typer.echo(f"Results written to Postgres: {db_url}")
    resolved_output = output_path or loaded.project.output_path
    typer.echo(
        f"Run artifacts: {resolved_output}/{loaded.project.name}/run_id={run_summary.run_id}"
    )
    if run_summary.status in ("FAIL", "ERROR") and not allow_validation_fail:
        raise typer.Exit(code=1)


def _fetch_rows(conn: psycopg.Connection, sql: str, params: tuple | dict | None = None) -> list[dict]:
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(sql, params or ())
        return list(cur.fetchall())


def _print_rows(title: str, rows: list[dict], columns: list[str] | None = None) -> None:
    typer.echo(f"\n-- {title} " + "-" * max(1, 40 - len(title)))
    if not rows:
        typer.echo("  (none)")
        return
    for row in rows:
        keys = columns or list(row.keys())
        typer.echo("  " + " | ".join(f"{k}={row.get(k)}" for k in keys))


def _make_filtered(
    conn: psycopg.Connection, run_id: str, dataset_name: str | None
):
    def _filtered(table: str, extra_where: str = "", extra_params: tuple = ()) -> list[dict]:
        where = "run_id = %s"
        params: list = [run_id]
        if dataset_name:
            where += " AND dataset_name = %s"
            params.append(dataset_name)
        if extra_where:
            where += f" AND {extra_where}"
        params.extend(extra_params)
        return _fetch_rows(conn, f"SELECT * FROM dva.{table} WHERE {where}", tuple(params))

    return _filtered


def _print_summary(conn: psycopg.Connection, run_id: str, dataset_name: str | None) -> None:
    _filtered = _make_filtered(conn, run_id, dataset_name)
    _print_rows(
        "Count reconciliation",
        _filtered("count_results"),
        ["dataset_name", "source_count", "target_count", "difference", "pct_difference", "status"],
    )
    _print_rows(
        "Row hash summary",
        _filtered("hash_summary"),
        [
            "dataset_name",
            "matched_count",
            "missing_count",
            "extra_count",
            "mismatch_count",
            "status",
        ],
    )
    _print_rows(
        "Rule outcomes",
        _filtered("rule_results"),
        ["dataset_name", "rule_name", "rule_type", "status", "details"],
    )
    _print_rows(
        "Aggregate results",
        _filtered("aggregate_results"),
        [
            "dataset_name",
            "group_key",
            "column_name",
            "metric",
            "source_value",
            "target_value",
            "pct_difference",
            "status",
        ],
    )
    _print_rows(
        "Statistical results",
        _filtered("statistical_results"),
        [
            "dataset_name",
            "column_name",
            "metric",
            "source_value",
            "target_value",
            "pct_difference",
            "status",
        ],
    )
    _print_rows(
        "Schema contract checks",
        [r for r in _filtered("schema_results") if r["status"] != "PASS"],
        ["dataset_name", "check_name", "status", "details"],
    )
    _print_rows(
        "Duplicate keys",
        _filtered("duplicate_keys"),
        ["dataset_name", "side", "primary_key", "duplicate_count"],
    )
    _print_rows(
        "Data quality results",
        _filtered("dq_results"),
        ["dataset_name", "rule_name", "rule_type", "side", "failed_count", "severity", "status"],
    )


def _print_forensics(
    conn: psycopg.Connection,
    run_id: str,
    dataset_name: str | None,
    max_rows: int,
) -> None:
    _filtered = _make_filtered(conn, run_id, dataset_name)
    _print_rows(
        "Missing records (in source, not target)",
        _filtered("missing_records")[:max_rows],
        ["dataset_name", "primary_key", "record"],
    )
    _print_rows(
        "Extra records (in target, not source)",
        _filtered("extra_records")[:max_rows],
        ["dataset_name", "primary_key", "record"],
    )
    _print_rows(
        "Row hash mismatches",
        _filtered("hash_mismatches")[:max_rows],
        [
            "dataset_name",
            "primary_key",
            "source_hash",
            "target_hash",
            "source_record",
            "target_record",
        ],
    )
    _print_rows(
        "Validation issues",
        _filtered("validation_issues"),
        ["dataset_name", "rule_name", "issue_type", "severity", "failed_count", "sample_values"],
    )


def _print_detail(
    conn: psycopg.Connection,
    run_id: str,
    dataset_name: str | None,
    max_rows: int,
) -> None:
    _print_summary(conn, run_id, dataset_name)
    _print_forensics(conn, run_id, dataset_name, max_rows)


@app.command()
def results(
    project: str = typer.Option(..., "--project", help="Project name"),
    database_url: str = typer.Option(
        None, "--database-url", help="Postgres URL (defaults to DVA_DATABASE_URL env var)"
    ),
    failed_only: bool = typer.Option(False, "--failed-only", help="Only show FAIL/ERROR datasets"),
    summary: bool = typer.Option(
        False, "--summary", help="Show table-level detail (count, hash summary, aggregate, statistical)"
    ),
    forensics: bool = typer.Option(
        False, "--forensics", help="Show row-level samples (missing/extra/hash mismatches)"
    ),
    detail: bool = typer.Option(
        False,
        "--detail",
        help="Show full detail: table-level summary plus row-level forensics",
    ),
    dataset: str = typer.Option(
        None, "--dataset", help="Limit output to a single dataset name"
    ),
    max_rows: int = typer.Option(
        100, "--max-rows", help="Max rows per forensics table (default: 100)"
    ),
) -> None:
    """Show dataset-level results for the most recent run of a project, via Postgres."""
    url = get_database_url(database_url)
    try:
        with connect(url) as conn:
            latest = _fetch_rows(
                conn,
                """
                SELECT run_id FROM dva.run_summary
                WHERE project_name = %s
                ORDER BY start_time DESC
                LIMIT 1
                """,
                (project,),
            )
            if not latest:
                typer.echo(f"No runs found for project '{project}'")
                raise typer.Exit(code=1)
            run_id = latest[0]["run_id"]
            typer.echo(f"Latest run: {run_id}")

            status_filter = "AND status IN ('FAIL', 'ERROR')" if failed_only else ""
            rows = _fetch_rows(
                conn,
                f"""
                SELECT dataset_name, status, source_count, target_count,
                       missing_count, extra_count, mismatch_count
                FROM dva.dataset_summary
                WHERE run_id = %s {status_filter}
                ORDER BY dataset_name
                """,
                (run_id,),
            )
            columns = [
                "dataset_name",
                "status",
                "source_count",
                "target_count",
                "missing_count",
                "extra_count",
                "mismatch_count",
            ]
            for row in rows:
                typer.echo(" | ".join(f"{c}={row[c]}" for c in columns))

            if not (summary or forensics or detail):
                typer.echo(
                    "\nUse --summary for table-level drift, "
                    "--forensics for row samples (default max 100 rows)."
                )
            elif detail or (summary and forensics):
                _print_detail(conn, run_id, dataset, max_rows)
            elif summary:
                _print_summary(conn, run_id, dataset)
            elif forensics:
                _print_forensics(conn, run_id, dataset, max_rows)
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Failed to query results: {exc}")
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
