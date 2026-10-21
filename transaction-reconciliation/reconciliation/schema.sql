PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS reconciliation_runs (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    internal_filename TEXT NOT NULL,
    platform_filename TEXT NOT NULL,
    internal_hash TEXT NOT NULL,
    platform_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status = 'completed'),
    UNIQUE(internal_hash, platform_hash, rule_version)
);
CREATE TABLE IF NOT EXISTS source_records (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES reconciliation_runs(id),
    source TEXT NOT NULL CHECK(source IN ('internal', 'platform')),
    row_number INTEGER NOT NULL,
    raw_json TEXT NOT NULL,
    transaction_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    transaction_date TEXT NOT NULL,
    amount_minor INTEGER,
    is_valid INTEGER NOT NULL CHECK(is_valid IN (0, 1)),
    UNIQUE(run_id, source, row_number)
);
CREATE TABLE IF NOT EXISTS validation_issues (
    id INTEGER PRIMARY KEY,
    record_id INTEGER NOT NULL REFERENCES source_records(id),
    code TEXT NOT NULL,
    message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reconciliation_results (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES reconciliation_runs(id),
    transaction_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('matched', 'amount_mismatch', 'missing_platform', 'missing_internal', 'blocked')),
    internal_rows TEXT NOT NULL,
    platform_rows TEXT NOT NULL,
    internal_amount_minor INTEGER,
    platform_amount_minor INTEGER,
    difference_minor INTEGER,
    reason TEXT NOT NULL,
    UNIQUE(run_id, transaction_id, currency)
);
CREATE INDEX IF NOT EXISTS ix_results_run_status ON reconciliation_results(run_id, status, currency);
CREATE INDEX IF NOT EXISTS ix_records_transaction ON source_records(transaction_id, currency, run_id);
CREATE INDEX IF NOT EXISTS ix_issues_record ON validation_issues(record_id);
