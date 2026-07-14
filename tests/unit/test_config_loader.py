import pytest

from dva.config.env import substitute_env_vars
from dva.config.loader import load_config
from dva.config.validator import ConfigValidationError, validate_config


def test_load_config_parses_example(tmp_path, monkeypatch):
    config = load_config("configs/examples/postgres_to_snowflake_table.yaml")
    assert config.project.name == "customer_migration"
    assert "source_postgres" in config.connections
    assert config.datasets[0].mapping_mode == "table_to_table"


def test_env_var_substitution(monkeypatch):
    monkeypatch.setenv("MY_VAR", "hello")
    assert substitute_env_vars("value: ${MY_VAR}") == "value: hello"


def test_env_var_substitution_missing_raises():
    with pytest.raises(KeyError):
        substitute_env_vars("value: ${TOTALLY_UNSET_VAR}")


def test_env_var_in_comment_is_not_substituted(tmp_path):
    config_text = """
project:
  name: t
connections:
  src:
    type: duckdb
    path: ":memory:"
datasets:
  - name: ds1
    mapping_mode: table_to_table
    source:
      connection: src
      object: t
    target:
      connection: src
      object: t
    primary_key: [id]
# a comment referencing ${NOT_SET_ANYWHERE}
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_text)
    config = load_config(str(config_file))
    assert config.project.name == "t"


def test_validate_config_requires_primary_key():
    config = load_config("configs/examples/postgres_to_snowflake_table.yaml")
    config.datasets[0].primary_key = []
    with pytest.raises(ConfigValidationError):
        validate_config(config)


def test_validate_config_checks_connection_reference():
    config = load_config("configs/examples/postgres_to_snowflake_table.yaml")
    config.datasets[0].source.connection = "does_not_exist"
    with pytest.raises(ConfigValidationError):
        validate_config(config)
