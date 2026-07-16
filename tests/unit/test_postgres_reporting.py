import psycopg
import pytest

from dva.reporting.models import DatasetSummary, RunSummary
from dva.reporting.writer import ReportCollector

pytestmark = pytest.mark.usefixtures("postgres_db")


def test_report_models_round_trip_through_postgres(database_url: str):
    collector = ReportCollector()
    collector.run_summaries.append(
        RunSummary(
            run_id="r1",
            project_name="proj",
            environment="dev",
            start_time="2026-01-01T00:00:00+00:00",
            end_time="2026-01-01T00:01:00+00:00",
            status="FAIL",
            dataset_count=1,
            passed_count=0,
            failed_count=1,
            error_count=0,
        )
    )
    collector.dataset_summaries.append(
        DatasetSummary(
            run_id="r1",
            dataset_name="ds1",
            mapping_mode="table_to_table",
            status="FAIL",
            source_count=10,
            target_count=9,
            missing_count=1,
            extra_count=0,
            mismatch_count=0,
            start_time="2026-01-01T00:00:00+00:00",
            end_time="2026-01-01T00:01:00+00:00",
        )
    )

    with psycopg.connect(database_url) as conn:
        collector.write_all(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ds.dataset_name
                FROM dva.dataset_summary ds
                JOIN dva.run_summary rs ON ds.run_id = rs.run_id
                WHERE ds.status IN ('FAIL', 'ERROR')
                """
            )
            rows = cur.fetchall()

    assert len(rows) == 1
    assert rows[0][0] == "ds1"


def test_all_postgres_view_files_exist():
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    expected = {
        "001_schema.sql",
        "002_views.sql",
    }
    actual = {p.name for p in (repo_root / "sql" / "postgres").glob("*.sql")}
    assert expected.issubset(actual)
