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

from dva.config.models import HashDefaults


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
        text = value.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(value, date):
        text = value.strftime("%Y-%m-%d 00:00:00")
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
