"""Audit logging service with v2.3.1 batched async writes."""

from __future__ import annotations
import logging
import threading
import time
from collections import deque
from typing import Optional, List

from cloud.auth.database import db_ctx
from cloud.auth.models import AuditLogResponse, AuditLogListResponse

logger = logging.getLogger(__name__)

# v2.3.1: Module-level batch buffer
_batch_buffer: deque = deque(maxlen=1000)
_batch_lock = threading.RLock()
_batch_last_flush = time.time()
_batch_size = 50
_batch_interval = 2.0  # seconds
_batch_thread: Optional[threading.Thread] = None
_batch_running = False


def _flush_batch() -> int:
    """Flush buffered audit logs to DB."""
    with _batch_lock:
        if not _batch_buffer:
            return 0
        batch = list(_batch_buffer)
        _batch_buffer.clear()
    try:
        with db_ctx() as conn:
            conn.executemany(
                "INSERT INTO audit_logs (user_id, action, target, details, ip_address) VALUES (?, ?, ?, ?, ?)",
                batch,
            )
        return len(batch)
    except Exception as e:
        logger.error("Batch audit flush failed: %s", e)
        return 0


def _batch_loop():
    """Background thread that flushes the audit buffer periodically."""
    global _batch_last_flush, _batch_running
    while _batch_running:
        time.sleep(0.5)
        should_flush = False
        with _batch_lock:
            if len(_batch_buffer) >= _batch_size:
                should_flush = True
            elif _batch_buffer and (time.time() - _batch_last_flush) >= _batch_interval:
                should_flush = True
        if should_flush:
            _flush_batch()
            _batch_last_flush = time.time()


def start_batch_daemon():
    """Start the background batch flush thread."""
    global _batch_thread, _batch_running
    if _batch_running:
        return
    _batch_running = True
    _batch_thread = threading.Thread(target=_batch_loop, daemon=True, name="audit-batch")
    _batch_thread.start()


def stop_batch_daemon():
    """Stop the daemon and flush remaining logs."""
    global _batch_running
    _batch_running = False
    if _batch_thread:
        _batch_thread.join(timeout=5)
    _flush_batch()


class AuditService:
    """Log all operations with user_id, action, target, ip, timestamp."""

    @staticmethod
    def log(user_id: Optional[str], action: str, target: str = "",
            details: str = "", ip: str = ""):
        """Buffer an audit log entry; flushed by background thread."""
        start_batch_daemon()
        with _batch_lock:
            _batch_buffer.append((user_id, action, target, details, ip))

    @staticmethod
    def get_logs(limit: int = 100, offset: int = 0,
                 user_id: Optional[str] = None) -> AuditLogListResponse:
        """Query audit logs with optional user filter."""
        with db_ctx() as conn:
            if user_id:
                total = conn.execute(
                    "SELECT COUNT(*) FROM audit_logs WHERE user_id = ?", (user_id,)
                ).fetchone()[0]
                rows = conn.execute(
                    "SELECT * FROM audit_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                    (user_id, limit, offset),
                ).fetchall()
            else:
                total = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
                rows = conn.execute(
                    "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()

            logs = [
                AuditLogResponse(
                    log_id=r["log_id"],
                    user_id=r["user_id"],
                    action=r["action"],
                    target=r["target"],
                    details=r["details"],
                    ip_address=r["ip_address"],
                    timestamp=r["timestamp"],
                )
                for r in rows
            ]
            return AuditLogListResponse(logs=logs, total=total)

    @staticmethod
    def recent_count(hours: int = 24) -> int:
        with db_ctx() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE timestamp >= datetime('now', ?)",
                (f"-{hours} hours",),
            ).fetchone()[0]

    @staticmethod
    def total_count() -> int:
        with db_ctx() as conn:
            return conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
