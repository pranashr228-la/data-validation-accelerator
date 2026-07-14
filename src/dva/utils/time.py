"""Time helpers."""

from __future__ import annotations

import datetime as _dt


def utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def to_iso(value: _dt.datetime) -> str:
    return value.isoformat()
