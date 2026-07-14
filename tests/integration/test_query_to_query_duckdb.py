from dva.config.loader import load_config
from dva.config.validator import validate_config
from dva.engine.orchestrator import Orchestrator


def test_fact_order_query_to_query_join_and_detects_mismatch(tmp_path):
    config = load_config("configs/examples/query_to_query_fact_order.yaml")
    validate_config(config)

    orchestrator = Orchestrator(config, str(tmp_path))
    summary = orchestrator.run_validation()

    assert summary.status == "FAIL"

    run_dir = tmp_path / config.project.name / f"run_id={summary.run_id}"
    assert (run_dir / "hash_mismatches.parquet").exists()
    assert (run_dir / "missing_records.parquet").exists()
