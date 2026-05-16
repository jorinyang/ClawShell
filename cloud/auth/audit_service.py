"""Audit logging service."""

from __future__ import annotations
import logging
from typing import Optional, List

from cloud.auth.database import db_ctx
from cloud.auth.models import AuditLogResponse, AuditLogListResponse

logger = logging.getLogger(__name__)


class AuditService:
    """Log all operations with user_id, action, target, ip, timestamp."""

    @staticmethod
    def log(user_id: Optional[str], action: str, target: str = "",
            details: str = "", ip: str = ""):
        """Insert an audit log entry."""
        with db_ctx() as conn:
            conn.execute(
                """INSERT INTO audit_logs (user_id, action, target, details, ip_address)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, action, target, details, ip),
            )

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
