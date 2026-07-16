from pathlib import Path
from unittest.mock import patch

import psycopg
import pytest

from dva.config.models import (
    DatasetConfig,
    DatasetSide,
    DuckDBConnectionConfig,
    ExecutionConfig,
    ProjectConfig,
    RootConfig,
)
from dva.engine.orchestrator import Orchestrator

pytestmark = pytest.mark.usefixtures("postgres_db")


def test_fail_fast_on_exception_still_writes_reports(tmp_path):
    source_path = tmp_path / "source.duckdb"
    target_path = tmp_path / "target.duckdb"

    import duckdb

    con = duckdb.connect(str(source_path))
    con.execute("CREATE TABLE t AS SELECT 1 AS id, 'a' AS name")
    con.close()
    con = duckdb.connect(str(target_path))
    con.execute("CREATE TABLE t AS SELECT 1 AS id, 'a' AS name")
    con.close()

    dataset = DatasetConfig(
        name="ds",
        mapping_mode="table_to_table",
        source=DatasetSide(connection="src", object="t"),
        target=DatasetSide(connection="tgt", object="t"),
        primary_key=["id"],
        compare_columns=["name"],
    )
    config = RootConfig(
        project=ProjectConfig(name="p", output_path=str(tmp_path / "runs")),
        execution=ExecutionConfig(fail_fast=True),
        connections={
            "src": DuckDBConnectionConfig(path=str(source_path)),
            "tgt": DuckDBConnectionConfig(path=str(target_path)),
        },
        datasets=[dataset],
    )

    with patch(
        "dva.engine.dataset_runner.VALIDATION_PLAN",
        [("boom", lambda _ctx: (_ for _ in ()).throw(RuntimeError("boom")))],
    ):
        orchestrator = Orchestrator(config)
        summary = orchestrator.run_validation()

    assert summary.status == "ERROR"
    run_dir = Path(tmp_path) / "runs" / "p" / f"run_id={summary.run_id}"
    assert (run_dir / "manifest.json").exists()

    with psycopg.connect(orchestrator.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM dva.run_summary WHERE run_id = %s",
                (summary.run_id,),
            )
            assert cur.fetchone()[0] == 1
            cur.execute(
                "SELECT COUNT(*) FROM dva.dataset_summary WHERE run_id = %s",
                (summary.run_id,),
            )
            assert cur.fetchone()[0] == 1
