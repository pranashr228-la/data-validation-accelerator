import duckdb

from dva.config.loader import load_config
from dva.config.validator import validate_config
from dva.engine.orchestrator import Orchestrator


def test_parquet_to_parquet_detects_missing_record(tmp_path):
    config = load_config("configs/examples/parquet_to_parquet.yaml")
    validate_config(config)

    orchestrator = Orchestrator(config, str(tmp_path))
    summary = orchestrator.run_validation()

    assert summary.status == "FAIL"

    run_dir = tmp_path / config.project.name / f"run_id={summary.run_id}"
    con = duckdb.connect(":memory:")
    missing = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{(run_dir / 'missing_records.parquet').as_posix()}')"
    ).fetchone()[0]
    assert missing == 1


def test_schema_contract_only_config_passes(tmp_path):
    config = load_config("configs/examples/schema_contract_customer.yaml")
    validate_config(config)

    orchestrator = Orchestrator(config, str(tmp_path))
    summary = orchestrator.run_validation()

    assert summary.status == "PASS"
