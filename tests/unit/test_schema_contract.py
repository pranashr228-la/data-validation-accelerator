from pathlib import Path

from dva.config.models import (
    DatasetConfig,
    DatasetSide,
    DuckDBConnectionConfig,
    RootConfig,
    ProjectConfig,
    SchemaContractConfig,
    ValidationsConfig,
)
from dva.connectors.registry import create_connector
from dva.dialects.registry import get_dialect
from dva.engine.context import DatasetContext, RunContext
from dva.normalization.sql_builder import build_base_sql
from dva.validations.schema_contract import run_schema_contract


def _build_ctx(tmp_path, source_sql_setup, target_sql_setup, primary_key, compare_columns):
    source = create_connector(DuckDBConnectionConfig(path=":memory:"))
    target = create_connector(DuckDBConnectionConfig(path=":memory:"))
    source.connect()
    target.connect()
    source.execute(source_sql_setup)
    target.execute(target_sql_setup)

    dataset = DatasetConfig(
        name="ds",
        mapping_mode="table_to_table",
        source=DatasetSide(connection="src", object="t"),
        target=DatasetSide(connection="tgt", object="t"),
        primary_key=primary_key,
        compare_columns=compare_columns,
        validations=ValidationsConfig(schema_contract=SchemaContractConfig(enabled=True)),
    )
    config = RootConfig(
        project=ProjectConfig(name="p", output_path=str(tmp_path)),
        connections={"src": DuckDBConnectionConfig(path=":memory:"), "tgt": DuckDBConnectionConfig(path=":memory:")},
        datasets=[dataset],
    )
    run = RunContext(run_id="r1", config=config, run_dir=Path(tmp_path))
    ctx = DatasetContext(
        run=run,
        dataset=dataset,
        source=source,
        target=target,
        source_dialect=get_dialect("duckdb"),
        target_dialect=get_dialect("duckdb"),
        source_base_sql=build_base_sql(dataset.source),
        target_base_sql=build_base_sql(dataset.target),
    )
    return ctx, source, target


def test_schema_contract_passes_when_columns_present(tmp_path):
    ctx, source, target = _build_ctx(
        tmp_path,
        "CREATE TABLE t AS SELECT 1 AS id, 'a' AS name",
        "CREATE TABLE t AS SELECT 1 AS id, 'a' AS name",
        primary_key=["id"],
        compare_columns=["name"],
    )
    run_schema_contract(ctx)
    result = ctx.run.report.rule_results[-1]
    assert result.status == "PASS"
    source.close()
    target.close()


def test_schema_contract_fails_when_primary_key_missing_on_target(tmp_path):
    ctx, source, target = _build_ctx(
        tmp_path,
        "CREATE TABLE t AS SELECT 1 AS id, 'a' AS name",
        "CREATE TABLE t AS SELECT 'a' AS name",
        primary_key=["id"],
        compare_columns=["name"],
    )
    run_schema_contract(ctx)
    result = ctx.run.report.rule_results[-1]
    assert result.status == "FAIL"
    assert any(i.issue_type == "primary_key_in_target" for i in ctx.run.report.validation_issues)
    source.close()
    target.close()


def test_schema_contract_case_insensitive_column_match(tmp_path):
    ctx, source, target = _build_ctx(
        tmp_path,
        "CREATE TABLE t AS SELECT 1 AS id, 'a' AS name",
        "CREATE TABLE t AS SELECT 1 AS ID, 'a' AS NAME",
        primary_key=["id"],
        compare_columns=["name"],
    )
    run_schema_contract(ctx)
    result = ctx.run.report.rule_results[-1]
    assert result.status == "PASS"
    source.close()
    target.close()


def test_schema_contract_warns_on_extra_target_columns(tmp_path):
    ctx, source, target = _build_ctx(
        tmp_path,
        "CREATE TABLE t AS SELECT 1 AS id, 'a' AS name",
        "CREATE TABLE t AS SELECT 1 AS id, 'a' AS name, 'x' AS extra_col",
        primary_key=["id"],
        compare_columns=["name"],
    )
    run_schema_contract(ctx)
    result = ctx.run.report.rule_results[-1]
    assert result.status == "WARN"
    source.close()
    target.close()


def test_schema_contract_mapping_based_checks_required_and_expected_columns(tmp_path):
    ctx, source, target = _build_ctx(
        tmp_path,
        "CREATE TABLE t AS SELECT 1 AS id, 'a' AS first_name, 'b' AS last_name",
        "CREATE TABLE t AS SELECT 1 AS id, 'a' AS customer_name",
        primary_key=["id"],
        compare_columns=["first_name"],
    )
    ctx.dataset.validations.schema_contract.mode = "mapping_based"
    ctx.dataset.validations.schema_contract.source_required_columns = [
        "id",
        "first_name",
        "last_name",
        "email",
    ]
    ctx.dataset.validations.schema_contract.target_expected_columns = [
        "id",
        "customer_name",
        "balance",
    ]
    run_schema_contract(ctx)
    result = ctx.run.report.rule_results[-1]
    assert result.status == "FAIL"
    issue_types = {i.issue_type for i in ctx.run.report.validation_issues}
    assert "source_required_columns" in issue_types
    assert "target_expected_columns" in issue_types
    source.close()
    target.close()
