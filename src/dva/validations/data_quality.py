"""Basic data quality rules (section 10.7). Runs against both source and target."""

from __future__ import annotations

from dva.config.models import DataQualityRule
from dva.connectors.base import Connector
from dva.dialects.base import SQLDialect
from dva.engine.context import DatasetContext
from dva.reporting.models import DataQualityResult
from dva.validations.base import now_iso, record_issue, record_rule_result


def _rule_sql(rule: DataQualityRule, base_sql: str, dialect: SQLDialect) -> str:
    if rule.type == "custom_sql":
        assert rule.sql is not None
        return rule.sql.strip().rstrip(";")

    assert rule.column is not None, f"rule '{rule.name}' requires 'column'"
    col = dialect.quote_ident(rule.column)

    if rule.type == "not_null":
        predicate = f"{col} IS NULL"
    elif rule.type == "duplicate":
        return (
            f"SELECT COUNT(*) AS failed_count FROM (\n{base_sql}\n) q\n"
            f"WHERE {col} IN (\n"
            f"  SELECT {col} FROM (\n{base_sql}\n) q2 GROUP BY {col} HAVING COUNT(*) > 1\n"
            f")"
        )
    elif rule.type == "allowed_values":
        allowed = rule.values or []
        if not allowed:
            raise ValueError(f"rule '{rule.name}' requires at least one allowed value")
        values = ", ".join(f"'{v.replace("'", "''")}'" for v in allowed)
        predicate = f"{col} NOT IN ({values}) AND {col} IS NOT NULL"
    elif rule.type == "range":
        conditions = []
        if rule.min is not None:
            conditions.append(f"{col} < {rule.min}")
        if rule.max is not None:
            conditions.append(f"{col} > {rule.max}")
        predicate = " OR ".join(conditions) if conditions else "1 = 0"
    elif rule.type == "regex":
        assert rule.pattern is not None
        predicate = f"{dialect.not_regex_predicate(col, rule.pattern)} AND {col} IS NOT NULL"
    elif rule.type == "length":
        conditions = []
        if rule.length_min is not None:
            conditions.append(f"LENGTH({col}) < {rule.length_min}")
        if rule.length_max is not None:
            conditions.append(f"LENGTH({col}) > {rule.length_max}")
        predicate = " OR ".join(conditions) if conditions else "1 = 0"
    else:
        raise ValueError(f"Unsupported data quality rule type: {rule.type}")

    return f"SELECT COUNT(*) AS failed_count FROM (\n{base_sql}\n) q WHERE {predicate}"


def _run_side(
    ctx: DatasetContext,
    side: str,
    connector: Connector,
    dialect: SQLDialect,
    base_sql: str,
) -> str:
    config = ctx.dataset.validations.data_quality
    overall_status = "PASS"
    for rule in config.rules:
        sql = _rule_sql(rule, base_sql, dialect)
        ctx.run.write_generated_sql(ctx.dataset.name, f"dq_{rule.name}_{side}", sql)
        failed_count = int(connector.fetch_scalar(sql) or 0)
        status = "FAIL" if failed_count > 0 else "PASS"
        if status == "FAIL" and overall_status == "PASS":
            overall_status = "FAIL"
        ctx.run.report.dq_results.append(
            DataQualityResult(
                run_id=ctx.run.run_id,
                dataset_name=ctx.dataset.name,
                rule_name=rule.name,
                rule_type=rule.type,
                side=side,  # type: ignore[arg-type]
                status=status,
                failed_count=failed_count,
                severity=rule.severity,
            )
        )
        if status == "FAIL":
            record_issue(
                ctx, rule_name=rule.name, rule_type="data_quality",
                issue_type=f"{rule.type}_{side}", severity=rule.severity,
                failed_count=failed_count,
            )
    return overall_status


def run_data_quality(ctx: DatasetContext) -> None:
    config = ctx.dataset.validations.data_quality
    if not config.enabled:
        return

    start = now_iso()
    source_status = _run_side(ctx, "source", ctx.source, ctx.source_dialect, ctx.source_base_sql)
    target_status = _run_side(ctx, "target", ctx.target, ctx.target_dialect, ctx.target_base_sql)
    overall_status = "FAIL" if "FAIL" in (source_status, target_status) else "PASS"

    record_rule_result(
        ctx, rule_name="data_quality", rule_type="data_quality", status=overall_status,
        details="See dq_results.parquet for per-rule detail", start_iso=start,
    )
