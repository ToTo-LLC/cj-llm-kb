-- brain_core.state migration 0002 — ingest history log.
-- Owned by Plan 07 Task 4. Powers brain_recent_ingests (Inbox UI tabs).
-- Additive-only; no ALTER/DROP of existing columns.

CREATE TABLE IF NOT EXISTS ingest_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_type TEXT,
    domain TEXT,
    status TEXT NOT NULL,
    patch_id TEXT,
    classified_at TEXT NOT NULL,
    cost_usd REAL DEFAULT 0.0,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_ingest_history_classified_at ON ingest_history(classified_at DESC);
