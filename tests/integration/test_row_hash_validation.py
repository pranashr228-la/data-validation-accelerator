import psycopg

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

    with psycopg.connect(orchestrator.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT missing_count, extra_count, mismatch_count
                FROM dva.hash_summary
                WHERE run_id = %s
                """,
                (summary.run_id,),
            )
            hash_summary = cur.fetchone()
            assert hash_summary[0] == 2  # missing_count
            assert hash_summary[1] == 1  # extra_count
            assert hash_summary[2] == 1  # mismatch_count

            cur.execute(
                "SELECT COUNT(*) FROM dva.duplicate_keys WHERE run_id = %s",
                (summary.run_id,),
            )
            assert cur.fetchone()[0] == 1

    for artifact in ("manifest.json", "execution_logs.jsonl"):
        assert (run_dir / artifact).exists(), f"missing {artifact}"
