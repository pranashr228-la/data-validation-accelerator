import psycopg

from dva.config.loader import load_config
from dva.config.validator import validate_config
from dva.engine.orchestrator import Orchestrator


def test_fact_order_query_to_query_join_and_detects_mismatch(tmp_path):
    config = load_config("configs/examples/query_to_query_fact_order.yaml")
    validate_config(config)

    orchestrator = Orchestrator(config, str(tmp_path))
    summary = orchestrator.run_validation()

    assert summary.status == "FAIL"

    with psycopg.connect(orchestrator.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM dva.hash_mismatches WHERE run_id = %s",
                (summary.run_id,),
            )
            assert cur.fetchone()[0] >= 1
            cur.execute(
                "SELECT COUNT(*) FROM dva.missing_records WHERE run_id = %s",
                (summary.run_id,),
            )
            assert cur.fetchone()[0] >= 1
