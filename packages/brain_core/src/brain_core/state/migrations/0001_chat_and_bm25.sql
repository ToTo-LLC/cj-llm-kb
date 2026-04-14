-- brain_core.state migration 0001 — chat thread metadata + BM25 index cache.
-- Owned by Plan 03. Additive-only from here; never ALTER/DROP existing columns.

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_threads (
    thread_id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    domain TEXT NOT NULL,
    mode TEXT NOT NULL,
    turns INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_threads_domain ON chat_threads(domain);
CREATE INDEX IF NOT EXISTS idx_chat_threads_updated ON chat_threads(updated_at DESC);

CREATE TABLE IF NOT EXISTS bm25_cache (
    domain TEXT PRIMARY KEY,
    vault_hash TEXT NOT NULL,
    index_blob BLOB NOT NULL,
    built_at TEXT NOT NULL DEFAULT (datetime('now'))
);
