"""SQLite WAL database for ClawShell v2.0 auth system.

Thread-safe with RLock. 6 tables: users, credentials, shared_credentials,
edge_nodes, sessions, audit_logs.
"""

from __future__ import annotations
import sqlite3
import threading
import os
import logging
from pathlib import Path

from cloud.auth.crypto import hash_password

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("CLAWSHELL_DB_PATH", str(Path.home() / ".clawshell" / "data" / "clawshell.db"))

_lock = threading.RLock()
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Get a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn


def get_db() -> sqlite3.Connection:
    """Return thread-local database connection (context-managed usage)."""
    return _get_conn()


class DatabaseContext:
    """Context manager for database operations with auto-commit/rollback."""

    def __enter__(self):
        _lock.acquire()
        self.conn = _get_conn()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
        finally:
            _lock.release()
        return False


def db_ctx() -> DatabaseContext:
    return DatabaseContext()


def init_database():
    """Create all tables if they don't exist, insert default admin."""
    with db_ctx() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     TEXT PRIMARY KEY,
                account_id  TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role        TEXT NOT NULL DEFAULT 'user',
                must_change_pwd INTEGER NOT NULL DEFAULT 0,
                is_active   INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS credentials (
                cred_id     TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                service     TEXT NOT NULL,
                cred_key    TEXT NOT NULL,
                cred_value_enc TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS shared_credentials (
                sc_id       TEXT PRIMARY KEY,
                service     TEXT NOT NULL,
                cred_key    TEXT NOT NULL,
                cred_value_enc TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_by  TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (created_by) REFERENCES users(user_id)
            );

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

            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT,
                action      TEXT NOT NULL,
                target      TEXT DEFAULT '',
                details     TEXT DEFAULT '',
                ip_address  TEXT DEFAULT '',
                timestamp   TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_cred_user ON credentials(user_id);
            CREATE INDEX IF NOT EXISTS idx_cred_service ON credentials(service);
            CREATE INDEX IF NOT EXISTS idx_shared_cred_service ON shared_credentials(service);
            CREATE INDEX IF NOT EXISTS idx_session_user ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_session_active ON sessions(is_active);
            CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
        """)

        # Insert default core_admin if not exists
        existing = conn.execute(
            "SELECT user_id FROM users WHERE account_id = ?", ("jorinyang",)
        ).fetchone()
        if not existing:
            pwd_hash = hash_password("clawshell2026")
            conn.execute(
                """INSERT INTO users (user_id, account_id, display_name, password_hash, role, must_change_pwd)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("usr_000001", "jorinyang", "杨瑒", pwd_hash, "core_admin", 1),
            )
            logger.info("Default core_admin user created: jorinyang")
