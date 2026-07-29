# Feature: Referential Integrity Validation

## Status

| Field      | Value                                                   |
| ---------- | ------------------------------------------------------- |
| Priority   | High                                                    |
| Status     | Approved — Ready for Implementation                    |
| Complexity | Medium-Large                                           |
| Output     | New validation type: `referential_integrity`            |

---

## Problem

DVA currently validates a configured source dataset against a configured target dataset using
count, duplicate-key, row-hash, aggregate, statistical, data-quality, and schema-contract checks.

Those validations can prove that a migrated fact table matches its source, but they do not prove
that the target warehouse model is internally usable.

In a dimensional warehouse, fact tables depend on dimension tables. For example, sales facts must
join to product, customer, date, promotion, currency, and territory dimensions. If a fact table
contains a key that does not exist in the related dimension, business reports may lose or misclassify
rows even when source-versus-target row counts and hashes are otherwise useful.

Add a referential-integrity validation that checks whether configured child keys in one dataset
exist in configured parent keys from another dataset.

---

## Goal

Provide a validation capability that:

* Checks configured cross-dataset relationships, such as `fact_sales.ProductKey -> dim_product.ProductKey`.
* Runs as part of the normal DVA validation plan when enabled in YAML.
* Reports missing parent keys and affected child-row counts.
* Stores results in Postgres.
* Surfaces results in CLI reporting and Superset.
* Remains fully backward compatible with existing configurations.
* Helps users determine whether target warehouse facts can join correctly to target dimensions.

---

## In Scope

* New optional validation type: `referential_integrity`
* YAML configuration model for cross-dataset relationships
* Validation engine for checking child dataset keys against parent dataset keys
* Result model and Postgres persistence
* New additive Postgres migration and dashboard-friendly views
* CLI reporting through existing results workflow
* Superset visibility for referential-integrity failures
* Unit tests and integration-style tests using local DuckDB/sample data where practical
* Documentation updates after implementation

## Out of Scope

* CSV export
* Automatic relationship discovery
* Automatic foreign-key inference from database catalogs
* Enforcing physical database constraints
* Changing existing validation behavior
* Changing existing validation result semantics
* Requiring all datasets to define relationships
* Redesigning the orchestrator or connector architecture
* Replacing existing schema-contract validation
* Validating relationships across live databases by using database-native foreign-key metadata

## Grain

One result row per configured relationship per child dataset per run.

Each result must contain enough information to report:

* Run identifier
* Child dataset name
* Relationship name
* Child side being checked
* Child column or columns
* Parent dataset name
* Parent side being checked
* Parent column or columns
* Status
* Missing-key count
* Affected child-row count
* Sample missing keys
* Optional details or error message

---

## Functional Requirements

### FR-01: YAML Configuration

Add support for:

```yaml
validations:
  referential_integrity:
    enabled: true
    max_samples: 50
    null_handling: ignore
    relationships:
      - name: product_key_exists
        child_column: ProductKey
        parent_dataset: dim_product_validation
        parent_column: ProductKey
```

The validation must also support composite relationships:

```yaml
validations:
  referential_integrity:
    enabled: true
    relationships:
      - name: sales_order_line_exists
        child_columns: [SalesOrderNumber, SalesOrderLineNumber]
        parent_dataset: sales_order_line_validation
        parent_columns: [SalesOrderNumber, SalesOrderLineNumber]
```

For single-column relationships, `child_column` and `parent_column` may be used.
For composite relationships, `child_columns` and `parent_columns` must be used.

The configuration must reject a relationship that mixes single-column and composite-column syntax.

### FR-02: Backward Compatibility

Existing YAML files that do not include `referential_integrity` must continue to load and run
unchanged.

The new validation must be disabled by default unless explicitly enabled with at least one
relationship.

Existing CLI commands, existing result tables, and existing dashboards must continue to work.

### FR-03: Relationship Reference Validation

Config validation must verify that:

1. Each `parent_dataset` exists in the same config.
2. A relationship has a non-empty `name`.
3. A relationship has either single-column syntax or composite-column syntax.
4. Child and parent composite lists have the same length.
5. The child dataset does not reference itself as the parent dataset unless explicitly allowed by
   future configuration. Self-references are out of scope for this feature.

Column existence should be checked at runtime using the same schema-probe behavior used by existing
connectors, not during config parsing.

### FR-04: Child and Parent Sides

The first implementation must check target-to-target relationships by default:

```text
child dataset target query/object -> parent dataset target query/object
```

Example:

```text
fact_internet_sales_validation.target.ProductKey
must exist in
dim_product_validation.target.ProductKey
```

The configuration may include optional side fields for future extensibility:

```yaml
child_side: target
parent_side: target
```

For this feature, supported values are `target` only. If provided with any other value, config
validation must reject it with a clear error message.

### FR-05: Validation Logic

For each relationship:

1. Build child SQL from the child dataset target object/query.
2. Build parent SQL from the parent dataset target object/query.
3. Select distinct child key values from the child SQL.
4. Select distinct parent key values from the parent SQL.
5. Identify child key values that do not exist in parent key values.
6. Count distinct missing keys.
7. Count affected child rows for those missing keys.
8. Capture sample missing keys up to `max_samples`.
9. Write one result row for the relationship.

If no missing keys are found, status is `PASS`.

If one or more missing keys are found, status is `FAIL`.

If the validation cannot run because of a SQL or connector error, status is `ERROR` for that
relationship and the dataset should be marked according to existing dataset status rules.

### FR-06: Null Handling

Support a relationship-level or validation-level `null_handling` setting:

| Value | Behavior |
| ----- | -------- |
| `ignore` | Null child keys are ignored and do not fail referential integrity. Default. |
| `fail` | Null child keys are counted as missing parent keys. |

The default must be `ignore`, because nullable foreign keys are common in warehouse models.

Composite keys with any null component follow the same null-handling rule.

### FR-07: SQL Generation

SQL generation must:

* Use the existing dialect identifier quoting.
* Use existing base SQL builders where possible.
* Work for DuckDB, Postgres, Snowflake, and Databricks dialects where the existing connector can
  execute standard SQL.
* Avoid database-specific anti-join syntax when a portable `LEFT JOIN ... WHERE parent IS NULL`
  form is sufficient.
* Write generated SQL files when `execution.write_generated_sql` is true, using clear labels such
  as:

```text
<dataset>__referential_integrity_<relationship>_child.sql
<dataset>__referential_integrity_<relationship>_parent.sql
<dataset>__referential_integrity_<relationship>_missing.sql
```

### FR-08: Result Persistence

Add a new migration file:

```text
sql/postgres/003_referential_integrity.sql
```

Do not modify existing numbered migrations unless strictly necessary for migration registration.

Create a table:

```text
dva.referential_integrity_results
```

Required columns:

* `id`
* `run_id`
* `dataset_name`
* `relationship_name`
* `child_side`
* `child_columns`
* `parent_dataset_name`
* `parent_side`
* `parent_columns`
* `status`
* `missing_key_count`
* `affected_row_count`
* `sample_missing_keys`
* `details`

Use text or JSON-compatible text columns for column lists and sample keys to stay consistent with
the current project style.

Add indexes for:

* `run_id`
* `dataset_name`
* `parent_dataset_name`
* `status`

### FR-09: Views

Create dashboard-friendly views in the same migration or a subsequent migration:

* `dva.v_referential_integrity_failures`
* `dva.v_chart_referential_integrity_results`

The chart view must include dataset-level dimensions from `dva.dataset_summary` where available:

* run ID
* dataset name
* source connection
* target connection
* dataset status
* relationship name
* child columns
* parent dataset
* parent columns
* missing-key count
* affected-row count
* status

### FR-10: CLI Reporting

Extend the existing `dva results` detail output so referential-integrity results appear in the
summary/detail path.

At minimum, `dva results --project <name> --summary` must include a section:

```text
-- Referential integrity ----------------
```

Each row should show:

* dataset name
* relationship name
* child columns
* parent dataset name
* parent columns
* missing-key count
* affected-row count
* status

Failed relationships should be visible without requiring Superset.

### FR-11: Superset Reporting

Update the Superset bootstrap so referential-integrity results are visible.

At minimum:

* Register `v_chart_referential_integrity_results` as a dataset.
* Add a chart/table named `Referential Integrity Failures`.
* Add the chart to an appropriate existing dashboard, preferably `Validation Deep Dive`.

Do not remove, rename, or recreate unrelated charts beyond the existing bootstrap refresh behavior.

Do not add CSV reporting.

### FR-12: Validation Issues

When a relationship fails, record a validation issue using the existing issue mechanism.

Use:

```text
rule_type = referential_integrity
issue_type = missing_parent_keys
```

Severity should default to `HIGH`.

The sample values should include sampled missing keys.

### FR-13: Execution Order

Add `referential_integrity` to the validation execution plan after row-level source-target checks
and before aggregate/statistical checks, unless implementation analysis identifies a better order.

Recommended order:

```text
schema_contract
count
duplicate_keys
row_hash
referential_integrity
aggregate
statistical
data_quality
```

The new validation must respect CLI scoping:

* Included when default validations run, if enabled in config.
* Included when explicitly selected using `--validations referential_integrity`.
* Excluded when skipped using `--skip-validations referential_integrity`.

Add aliases:

| Alias | Canonical type |
| ----- | -------------- |
| `ri` | `referential_integrity` |
| `fk` | `referential_integrity` |
| `foreign_keys` | `referential_integrity` |

### FR-14: Mandatory Runtime Verification

After implementation and automated testing, run the feature against a local, available configuration
that demonstrates at least one passing and one failing referential-integrity relationship. Runtime
verification must also cover the full set of relationships added under FR-15, not only a single
dataset.

Use the project's documented command invocation.

If live Postgres/Superset services are unavailable, inspect documented startup commands, environment
variables, and available services before marking verification as not completed. Do not stop after
mocked unit tests.

If the runtime command cannot be executed, first inspect the repository, environment variables,
configuration files, and available services to determine whether the required inputs already
exist. Use the available project-supported command invocation and retry when the normal command
is blocked or unavailable.

Before checking whether Postgres or Superset is running, detect which container tooling is
actually available in the environment (for example, `docker` or `podman`) rather than assuming a
specific tool is installed. If a command using one tool is not found or fails to execute, retry
the equivalent command using the other tool before concluding a service is unavailable.

When checking whether Postgres or Superset is already running, list existing containers (for
example using `docker ps` or `podman ps`, whichever is actually available) and match against the
project's expected container or service names (for example `*_postgres_1`, `*_superset_1`) before
concluding a service must be started. A container already reported as running or healthy must be
treated as available, even if a separate health-endpoint request fails for an unrelated reason
such as an incorrect host, port, or protocol used by the verification step itself.

Only mark an item as `Not verified` when a required credential, configuration value, service, or
network path is genuinely unavailable after inspection using the available container tooling.
State exactly what is missing and which commands were attempted.

For each attempted runtime item (Postgres persistence, CLI reporting, Superset visibility), report:

- `✅ Verified`
- `❌ Failed`
- `⚠️ Not verified`
- `⏭️ Skipped`

Runtime verification must report:

* Config used
* Command used
* Run ID
* Number of referential-integrity relationships checked
* Number passed
* Number failed
* At least one sample failed relationship, if present
* Whether CLI reporting showed the new section
* Whether Postgres persistence was verified
* Whether Superset visibility was verified

Do not report mocked unit-test success as proof of live referential-integrity validation.

### FR-15: Mandatory Full-Warehouse Coverage in the Real Configuration

This feature must be configured directly in the project's real, existing configuration file (the
configuration file actually used for validation runs today), not in a separate demo or example
file created solely for this feature.

The implementation agent must inspect every dataset already defined in that real configuration
file and identify, for each fact-type dataset, which of its columns are foreign keys that
logically correspond to the primary key of another dataset already defined in the same file. A
column is considered a candidate foreign key when its name matches or closely corresponds to the
primary key column name of another dataset in the file.

For every such relationship the agent discovers, it must add a corresponding
`referential_integrity` relationship entry on the child (fact) dataset, pointing to the correct
parent dataset and parent column, using the configuration syntax defined in FR-01.

The agent must not skip a fact dataset solely because it was not explicitly named anywhere in this
specification. Coverage must be determined by inspecting the actual configuration file's datasets,
primary keys, and column names at implementation time, not by following a fixed, pre-named list of
dataset or column names supplied elsewhere.

Configuring `referential_integrity` on only one fact dataset, while the same configuration file
contains other fact datasets with discoverable foreign-key relationships to existing dimension
datasets, does not satisfy this requirement.

This discovery step is a one-time configuration-authoring task performed by the implementation
agent while editing the YAML file. It is separate from, and must not be confused with, the
automatic relationship-discovery and foreign-key-inference capabilities that remain out of scope
for the validation engine itself per NFR-02 and the Out of Scope section. The engine continues to
require relationships to be explicitly listed in YAML at run time; only the initial authoring of
that YAML is expected to be performed by inspecting the existing configuration.

### FR-16: No Synthetic or Demo Verification Data

Runtime verification must use the project's real, existing configuration file and the real,
already-configured connections used for actual validation runs — the same configuration file
covered by FR-15.

The implementation agent must not create a new synthetic dataset, demo configuration file, or
fabricated fact/dimension pair solely to produce a passing or failing referential-integrity result
for verification purposes. A synthetic result does not satisfy any acceptance criterion that
requires a real, live result.

If the implementation agent temporarily creates any test data, configuration, or dataset for its
own development or debugging purposes while building the feature, it must fully remove that data
before reporting completion — including any rows written to `dva.referential_integrity_results` or
any other persisted table, and any temporary configuration files. Final runtime verification
results reported to the user must come only from a real run against the real configuration file,
never from synthetic or demo data left in place.

### FR-17: Autonomous Environment Resolution

The implementation agent is responsible for resolving environment setup issues — Python
interpreter selection, virtual environment creation, and dependency installation — using the
project's own documented commands (see the project's command cheat sheet, `pyproject.toml`, and
`.python-version`) without requiring the user to manually diagnose or fix these issues step by
step.

The agent must not ask the user to manually run individual low-level setup commands (for example,
"run this sync command," "activate the virtual environment," or "change the Python version") as a
substitute for the agent performing environment setup itself as part of completing this feature.

The agent must not modify project files that are unrelated to this feature as a workaround for an
environment problem. In particular, the agent must not modify existing certificate or trust-store
files (for example a bundled CA bundle) to work around a TLS or network connectivity issue.

If, after genuinely attempting the project's documented setup and connection commands, a real
external blocker remains — for example, a corporate network, firewall, or proxy prevents reaching
a configured warehouse, or valid credentials are not available in the environment — the agent must
stop, report the specific blocker precisely, and state exactly what external action (not a code or
configuration change) is required to unblock it. This must be reported as `Not verified` with the
specific reason, not worked around by hardcoding values, patching unrelated files, or fabricating
results.

### FR-18: Full-Configuration Runtime Execution

Runtime verification must run the complete real configuration file as configured for normal use,
using the project's standard invocation, without limiting execution to a hand-selected subset of
datasets via a dataset-filtering flag.

A reduced-scope run is only acceptable when the full run is genuinely not completable because of a
real external blocker documented under FR-17, and only when the subset used is the minimum
necessary to demonstrate the feature. In that case, the reduced scope and the exact reason for it
must be explicitly reported.

Runtime verification must report whether the full configuration file was run, and if not, exactly
which datasets were included and why the remainder were excluded.

---

## Acceptance Criteria

| ID    | Acceptance Criterion |
| ----- | -------------------- |
| AC-01 | Existing configs without `referential_integrity` load and run unchanged. |
| AC-02 | Config validation rejects relationships that reference an unknown parent dataset. |
| AC-03 | Config validation rejects relationships with mismatched composite child/parent column counts. |
| AC-04 | A relationship where all child keys exist in the parent dataset produces a `PASS` result. |
| AC-05 | A relationship where one or more child keys are missing from the parent dataset produces a `FAIL` result. |
| AC-06 | Failed results include missing-key count, affected-row count, and sampled missing keys. |
| AC-07 | Null child keys are ignored by default. |
| AC-08 | With `null_handling: fail`, null child keys are counted as failures. |
| AC-09 | Composite-key relationships are supported and tested. |
| AC-10 | Generated SQL is written when `execution.write_generated_sql` is true. |
| AC-11 | Results are persisted in `dva.referential_integrity_results`. |
| AC-12 | Failed relationships are visible in CLI summary/detail output. |
| AC-13 | Failed relationships create validation issues with `rule_type=referential_integrity`. |
| AC-14 | Superset bootstrap registers the new referential-integrity dataset and chart. |
| AC-15 | The new validation respects `--validations`, `--skip-validations`, and validation aliases. |
| AC-16 | The new validation does not change existing count, duplicate-key, row-hash, aggregate, statistical, data-quality, or schema-contract behavior. |
| AC-17 | Unit tests cover config parsing, validation logic, null handling, composite keys, result persistence, and CLI output. |
| AC-18 | Existing tests continue to pass without modification. |
| AC-19 | Runtime verification clearly separates automated test results from live validation and reporting results. |
| AC-20 | No CSV output is required or added for this feature. |
| AC-21 | A relationship, persistence check, or reporting check tested only through mocks is reported as `Not verified`, not as verified. |
| AC-22 | Mocked unit-test success is never presented as proof of live referential-integrity validation, persistence, or dashboard visibility. |
| AC-23 | The final report includes a per-item table showing Verified, Failed, Skipped, or Not verified for each runtime check (Postgres persistence, CLI reporting, Superset visibility). |
| AC-24 | Each failed live check includes a sanitized, actionable error explaining what to check next (for example, database connectivity, dataset naming, or Superset availability). |
| AC-25 | Before any runtime item is marked `Not verified`, the implementation agent inspects the repository, environment variables, configuration files, and available services to confirm the prerequisite is genuinely unavailable. |
| AC-26 | Before marking Superset or Postgres as `Not verified`, the implementation agent lists running containers using whichever container tool is actually available (`docker`, falling back to `podman`, or vice versa) and matches results against the project's expected container names. |
| AC-27 | A service running in an already-existing container is never marked `Not verified` solely because a different container-management command (for example `docker ps` when only `podman` is installed, or the reverse) failed to find it. |
| AC-28 | `referential_integrity` relationships are added directly into the real, existing project configuration file used for validation runs today — not into a new demo or example file. |
| AC-29 | The implementation agent inspects all datasets in that real configuration file and adds a `referential_integrity` relationship for every discoverable foreign-key-to-primary-key relationship between a fact-type dataset and a dimension-type dataset already present in the same file, without relying on any fixed, pre-named list of dataset or column names. |
| AC-30 | Runtime verification reports, per fact dataset, how many foreign-key relationships were discovered and configured, so coverage across the whole file is visible and not limited to a single dataset. |
| AC-31 | A fact dataset with a genuine, discoverable foreign-key relationship to an existing dimension dataset is not left unconfigured merely because it was not explicitly named anywhere in this specification. |
| AC-32 | Runtime verification results reported to the user come only from a real run against the real, existing configuration file — no synthetic dataset, demo configuration file, or fabricated fact/dimension pair is used to produce the reported passing or failing result. |
| AC-33 | Any temporary test data, configuration, or dataset created by the implementation agent during development is fully removed — including any persisted rows in `dva.referential_integrity_results` or other tables, and any temporary configuration files — before completion is reported. |
| AC-34 | The implementation agent resolves environment setup issues (interpreter selection, virtual environment, dependencies) itself using the project's documented commands, without requiring the user to manually run individual low-level setup commands as a substitute for the agent doing so. |
| AC-35 | The implementation agent does not modify unrelated project files (for example, an existing bundled CA/certificate bundle) as a workaround for an environment, network, or TLS connectivity problem. |
| AC-36 | When a genuine external blocker (network, firewall, proxy, or missing credentials) prevents completing runtime verification after real setup attempts, it is reported precisely as `Not verified` with the exact blocker and the exact external action required — not worked around by hardcoding, patching unrelated files, or fabricating a result. |
| AC-37 | Runtime verification runs the complete real configuration file using the project's standard invocation; any reduced-scope run is used only because of a documented real external blocker, and the reduced scope and reason are explicitly reported. |

---

## Non-Functional Requirements

| ID     | Requirement |
| ------ | ----------- |
| NFR-01 | The feature must be backward compatible. |
| NFR-02 | The feature must not require automatic relationship discovery. |
| NFR-03 | The implementation must not add third-party dependencies. |
| NFR-04 | The validation must avoid fetching full parent/child datasets into Python when SQL anti-joins can produce counts and samples. |
| NFR-05 | Query generation must remain dialect-aware through existing dialect abstractions. |
| NFR-06 | Large failure sets must be sampled and bounded by `max_samples`. |
| NFR-07 | Error messages must identify the relationship and dataset that failed. |
| NFR-08 | The feature must not expose credentials, connection strings, or secrets in persisted details or CLI output. |
| NFR-09 | Superset changes must be idempotent under repeated bootstrap runs. |
| NFR-10 | Result persistence must remain additive and must not require destructive migration behavior. |
| NFR-11 | Runtime verification steps must not assume a specific container tool (`docker` vs `podman`) is available; they must detect and use whichever is actually present in the environment before concluding a service is unavailable. |
| NFR-12 | Referential integrity coverage decisions must be derived by inspecting the actual configuration file's datasets, primary keys, and column names at implementation time — not from a hardcoded list of dataset or column names in this specification or in the implementation. |
| NFR-13 | Runtime verification must not depend on synthetic, demo, or fabricated data left in place after completion; any temporary verification artifacts must be cleaned up so that persisted results reflect only real runs against the real configuration. |
