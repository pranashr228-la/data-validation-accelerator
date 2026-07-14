"""Schema contract validation (section 9 of the MVP plan).

This is a *contract* check, not "source schema == target schema": primary
key and compare columns must exist on both sides, extra/unmapped target
columns and cross-family type differences only produce warnings.
"""

from __future__ import annotations

from dva.engine.context import DatasetContext
from dva.reporting.models import SchemaResult
from dva.validations.base import now_iso, record_issue, record_rule_result

_TYPE_FAMILIES = {
    "numeric": ("int", "float", "double", "decimal", "numeric", "real"),
    "string": ("varchar", "char", "text", "string"),
    "temporal": ("date", "time", "timestamp"),
    "boolean": ("bool",),
}


def _type_family(type_name: str) -> str:
    lowered = type_name.lower()
    for family, markers in _TYPE_FAMILIES.items():
        if any(marker in lowered for marker in markers):
            return family
    return "other"


def _lower_keys(schema: dict[str, str]) -> dict[str, str]:
    """Fold schema column names to lowercase for case-insensitive comparison.

    Postgres folds unquoted identifiers to lowercase and Snowflake folds
    them to uppercase by default, so a contract check between the two must
    compare names case-insensitively rather than treating a casing
    difference as a missing column.
    """
    return {name.lower(): type_ for name, type_ in schema.items()}


def _add_check(ctx: DatasetContext, run_id: str, check_name: str, status: str, details: str) -> None:
    ctx.run.report.schema_results.append(
        SchemaResult(
            run_id=run_id,
            dataset_name=ctx.dataset.name,
            check_name=check_name,
            status=status,
            details=details,
        )
    )


def run_schema_contract(ctx: DatasetContext) -> None:
    config = ctx.dataset.validations.schema_contract
    if not config.enabled:
        return

    start = now_iso()
    run_id = ctx.run.run_id
    overall_status = "PASS"

    try:
        source_schema = ctx.source.get_schema(ctx.source_base_sql)
        _add_check(ctx, run_id, "source_exists", "PASS", "Source query/object resolved")
    except Exception as exc:  # noqa: BLE001 - surfaced as a schema check failure
        _add_check(ctx, run_id, "source_exists", "FAIL", str(exc))
        record_rule_result(
            ctx, rule_name="schema_contract", rule_type="schema_contract", status="FAIL",
            details=f"source object/query could not be resolved: {exc}", start_iso=start,
        )
        record_issue(
            ctx, rule_name="schema_contract", rule_type="schema_contract",
            issue_type="source_object_missing", severity="HIGH", failed_count=1,
        )
        return

    try:
        target_schema = ctx.target.get_schema(ctx.target_base_sql)
        _add_check(ctx, run_id, "target_exists", "PASS", "Target query/object resolved")
    except Exception as exc:  # noqa: BLE001
        _add_check(ctx, run_id, "target_exists", "FAIL", str(exc))
        record_rule_result(
            ctx, rule_name="schema_contract", rule_type="schema_contract", status="FAIL",
            details=f"target object/query could not be resolved: {exc}", start_iso=start,
        )
        record_issue(
            ctx, rule_name="schema_contract", rule_type="schema_contract",
            issue_type="target_object_missing", severity="HIGH", failed_count=1,
        )
        return

    source_schema_ci = _lower_keys(source_schema)
    target_schema_ci = _lower_keys(target_schema)

    def _columns_exist(columns: list[str], schema: dict[str, str], side: str, check: str) -> bool:
        nonlocal overall_status
        missing = [c for c in columns if c.lower() not in schema]
        if missing:
            overall_status = "FAIL"
            _add_check(ctx, run_id, check, "FAIL", f"Missing on {side}: {missing}")
            record_issue(
                ctx, rule_name="schema_contract", rule_type="schema_contract",
                issue_type=check, severity="HIGH", failed_count=len(missing),
                sample_values=missing,
            )
            return False
        _add_check(ctx, run_id, check, "PASS", f"All present on {side}")
        return True

    _columns_exist(ctx.dataset.primary_key, source_schema_ci, "source", "primary_key_in_source")
    _columns_exist(ctx.dataset.primary_key, target_schema_ci, "target", "primary_key_in_target")
    _columns_exist(
        ctx.dataset.compare_columns, source_schema_ci, "source", "compare_columns_in_source"
    )
    _columns_exist(
        ctx.dataset.compare_columns, target_schema_ci, "target", "compare_columns_in_target"
    )

    # Data type compatibility (warn on cross-family mismatch only)
    mismatches = []
    for col in ctx.dataset.compare_columns:
        key = col.lower()
        if key in source_schema_ci and key in target_schema_ci:
            if _type_family(source_schema_ci[key]) != _type_family(target_schema_ci[key]):
                mismatches.append(f"{col}: {source_schema_ci[key]} vs {target_schema_ci[key]}")
    if mismatches:
        if overall_status == "PASS":
            overall_status = "WARN"
        _add_check(ctx, run_id, "data_type_compatibility", "WARN", "; ".join(mismatches))
    else:
        _add_check(ctx, run_id, "data_type_compatibility", "PASS", "No incompatible type families")

    # Extra/unmapped target columns
    expected = {c.lower() for c in ctx.dataset.primary_key} | {
        c.lower() for c in ctx.dataset.compare_columns
    }
    unmapped_handled = {u.column.lower() for u in config.target_unmapped_columns}
    extra = [c for c in target_schema if c.lower() not in expected and c.lower() not in unmapped_handled]
    if extra:
        if overall_status == "PASS":
            overall_status = "WARN"
        _add_check(ctx, run_id, "extra_columns", "WARN", f"Unmapped target columns: {extra}")
    else:
        _add_check(ctx, run_id, "extra_columns", "PASS", "No unexpected extra target columns")

    record_rule_result(
        ctx, rule_name="schema_contract", rule_type="schema_contract",
        status=overall_status, details="See schema_results.parquet for check details",
        start_iso=start,
    )
