"""Deterministic, pure-Python row normalization and hashing.

Row hashing normalizes column values in Python (rather than pushing hash
functions into each source engine's SQL dialect) so behaviour is identical
regardless of which database the value came from, and doesn't depend on
vendor extensions (e.g. Postgres' ``pgcrypto``) being installed.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from dva.config.models import HashDefaults


def _java_timestamp_format_to_strftime(java_fmt: str) -> str:
    """Convert a Java-style timestamp pattern to Python ``strftime`` format."""
    return (
        java_fmt.replace("yyyy", "%Y")
        .replace("MM", "%m")
        .replace("dd", "%d")
        .replace("HH", "%H")
        .replace("mm", "%M")
        .replace("ss", "%S")
    )


def _format_datetime(value: datetime, hash_defaults: HashDefaults) -> str:
    dt = value if value.tzinfo is not None else value.replace(tzinfo=ZoneInfo("UTC"))
    if hash_defaults.timestamp_timezone:
        dt = dt.astimezone(ZoneInfo(hash_defaults.timestamp_timezone))
    return dt.strftime(_java_timestamp_format_to_strftime(hash_defaults.timestamp_format))


def _format_date(value: date, hash_defaults: HashDefaults) -> str:
    fmt = _java_timestamp_format_to_strftime(hash_defaults.timestamp_format)
    date_fmt = fmt.split("%H")[0].rstrip(" :-") if "%H" in fmt else fmt
    return value.strftime(date_fmt)


def normalize_value(value: Any, hash_defaults: HashDefaults) -> str:
    """Render a single value to its normalized text form for hashing."""
    if value is None:
        return hash_defaults.null_token

    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (int,)):
        text = str(value)
    elif isinstance(value, (float, Decimal)):
        if isinstance(value, float) and math.isnan(value):
            return hash_defaults.null_token
        rounded = round(Decimal(str(value)), hash_defaults.decimal_scale)
        text = f"{rounded:.{hash_defaults.decimal_scale}f}"
    elif isinstance(value, datetime):
        text = _format_datetime(value, hash_defaults)
    elif isinstance(value, date):
        text = _format_date(value, hash_defaults)
    else:
        text = str(value)
        if hash_defaults.trim_strings:
            text = text.strip()
        if hash_defaults.empty_string_as_null and text == "":
            return hash_defaults.null_token
        if not hash_defaults.case_sensitive:
            text = text.upper()

    return text


def hash_row(values: list[Any], hash_defaults: HashDefaults) -> str:
    """Normalize and hash an ordered list of column values into one digest."""
    normalized = [normalize_value(v, hash_defaults) for v in values]
    joined = hash_defaults.delimiter.join(normalized)
    digest = hashlib.new(hash_defaults.algorithm)
    digest.update(joined.encode("utf-8"))
    return digest.hexdigest()
