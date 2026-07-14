"""ID generation helpers."""

from __future__ import annotations

import datetime as _dt
import uuid


def short_uuid(length: int = 6) -> str:
    """Return a short lowercase hex fragment of a UUID4."""
    return uuid.uuid4().hex[:length]


def generate_run_id(now: _dt.datetime) -> str:
    """Build a run id in the form YYYYMMDD_HHMMSS_<short_uuid>."""
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{short_uuid()}"
