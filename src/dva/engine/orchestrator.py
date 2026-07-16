"""Top-level orchestrator: opens connections, runs each dataset, writes reports."""

from __future__ import annotations

from dva.config.models import RootConfig
from dva.connectors.base import Connector
from dva.connectors.registry import create_connector
from dva.engine.context import RunContext
from dva.engine.dataset_runner import run_dataset
from dva.engine.run_scope import RunScope
from dva.reporting.database import apply_schema, connect, get_database_url
from dva.reporting.jsonl_logger import JsonlLogger
from dva.reporting.manifest import write_manifest
from dva.reporting.models import ExecutionLog, RunSummary
from dva.utils.ids import generate_run_id
from dva.utils.paths import ensure_dir
from dva.utils.paths import run_dir as build_run_dir
from dva.utils.time import to_iso, utcnow


class Orchestrator:
    def __init__(
        self,
        config: RootConfig,
        output_path: str | None = None,
        scope: RunScope | None = None,
    ) -> None:
        self.config = config
        self.output_path = output_path or config.project.output_path
        self.database_url = get_database_url(config.project.results_database_url)
        self.scope = scope or RunScope()

    def run_validation(self) -> RunSummary:
        run_id = generate_run_id(utcnow())
        run_directory = ensure_dir(
            build_run_dir(self.output_path, self.config.project.name, run_id)
        )
        run = RunContext(
            run_id=run_id, config=self.config, run_dir=run_directory, scope=self.scope
        )
        run.logger = JsonlLogger(run_directory, run.report)
        start = to_iso(utcnow())

        connectors: dict[str, Connector] = {
            name: create_connector(conn_cfg) for name, conn_cfg in self.config.connections.items()
        }
        for connector in connectors.values():
            connector.connect()

        try:
            for dataset in self.config.datasets:
                if not run.scope.includes_dataset(dataset.name):
                    continue
                run.logger.log(
                    ExecutionLog(
                        run_id=run_id, timestamp=to_iso(utcnow()), level="INFO",
                        dataset_name=dataset.name, message=f"Starting dataset '{dataset.name}'",
                    )
                )
                summary = run_dataset(run, dataset, connectors)
                run.logger.log(
                    ExecutionLog(
                        run_id=run_id, timestamp=to_iso(utcnow()), level="INFO",
                        dataset_name=dataset.name,
                        message=f"Finished dataset '{dataset.name}' with status {summary.status}",
                    )
                )
                if self.config.execution.fail_fast and summary.status in ("FAIL", "ERROR"):
                    break
        finally:
            for connector in connectors.values():
                connector.close()
            run.scratch_duckdb.close()

        statuses = {d.status for d in run.report.dataset_summaries}
        if "ERROR" in statuses:
            overall_status = "ERROR"
        elif "FAIL" in statuses:
            overall_status = "FAIL"
        elif "WARN" in statuses:
            overall_status = "WARN"
        else:
            overall_status = "PASS"

        run_summary = RunSummary(
            run_id=run_id,
            project_name=self.config.project.name,
            environment=self.config.project.environment,
            start_time=start,
            end_time=to_iso(utcnow()),
            status=overall_status,
            dataset_count=len(run.report.dataset_summaries),
            passed_count=sum(1 for d in run.report.dataset_summaries if d.status == "PASS"),
            failed_count=sum(1 for d in run.report.dataset_summaries if d.status == "FAIL"),
            error_count=sum(1 for d in run.report.dataset_summaries if d.status == "ERROR"),
        )
        run.report.run_summaries.append(run_summary)

        with connect(self.database_url) as conn:
            apply_schema(conn)
            run.report.write_all(conn)

        write_manifest(
            run_directory,
            {
                "run_id": run_id,
                "project_name": self.config.project.name,
                "environment": self.config.project.environment,
                "status": overall_status,
                "start_time": start,
                "end_time": run_summary.end_time,
                "dataset_count": run_summary.dataset_count,
                "datasets": [d.name for d in self.config.datasets],
                "results_database_url": self.database_url,
                "output_files": [
                    "manifest.json",
                    "execution_logs.jsonl",
                ],
            },
        )
        return run_summary
