import duckdb

from dva.config.loader import load_config
from dva.config.validator import validate_config
from dva.engine.orchestrator import Orchestrator


def test_customer_table_validation_detects_seeded_discrepancies(tmp_path):
    config = load_config("configs/examples/postgres_to_snowflake_table.yaml")
    validate_config(config)

    orchestrator = Orchestrator(config, str(tmp_path))
    summary = orchestrator.run_validation()

    assert summary.status == "FAIL"
    assert summary.dataset_count == 1
    assert summary.failed_count == 1

    run_dir = tmp_path / config.project.name / f"run_id={summary.run_id}"
    con = duckdb.connect(":memory:")

    hash_summary = con.execute(
        f"SELECT * FROM read_parquet('{(run_dir / 'hash_summary.parquet').as_posix()}')"
    ).fetchone()
    # run_id, dataset_name, source_row_count, target_row_count, matched_count,
    # missing_count, extra_count, mismatch_count, status
    assert hash_summary[5] == 2  # missing_count
    assert hash_summary[6] == 1  # extra_count
    assert hash_summary[7] == 1  # mismatch_count

    duplicate_keys = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{(run_dir / 'duplicate_keys.parquet').as_posix()}')"
    ).fetchone()[0]
    assert duplicate_keys == 1

    for artifact in (
        "manifest.json",
        "execution_logs.jsonl",
        "run_summary.parquet",
        "dataset_summary.parquet",
        "rule_results.parquet",
        "validation_issues.parquet",
    ):
        assert (run_dir / artifact).exists(), f"missing {artifact}"
