"""Runs the full validation plan for a single dataset."""

from __future__ import annotations

from dva.connectors.base import Connector
from dva.dialects.registry import get_dialect
from dva.engine.context import DatasetContext, RunContext
from dva.engine.execution_plan import VALIDATION_PLAN
from dva.normalization.sql_builder import build_base_sql
from dva.reporting.models import DatasetSummary
from dva.reporting.models import ExecutionLog
from dva.config.models import DatasetConfig
from dva.utils.time import to_iso, utcnow


def run_dataset(
    run: RunContext, dataset: DatasetConfig, connectors: dict[str, Connector]
) -> DatasetSummary:
    start = to_iso(utcnow())
    source_connector = connectors[dataset.source.connection]
    target_connector = connectors[dataset.target.connection]

    ctx = DatasetContext(
        run=run,
        dataset=dataset,
        source=source_connector,
        target=target_connector,
        source_dialect=get_dialect(source_connector.dialect_name),
        target_dialect=get_dialect(target_connector.dialect_name),
        source_base_sql=build_base_sql(dataset.source),
        target_base_sql=build_base_sql(dataset.target),
    )

    rule_count_before = len(run.report.rule_results)
    dataset_status = "PASS"
    try:
        for _name, validation_fn in VALIDATION_PLAN:
            validation_fn(ctx)
    except Exception as exc:  # noqa: BLE001 - captured as a dataset-level error
        dataset_status = "ERROR"
        if run.logger:
            run.logger.log(
                ExecutionLog(
                    run_id=run.run_id, timestamp=to_iso(utcnow()), level="ERROR",
                    dataset_name=dataset.name, message=f"Dataset run failed: {exc}",
                )
            )
        if run.config.execution.fail_fast:
            raise

    new_rule_results = run.report.rule_results[rule_count_before:]
    if dataset_status != "ERROR":
        statuses = {r.status for r in new_rule_results}
        if "FAIL" in statuses:
            dataset_status = "FAIL"
        elif "WARN" in statuses:
            dataset_status = "WARN"
        else:
            dataset_status = "PASS"

    count_result = next(
        (c for c in run.report.count_results if c.dataset_name == dataset.name), None
    )
    hash_summary = next(
        (h for h in run.report.hash_summaries if h.dataset_name == dataset.name), None
    )

    summary = DatasetSummary(
        run_id=run.run_id,
        dataset_name=dataset.name,
        mapping_mode=dataset.mapping_mode,
        status=dataset_status,
        source_count=count_result.source_count if count_result else None,
        target_count=count_result.target_count if count_result else None,
        missing_count=hash_summary.missing_count if hash_summary else None,
        extra_count=hash_summary.extra_count if hash_summary else None,
        mismatch_count=hash_summary.mismatch_count if hash_summary else None,
        start_time=start,
        end_time=to_iso(utcnow()),
    )
    run.report.dataset_summaries.append(summary)
    return summary
