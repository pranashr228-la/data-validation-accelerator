from pathlib import Path

import duckdb

from dva.reporting.models import DatasetSummary, RunSummary
from dva.reporting.parquet_writer import write_models_to_parquet

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_report_models_round_trip_through_parquet(tmp_path):
    run_dir = tmp_path / "validation_runs" / "proj" / "run_id=r1"
    write_models_to_parquet(
        run_dir / "run_summary.parquet",
        [
            RunSummary(
                run_id="r1", project_name="proj", environment="dev",
                start_time="2026-01-01T00:00:00", end_time="2026-01-01T00:01:00",
                status="FAIL", dataset_count=1, passed_count=0, failed_count=1, error_count=0,
            )
        ],
    )
    write_models_to_parquet(
        run_dir / "dataset_summary.parquet",
        [
            DatasetSummary(
                run_id="r1", dataset_name="ds1", mapping_mode="table_to_table", status="FAIL",
                source_count=10, target_count=9, missing_count=1, extra_count=0, mismatch_count=0,
                start_time="2026-01-01T00:00:00", end_time="2026-01-01T00:01:00",
            )
        ],
    )

    con = duckdb.connect(":memory:")
    sql = (REPO_ROOT / "sql" / "duckdb" / "failed_datasets.sql").read_text()
    sql = sql.replace("validation_runs/", f"{(tmp_path / 'validation_runs').as_posix()}/")
    rows = con.execute(sql).fetchall()
    assert len(rows) == 1
    assert rows[0][1] == "ds1"


def test_all_duckdb_sql_pack_files_exist():
    expected = {
        "latest_run_summary.sql",
        "failed_datasets.sql",
        "failed_rules.sql",
        "aggregate_mismatches.sql",
        "hash_mismatches.sql",
        "validation_trends.sql",
    }
    actual = {p.name for p in (REPO_ROOT / "sql" / "duckdb").glob("*.sql")}
    assert expected.issubset(actual)
