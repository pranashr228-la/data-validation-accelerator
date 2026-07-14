"""ValidationIssue model — the actionable defect record for failed rules."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

IssueStatus = Literal["OPEN", "RESOLVED"]
WaiverStatus = Literal["NONE", "WAIVED"]


class ValidationIssue(BaseModel):
    issue_fingerprint: str
    run_id: str
    dataset_name: str
    rule_name: str
    rule_type: str
    issue_type: str
    severity: str
    status: IssueStatus = "OPEN"
    failed_count: int
    sample_values: str = "[]"
    first_seen_run_id: str
    last_seen_run_id: str
    recurrence_count: int = 1
    external_ticket_id: str | None = None
    waiver_status: WaiverStatus = "NONE"
    waiver_reason: str | None = None
