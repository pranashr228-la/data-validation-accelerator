"""Stable issue fingerprinting.

The fingerprint identifies a recurring class of failure (same dataset,
rule, rule type, and issue type) across runs, so it deliberately excludes
the run id — that is what lets ``recurrence_count``/``first_seen_run_id``/
``last_seen_run_id`` track the same issue over time.
"""

from __future__ import annotations

import hashlib


def compute_fingerprint(
    *, dataset_name: str, rule_name: str, rule_type: str, issue_type: str
) -> str:
    key = "|".join([dataset_name, rule_name, rule_type, issue_type])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
