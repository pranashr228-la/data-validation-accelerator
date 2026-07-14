"""Environment variable substitution for YAML config text.

Supports ``${VAR_NAME}`` placeholders, resolved from the process environment
after loading a ``.env`` file (if present) via ``python-dotenv``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

_dotenv_loaded = False


def load_dotenv_once(dotenv_path: str | None = None) -> None:
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    candidate = Path(dotenv_path) if dotenv_path else Path(".env")
    if candidate.exists():
        load_dotenv(dotenv_path=candidate)
    _dotenv_loaded = True


def substitute_env_vars(text: str) -> str:
    """Replace ``${VAR}`` placeholders with values from the environment.

    Raises ``KeyError`` if a referenced variable is not set, so missing
    credentials fail fast at config-load time rather than at query time.
    """

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in os.environ:
            raise KeyError(f"Environment variable '{name}' referenced in config is not set")
        return os.environ[name]

    return _VAR_PATTERN.sub(_replace, text)
