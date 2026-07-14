"""Pydantic models for every parquet report entity the MVP writes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Status = Literal["PASS", "WARN", "FAIL", "ERROR"]


class RunSummary(BaseModel):
    run_id: str
    project_name: str
    environment: str
    start_time: str
    end_time: str
    status: Status
    dataset_count: int
    passed_count: int
    failed_count: int
    error_count: int


class DatasetSummary(BaseModel):
    run_id: str
    dataset_name: str
    mapping_mode: str
    status: Status
    source_count: int | None = None
    target_count: int | None = None
    missing_count: int | None = None
    extra_count: int | None = None
    mismatch_count: int | None = None
    start_time: str
    end_time: str


class RuleResult(BaseModel):
    run_id: str
    dataset_name: str
    rule_name: str
    rule_type: str
    status: Status
    details: str = ""
    start_time: str
    end_time: str


class SchemaResult(BaseModel):
    run_id: str
    dataset_name: str
    check_name: str
    status: Status
    details: str = ""


class CountResult(BaseModel):
    run_id: str
    dataset_name: str
    source_count: int
    target_count: int
    difference: int
    pct_difference: float
    status: Status


class AggregateResult(BaseModel):
    run_id: str
    dataset_name: str
    group_key: str
    column: str
    metric: str
    source_value: float | None
    target_value: float | None
    difference: float | None
    pct_difference: float | None
    status: Status


class StatisticalResult(BaseModel):
    run_id: str
    dataset_name: str
    column: str
    metric: str
    source_value: float | None
    target_value: float | None
    difference: float | None
    pct_difference: float | None
    status: Status


class HashSummary(BaseModel):
    run_id: str
    dataset_name: str
    source_row_count: int
    target_row_count: int
    matched_count: int
    missing_count: int
    extra_count: int
    mismatch_count: int
    status: Status


class HashMismatch(BaseModel):
    run_id: str
    dataset_name: str
    primary_key: str
    source_hash: str
    target_hash: str
    source_record: str | None = None
    target_record: str | None = None


class MissingRecord(BaseModel):
    run_id: str
    dataset_name: str
    primary_key: str
    record: str


class ExtraRecord(BaseModel):
    run_id: str
    dataset_name: str
    primary_key: str
    record: str


class DuplicateKey(BaseModel):
    run_id: str
    dataset_name: str
    side: Literal["source", "target"]
    primary_key: str
    duplicate_count: int


class DataQualityResult(BaseModel):
    run_id: str
    dataset_name: str
    rule_name: str
    rule_type: str
    side: Literal["source", "target"]
    status: Status
    failed_count: int
    severity: str


class ExecutionLog(BaseModel):
    run_id: str
    timestamp: str
    level: str
    dataset_name: str | None
    message: str
