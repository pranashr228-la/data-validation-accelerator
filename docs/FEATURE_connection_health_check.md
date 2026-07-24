# Feature: Connection Health Check

## Status

| Field      | Value                                    |
| ---------- | ---------------------------------------- |
| Priority   | High                                     |
| Status     | Approved — Ready for Implementation      |
| Complexity | Small                                    |
| Output     | New CLI command: `dva check-connections` |

---

## Problem

DVA connects to source systems, target systems, the results database, and optionally Superset.

These connections are currently not verified before a validation run begins. Invalid credentials, unavailable hosts, missing databases, or an unavailable Superset server may therefore cause a run to fail after processing has already started.

Add a fast, read-only pre-flight command that checks all required connections before a full validation run.

---

## Goal

Provide a CLI command that:

* Checks every source and target connection defined in the supplied configuration.
* Checks the DVA results database.
* Checks the Superset health endpoint unless explicitly skipped.
* Reports each target as healthy or unhealthy.
* Includes elapsed time and a useful error message.
* Returns an exit code suitable for CI and scripting.

---

## In Scope

* New command: `dva check-connections`
* Existing configured connection types only
* DVA results-database connectivity
* Superset `/health` endpoint

## Out of Scope

* Adding new connector types
* Verifying dataset objects or queries
* Authenticated Superset API checks
* Verifying Superset's internal database connection
* Changing existing validation engines
* Changing the results-database schema
* Changing existing CLI command behavior
* Writing run artifacts, manifests, or generated SQL

## Grain

One result per attempted connection or service.

Each result must contain enough information to report:

* Name
* Connection or service kind
* Healthy or unhealthy status
* Elapsed milliseconds
* Error message when unsuccessful

---

## Functional Requirements

### FR-01: CLI Command

Add:

```text
dva check-connections --config <path> [--database-url <url>] [--superset-url <url>] [--skip-superset]
```

Options:

* `--config` is required.
* `--database-url` overrides the configured results-database URL.
* `--superset-url` overrides the Superset URL.
* `--skip-superset` omits the Superset check.

### FR-02: Configured Connection Checks

For every connection in the loaded configuration:

1. Create the connector using the existing connector registry.
2. Measure the time required to connect.
3. Close the connector after a successful connection.
4. Record success or failure.
5. Continue checking remaining connections after any failure.

A failure in one connection must not stop other checks.

When no connections are defined, print:

```text
No connections defined in config.
```

An empty connection collection is not itself a failure.

### FR-03: Results Database

Resolve the results-database URL using the existing reporting-database utilities.

The check must:

1. Open a connection.
2. Execute `SELECT 1`.
3. Close the connection.
4. Record success, elapsed time, or the failure reason.

This check must run independently of configured source and target checks.

### FR-04: Superset

Unless `--skip-superset` is provided:

1. Request `{superset_url}/health`.
2. Remove any trailing slash before appending `/health`.
3. Use a five-second timeout.
4. Treat HTTP status `200` as healthy.
5. Treat exceptions and non-success responses as unhealthy.

Use `urllib.request` or another suitable Python standard-library API.

### FR-05: Output

Print sections in this order:

```text
YAML Connections
Results Database
Superset
```

Do not print the Superset section when it is skipped.

Successful checks must follow this pattern:

```text
✅ {name} ({kind}): connected ({elapsed_ms} ms)
```

Failed checks must follow this pattern:

```text
❌ {name} ({kind}): connection failed — {error}
```

A failed check's message must help the user take action, not only report that it failed.
Alongside the underlying error, tell the user what to check next — for example, to verify the
username, password, host, or port in their configuration for a database or warehouse connection,
or to verify the URL and that the server is running for Superset — so the user knows what to
correct before running the command again. Do not only repeat a raw technical error with no
guidance on what to check.

The Superset wording may use `reachable` and `unreachable` where appropriate.

Print a final summary:

```text
{healthy} of {total} checks healthy
```

### FR-06: Exit Code

Return:

* `0` when every attempted check is healthy.
* `1` when at least one attempted check is unhealthy.

Skipped checks must not be included in totals or exit-code evaluation.

### FR-07: Backward Compatibility

The feature must not alter the behavior, flags, or output of existing commands.

### FR-08: Mandatory Runtime Verification

After implementation and automated testing, run the new command against the provided real
configuration and available environment.

The runtime verification must attempt:

- Every configured source and target connection
- The DVA results database
- Superset, unless `--skip-superset` is explicitly requested

Do not stop after mocked unit tests.

If the runtime command cannot be executed, first inspect the repository, environment variables,
configuration files, and available services to determine whether the required inputs already
exist. Use the available project-supported command invocation and retry when the normal command
is blocked or unavailable.

Only mark a system as `Not verified` when a required credential, configuration value, service,
or network path is genuinely unavailable after inspection. State exactly what is missing.

For each attempted system, report:

- `✅ Connected`
- `❌ Failed`
- `⚠️ Not verified`
- `⏭️ Skipped`

For failed checks, include the sanitized error and actionable next steps.

---

## Acceptance Criteria

| ID    | Acceptance Criterion                                                                                                                                   |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| AC-01 | A configuration containing two healthy connections reports both as healthy and returns exit code `0` when all other attempted checks are also healthy. |
| AC-02 | An invalid configured connection is reported as unhealthy with a useful error message, while all remaining checks still run.                           |
| AC-03 | An invalid results-database URL reports `results_database` as unhealthy without preventing configured connection checks from running.                  |
| AC-04 | `--skip-superset` removes the Superset section and excludes it from summary totals and exit-code evaluation.                                           |
| AC-05 | An unavailable Superset server is reported as unhealthy with a useful error reason.                                                                    |
| AC-06 | An empty configured-connections collection does not crash, does not count as a failed check, and allows the remaining checks to run.                   |
| AC-07 | Exit code is `0` only when every attempted check passes; any failed attempted check produces exit code `1`.                                            |
| AC-08 | Each successful check reports elapsed time.                                                                                                            |
| AC-09 | Connector, database, HTTP, and service failures are tested using mocks without requiring live external systems.                                        |
| AC-10 | All pre-existing tests continue to pass without modification.                                                                                          |
| AC-11 | A failed check's message suggests what the user should verify (for example, credentials, host, port, or URL), not only a raw technical error with no guidance on what to do next. |
| AC-12 | After implementation, the final report clearly separates automated test results from live connection-check results. |
| AC-13 | A system tested only through mocks is reported as `Not verified`, not as connected. |
| AC-14 | Each failed live connection includes sanitized, actionable guidance relevant to the failure. |
| AC-15 | The final report includes a per-system table showing Connected, Failed, Skipped, or Not verified. |
| AC-16 | Mocked unit-test success is never presented as proof of live connectivity. |

## Non-Functional Requirements

| ID     | Requirement                                                                               |
| ------ | ----------------------------------------------------------------------------------------- |
| NFR-01 | Do not add a third-party dependency for the Superset health check.                        |
| NFR-02 | Do not write files, run directories, manifests, or generated SQL.                         |
| NFR-03 | Do not insert, update, or delete data in the results database.                            |
| NFR-04 | Use lightweight connectivity checks only; do not fetch business data.                     |
| NFR-05 | Apply short, bounded timeouts where supported.                                            |
| NFR-06 | Keep new logic independently unit-testable.                                               |
| NFR-07 | Preserve existing CLI and validation behavior.                                            |
| NFR-08 | Do not expose passwords, tokens, or complete credential-bearing URLs in output or errors. |
