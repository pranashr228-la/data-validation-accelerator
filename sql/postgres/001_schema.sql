-- DVA validation results schema (Postgres-primary storage).
-- Apply via: dva init-db

CREATE SCHEMA IF NOT EXISTS dva;

CREATE TABLE IF NOT EXISTS dva.run_summary (
    run_id          TEXT PRIMARY KEY,
    project_name    TEXT NOT NULL,
    environment     TEXT NOT NULL,
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL,
    dataset_count   INTEGER NOT NULL,
    passed_count    INTEGER NOT NULL,
    failed_count    INTEGER NOT NULL,
    error_count     INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_summary_project ON dva.run_summary (project_name);
CREATE INDEX IF NOT EXISTS idx_run_summary_start_time ON dva.run_summary (start_time DESC);

CREATE TABLE IF NOT EXISTS dva.dataset_summary (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES dva.run_summary (run_id) ON DELETE CASCADE,
    dataset_name    TEXT NOT NULL,
    mapping_mode    TEXT NOT NULL,
    source_connection TEXT,
    target_connection TEXT,
    status          TEXT NOT NULL,
    source_count    INTEGER,
    target_count    INTEGER,
    missing_count   INTEGER,
    extra_count     INTEGER,
    mismatch_count  INTEGER,
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dataset_summary_run ON dva.dataset_summary (run_id);
CREATE INDEX IF NOT EXISTS idx_dataset_summary_name ON dva.dataset_summary (dataset_name);
CREATE INDEX IF NOT EXISTS idx_dataset_summary_source ON dva.dataset_summary (source_connection);
CREATE INDEX IF NOT EXISTS idx_dataset_summary_target ON dva.dataset_summary (target_connection);

CREATE TABLE IF NOT EXISTS dva.rule_results (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES dva.run_summary (run_id) ON DELETE CASCADE,
    dataset_name    TEXT NOT NULL,
    rule_name       TEXT NOT NULL,
    rule_type       TEXT NOT NULL,
    status          TEXT NOT NULL,
    details         TEXT NOT NULL DEFAULT '',
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rule_results_run ON dva.rule_results (run_id);
CREATE INDEX IF NOT EXISTS idx_rule_results_type ON dva.rule_results (rule_type);

CREATE TABLE IF NOT EXISTS dva.schema_results (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES dva.run_summary (run_id) ON DELETE CASCADE,
    dataset_name    TEXT NOT NULL,
    check_name      TEXT NOT NULL,
    status          TEXT NOT NULL,
    details         TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_schema_results_run ON dva.schema_results (run_id);

CREATE TABLE IF NOT EXISTS dva.count_results (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES dva.run_summary (run_id) ON DELETE CASCADE,
    dataset_name    TEXT NOT NULL,
    source_count    INTEGER NOT NULL,
    target_count    INTEGER NOT NULL,
    difference      INTEGER NOT NULL,
    pct_difference  DOUBLE PRECISION NOT NULL,
    status          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_count_results_run ON dva.count_results (run_id);

CREATE TABLE IF NOT EXISTS dva.aggregate_results (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES dva.run_summary (run_id) ON DELETE CASCADE,
    dataset_name    TEXT NOT NULL,
    group_key       TEXT NOT NULL,
    column_name     TEXT NOT NULL,
    metric          TEXT NOT NULL,
    source_value    DOUBLE PRECISION,
    target_value    DOUBLE PRECISION,
    difference      DOUBLE PRECISION,
    pct_difference  DOUBLE PRECISION,
    status          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_aggregate_results_run ON dva.aggregate_results (run_id);
CREATE INDEX IF NOT EXISTS idx_aggregate_results_dataset ON dva.aggregate_results (dataset_name);

CREATE TABLE IF NOT EXISTS dva.statistical_results (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES dva.run_summary (run_id) ON DELETE CASCADE,
    dataset_name    TEXT NOT NULL,
    column_name     TEXT NOT NULL,
    metric          TEXT NOT NULL,
    source_value    DOUBLE PRECISION,
    target_value    DOUBLE PRECISION,
    difference      DOUBLE PRECISION,
    pct_difference  DOUBLE PRECISION,
    status          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_statistical_results_run ON dva.statistical_results (run_id);
CREATE INDEX IF NOT EXISTS idx_statistical_results_dataset ON dva.statistical_results (dataset_name);

CREATE TABLE IF NOT EXISTS dva.hash_summary (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES dva.run_summary (run_id) ON DELETE CASCADE,
    dataset_name        TEXT NOT NULL,
    source_row_count    INTEGER NOT NULL,
    target_row_count    INTEGER NOT NULL,
    matched_count       INTEGER NOT NULL,
    missing_count       INTEGER NOT NULL,
    extra_count         INTEGER NOT NULL,
    mismatch_count      INTEGER NOT NULL,
    status              TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_hash_summary_run ON dva.hash_summary (run_id);

CREATE TABLE IF NOT EXISTS dva.hash_mismatches (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES dva.run_summary (run_id) ON DELETE CASCADE,
    dataset_name    TEXT NOT NULL,
    primary_key     TEXT NOT NULL,
    source_hash     TEXT NOT NULL,
    target_hash     TEXT NOT NULL,
    source_record   TEXT,
    target_record   TEXT
);

CREATE INDEX IF NOT EXISTS idx_hash_mismatches_run ON dva.hash_mismatches (run_id);
CREATE INDEX IF NOT EXISTS idx_hash_mismatches_dataset ON dva.hash_mismatches (dataset_name);

CREATE TABLE IF NOT EXISTS dva.missing_records (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES dva.run_summary (run_id) ON DELETE CASCADE,
    dataset_name    TEXT NOT NULL,
    primary_key     TEXT NOT NULL,
    record          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_missing_records_run ON dva.missing_records (run_id);

CREATE TABLE IF NOT EXISTS dva.extra_records (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES dva.run_summary (run_id) ON DELETE CASCADE,
    dataset_name    TEXT NOT NULL,
    primary_key     TEXT NOT NULL,
    record          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_extra_records_run ON dva.extra_records (run_id);

CREATE TABLE IF NOT EXISTS dva.duplicate_keys (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES dva.run_summary (run_id) ON DELETE CASCADE,
    dataset_name    TEXT NOT NULL,
    side            TEXT NOT NULL,
    primary_key     TEXT NOT NULL,
    duplicate_count INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_duplicate_keys_run ON dva.duplicate_keys (run_id);

CREATE TABLE IF NOT EXISTS dva.dq_results (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES dva.run_summary (run_id) ON DELETE CASCADE,
    dataset_name    TEXT NOT NULL,
    rule_name       TEXT NOT NULL,
    rule_type       TEXT NOT NULL,
    side            TEXT NOT NULL,
    status          TEXT NOT NULL,
    failed_count    INTEGER NOT NULL,
    severity        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dq_results_run ON dva.dq_results (run_id);

CREATE TABLE IF NOT EXISTS dva.validation_issues (
    id                  BIGSERIAL PRIMARY KEY,
    issue_fingerprint   TEXT NOT NULL,
    run_id              TEXT NOT NULL REFERENCES dva.run_summary (run_id) ON DELETE CASCADE,
    dataset_name        TEXT NOT NULL,
    rule_name           TEXT NOT NULL,
    rule_type           TEXT NOT NULL,
    issue_type          TEXT NOT NULL,
    severity            TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'OPEN',
    failed_count        INTEGER NOT NULL,
    sample_values       TEXT NOT NULL DEFAULT '[]',
    first_seen_run_id   TEXT NOT NULL,
    last_seen_run_id    TEXT NOT NULL,
    recurrence_count    INTEGER NOT NULL DEFAULT 1,
    external_ticket_id  TEXT,
    waiver_status       TEXT NOT NULL DEFAULT 'NONE',
    waiver_reason       TEXT
);

CREATE INDEX IF NOT EXISTS idx_validation_issues_run ON dva.validation_issues (run_id);
CREATE INDEX IF NOT EXISTS idx_validation_issues_fingerprint ON dva.validation_issues (issue_fingerprint);

CREATE TABLE IF NOT EXISTS dva.execution_logs (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES dva.run_summary (run_id) ON DELETE CASCADE,
    timestamp       TIMESTAMPTZ NOT NULL,
    level           TEXT NOT NULL,
    dataset_name    TEXT,
    message         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_execution_logs_run ON dva.execution_logs (run_id);
