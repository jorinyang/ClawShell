-- ClawShell v2.0 Database Initialization
-- SQLite3 — 6 tables for multi-account auth system
-- Run: sqlite3 /data/clawshell.db < init-db.sql

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ═══════════════════════════════════════════════════════════════
-- 1. Users — multi-role account system
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS users (
    user_id         TEXT PRIMARY KEY,
    account_id      TEXT UNIQUE NOT NULL,
    display_name    TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'user',
    must_change_pwd INTEGER NOT NULL DEFAULT 0,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══════════════════════════════════════════════════════════════
-- 2. Credentials — per-user encrypted credentials
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS credentials (
    cred_id         TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    service         TEXT NOT NULL,
    cred_key        TEXT NOT NULL,
    cred_value_enc  TEXT NOT NULL,
    description     TEXT DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ═══════════════════════════════════════════════════════════════
-- 3. Shared Credentials — admin-managed, visible to all users
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS shared_credentials (
    sc_id           TEXT PRIMARY KEY,
    service         TEXT NOT NULL,
    cred_key        TEXT NOT NULL,
    cred_value_enc  TEXT NOT NULL,
    description     TEXT DEFAULT '',
    created_by      TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (created_by) REFERENCES users(user_id)
);

-- ═══════════════════════════════════════════════════════════════
-- 4. Edge Nodes — registered edge devices
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS edge_nodes (
    node_id     TEXT PRIMARY KEY,
    node_name   TEXT NOT NULL,
    node_type   TEXT DEFAULT 'edge',
    status      TEXT DEFAULT 'offline',
    ip_address  TEXT DEFAULT '',
    metadata    TEXT DEFAULT '{}',
    last_seen   TEXT DEFAULT (datetime('now')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══════════════════════════════════════════════════════════════
-- 5. Sessions — JWT session tracking
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    token       TEXT NOT NULL,
    ip_address  TEXT DEFAULT '',
    user_agent  TEXT DEFAULT '',
    is_active   INTEGER NOT NULL DEFAULT 1,
    expires_at  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ═══════════════════════════════════════════════════════════════
-- 6. Audit Logs — security audit trail
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT,
    action      TEXT NOT NULL,
    target      TEXT DEFAULT '',
    details     TEXT DEFAULT '',
    ip_address  TEXT DEFAULT '',
    timestamp   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══════════════════════════════════════════════════════════════
-- Indexes
-- ═══════════════════════════════════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_cred_user ON credentials(user_id);
CREATE INDEX IF NOT EXISTS idx_cred_service ON credentials(service);
CREATE INDEX IF NOT EXISTS idx_shared_cred_service ON shared_credentials(service);
CREATE INDEX IF NOT EXISTS idx_session_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_session_active ON sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);

-- ═══════════════════════════════════════════════════════════════
-- Default core_admin user: jorinyang (password: clawshell2026)
-- Hash: pbkdf2:sha256:100000 (stdlib fallback, no bcrypt needed)
-- ═══════════════════════════════════════════════════════════════
INSERT OR IGNORE INTO users (user_id, account_id, display_name, password_hash, role, must_change_pwd)
VALUES (
    'usr_000001',
    'jorinyang',
    '杨瑒',
    'pbkdf2:sha256:100000$62c728f68ddbd021fab2207be5400da5$427970c30189f5a42f05be4486989c792a7d984d4939f981ee51a7d9ce844ede',
    'core_admin',
    1
);
