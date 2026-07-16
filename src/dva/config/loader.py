"""YAML config loading: read file, substitute env vars, parse into models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from dva.config.defaults import apply_defaults
from dva.config.env import load_dotenv_once, substitute_env_vars
from dva.config.models import RootConfig


def _substitute_recursive(node: Any) -> Any:
    """Apply ``${VAR}`` substitution to string leaves of a parsed YAML tree.

    Substituting after parsing (rather than on the raw file text) means
    ``#`` comments containing ``${...}`` placeholders are never evaluated.
    """
    if isinstance(node, str):
        return substitute_env_vars(node)
    if isinstance(node, dict):
        return {key: _substitute_recursive(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_substitute_recursive(item) for item in node]
    return node


def load_config(path: str) -> RootConfig:
    """Load, substitute, parse, and validate a YAML validation project file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    load_dotenv_once()
    data = yaml.safe_load(config_path.read_text()) or {}
    substituted = _substitute_recursive(data)
    config = RootConfig.model_validate(substituted)
    return apply_defaults(config)
