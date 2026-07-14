"""Minimal structured logging built on the stdlib logging module.

The MVP avoids a dedicated structured-logging dependency: log records are
plain dicts serialised as JSON lines by ``dva.reporting.jsonl_logger``. This
module just gives call sites a consistent logger to write through.
"""

from __future__ import annotations

import logging

_LOGGER_NAME = "dva"


def get_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
