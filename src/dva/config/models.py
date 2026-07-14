"""Pydantic models for the MVP validation project configuration.

Mirrors the YAML structure described in the MVP plan: project / execution /
connections / defaults / datasets. Only the two MVP mapping modes
(``table_to_table`` and ``query_to_query``) are supported — ``mapping_config``
is explicitly out of scope for the MVP.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

# --------------------------------------------------------------------------
# Project / execution
# --------------------------------------------------------------------------


class ProjectConfig(BaseModel):
    name: str
    environment: str = "dev"
    output_path: str = "./validation_runs"


class ExecutionConfig(BaseModel):
    mode: Literal["local", "docker"] = "local"
    max_parallel_datasets: int = 1
    max_parallel_partitions: int = 1
    fail_fast: bool = False
    write_generated_sql: bool = True


# --------------------------------------------------------------------------
# Connections
# --------------------------------------------------------------------------


class PostgresConnectionConfig(BaseModel):
    type: Literal["postgres"] = "postgres"
    host: str
    port: int = 5432
    database: str
    schema_name: str = Field(default="public", alias="schema")
    username: str
    password: str

    model_config = {"populate_by_name": True}


class SnowflakeConnectionConfig(BaseModel):
    type: Literal["snowflake"] = "snowflake"
    account: str
    warehouse: str
    database: str
    schema_name: str = Field(alias="schema")
    username: str
    password: str
    role: str | None = None

    model_config = {"populate_by_name": True}


class DuckDBConnectionConfig(BaseModel):
    """Local DuckDB file or in-memory database.

    Used both for report analysis and, in the MVP, as a stand-in connector
    when a real warehouse (e.g. Snowflake) is not reachable — the same SQL
    generated for ``postgres``/``snowflake`` dialects can be pointed at a
    DuckDB-backed dataset for local development and demos.
    """

    type: Literal["duckdb"] = "duckdb"
    path: str = ":memory:"


class ParquetConnectionConfig(BaseModel):
    type: Literal["parquet"] = "parquet"
    base_path: str = "."


class DatabricksConnectionConfig(BaseModel):
    type: Literal["databricks"] = "databricks"
    server_hostname: str
    http_path: str
    access_token: str
    catalog: str | None = None
    schema_name: str = Field(default="default", alias="schema")

    model_config = {"populate_by_name": True}


ConnectionConfig = Annotated[
    Union[
        PostgresConnectionConfig,
        SnowflakeConnectionConfig,
        DuckDBConnectionConfig,
        ParquetConnectionConfig,
        DatabricksConnectionConfig,
    ],
    Field(discriminator="type"),
]


# --------------------------------------------------------------------------
# Defaults
# --------------------------------------------------------------------------


class HashDefaults(BaseModel):
    algorithm: Literal["sha256", "md5"] = "sha256"
    null_token: str = "<NULL>"
    delimiter: str = "|"
    trim_strings: bool = True
    case_sensitive: bool = False
    empty_string_as_null: bool = False
    decimal_scale: int = 2
    timestamp_format: str = "yyyy-MM-dd HH:mm:ss"
    timestamp_timezone: str = "UTC"


class DefaultsConfig(BaseModel):
    hash: HashDefaults = Field(default_factory=HashDefaults)


# --------------------------------------------------------------------------
# Tolerance
# --------------------------------------------------------------------------


class ToleranceConfig(BaseModel):
    type: Literal["percentage", "absolute"] = "percentage"
    warning: float = 0.0
    failure: float = 0.0


# --------------------------------------------------------------------------
# Dataset side (source / target)
# --------------------------------------------------------------------------


class DatasetSide(BaseModel):
    connection: str
    object: str | None = None
    sql: str | None = None
    filter: str | None = None

    @model_validator(mode="after")
    def _one_of_object_or_sql(self) -> "DatasetSide":
        if bool(self.object) == bool(self.sql):
            raise ValueError("Exactly one of 'object' or 'sql' must be set on a dataset side")
        return self


# --------------------------------------------------------------------------
# Schema contract
# --------------------------------------------------------------------------


class UnmappedColumn(BaseModel):
    column: str
    handling: str = "unmapped"


class SchemaContractConfig(BaseModel):
    enabled: bool = False
    mode: Literal["structural", "mapping_based"] = "structural"
    source_required_columns: list[str] = Field(default_factory=list)
    target_expected_columns: list[str] = Field(default_factory=list)
    target_unmapped_columns: list[UnmappedColumn] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Count / duplicate keys
# --------------------------------------------------------------------------


class CountConfig(BaseModel):
    enabled: bool = False
    tolerance: ToleranceConfig | None = None


class DuplicateKeysConfig(BaseModel):
    enabled: bool = False


# --------------------------------------------------------------------------
# Row hash
# --------------------------------------------------------------------------


class RowHashConfig(BaseModel):
    enabled: bool = False
    max_mismatch_samples: int = 10000
    write_full_mismatches: bool = False


# --------------------------------------------------------------------------
# Aggregate
# --------------------------------------------------------------------------

AggregateCheck = Literal["count", "count_distinct", "sum", "avg", "min", "max", "null_count"]


class AggregateMetric(BaseModel):
    column: str
    checks: list[AggregateCheck]
    tolerance: ToleranceConfig | None = None


class AggregateConfig(BaseModel):
    enabled: bool = False
    group_by: list[str] = Field(default_factory=list)
    metrics: list[AggregateMetric] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Statistical
# --------------------------------------------------------------------------

StatisticalCheck = Literal[
    "mean", "stddev", "min", "max", "null_rate", "distinct_count", "p50", "p95", "p99"
]


class StatisticalMetric(BaseModel):
    column: str
    checks: list[StatisticalCheck]
    tolerance: ToleranceConfig | None = None


class StatisticalConfig(BaseModel):
    enabled: bool = False
    metrics: list[StatisticalMetric] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Data quality
# --------------------------------------------------------------------------

DataQualityRuleType = Literal[
    "not_null", "duplicate", "allowed_values", "range", "regex", "length", "custom_sql"
]
Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class DataQualityRule(BaseModel):
    name: str
    type: DataQualityRuleType
    column: str | None = None
    values: list[str] | None = None
    min: float | None = None
    max: float | None = None
    pattern: str | None = None
    length_min: int | None = None
    length_max: int | None = None
    sql: str | None = None
    severity: Severity = "MEDIUM"


class DataQualityConfig(BaseModel):
    enabled: bool = False
    rules: list[DataQualityRule] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Validations bundle
# --------------------------------------------------------------------------


class ValidationsConfig(BaseModel):
    schema_contract: SchemaContractConfig = Field(default_factory=SchemaContractConfig)
    count: CountConfig = Field(default_factory=CountConfig)
    duplicate_keys: DuplicateKeysConfig = Field(default_factory=DuplicateKeysConfig)
    row_hash: RowHashConfig = Field(default_factory=RowHashConfig)
    aggregate: AggregateConfig = Field(default_factory=AggregateConfig)
    statistical: StatisticalConfig = Field(default_factory=StatisticalConfig)
    data_quality: DataQualityConfig = Field(default_factory=DataQualityConfig)


# --------------------------------------------------------------------------
# Dataset
# --------------------------------------------------------------------------

MappingMode = Literal["table_to_table", "query_to_query"]


class DatasetConfig(BaseModel):
    name: str
    mapping_mode: MappingMode
    source: DatasetSide
    target: DatasetSide
    primary_key: list[str]
    compare_columns: list[str] = Field(default_factory=list)
    validations: ValidationsConfig = Field(default_factory=ValidationsConfig)


# --------------------------------------------------------------------------
# Root
# --------------------------------------------------------------------------


class RootConfig(BaseModel):
    project: ProjectConfig
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    connections: dict[str, ConnectionConfig]
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    datasets: list[DatasetConfig] = Field(default_factory=list)
