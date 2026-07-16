import psycopg

from dva.config.loader import load_config
from dva.config.validator import validate_config
from dva.engine.orchestrator import Orchestrator


def test_parquet_to_parquet_detects_missing_record(tmp_path):
    config = load_config("configs/examples/parquet_to_parquet.yaml")
    validate_config(config)

    orchestrator = Orchestrator(config, str(tmp_path))
    summary = orchestrator.run_validation()

    assert summary.status == "FAIL"

    with psycopg.connect(orchestrator.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM dva.missing_records WHERE run_id = %s",
                (summary.run_id,),
            )
            missing = cur.fetchone()[0]
    assert missing == 1


def test_schema_contract_only_config_passes(tmp_path):
    config = load_config("configs/examples/schema_contract_customer.yaml")
    validate_config(config)

    orchestrator = Orchestrator(config, str(tmp_path))
    summary = orchestrator.run_validation()

    assert summary.status == "PASS"

    with psycopg.connect(orchestrator.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM dva.run_summary WHERE run_id = %s",
                (summary.run_id,),
            )
            assert cur.fetchone()[0] == 1
