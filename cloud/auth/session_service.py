"""Session service: login, logout, refresh, verify."""

from __future__ import annotations
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional

from cloud.auth.database import db_ctx
from cloud.auth.crypto import verify_password, create_jwt, verify_jwt
from cloud.auth.models import LoginRequest, LoginResponse, TokenResponse, UserResponse

logger = logging.getLogger(__name__)


def _gen_session_id() -> str:
    return f"ses_{secrets.token_hex(8)}"


def _row_to_user_response(row) -> UserResponse:
    return UserResponse(
        user_id=row["user_id"],
        account_id=row["account_id"],
        display_name=row["display_name"],
        role=row["role"],
        must_change_pwd=row["must_change_pwd"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SessionService:
    """Login, logout, refresh, and JWT verification."""

    @staticmethod
    def login(data: LoginRequest, ip: str = "", user_agent: str = "") -> LoginResponse:
        """Authenticate user and create session + JWT."""
        with db_ctx() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE account_id = ?", (data.account_id,)
            ).fetchone()
            if not row:
                raise ValueError("Invalid account_id or password")

            if not row["is_active"]:
                raise ValueError("Account is disabled")

            if not verify_password(data.password, row["password_hash"]):
                raise ValueError("Invalid account_id or password")

            user = _row_to_user_response(row)

            # Create JWT
            jwt_payload = {
                "sub": user.user_id,
                "account_id": user.account_id,
                "role": user.role,
            }
            token = create_jwt(jwt_payload)

            # Create session record
            session_id = _gen_session_id()
            from cloud.auth.crypto import JWT_EXPIRE_HOURS
            expires = (datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)).isoformat()
            conn.execute(
                """INSERT INTO sessions (session_id, user_id, token, ip_address, user_agent, is_active, expires_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (session_id, user.user_id, token, ip, user_agent, expires),
            )

            return LoginResponse(token=token, user=user, must_change_pwd=user.must_change_pwd)

    @staticmethod
    def logout(token: str):
        """Revoke a session by token."""
        with db_ctx() as conn:
            conn.execute(
                "UPDATE sessions SET is_active = 0 WHERE token = ?", (token,)
            )

    @staticmethod
    def refresh(token: str) -> Optional[TokenResponse]:
        """Refresh a valid token: revoke old, issue new."""
        payload = verify_jwt(token)
        if not payload:
            return None

        user_id = payload.get("sub")
        account_id = payload.get("account_id")
        role = payload.get("role")

        with db_ctx() as conn:
            # Verify session is still active
            row = conn.execute(
                "SELECT * FROM sessions WHERE token = ? AND is_active = 1", (token,)
            ).fetchone()
            if not row:
                return None

            # Revoke old session
            conn.execute("UPDATE sessions SET is_active = 0 WHERE token = ?", (token,))

            # Issue new JWT
            new_token = create_jwt({"sub": user_id, "account_id": account_id, "role": role})
            from cloud.auth.crypto import JWT_EXPIRE_HOURS
            expires = (datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)).isoformat()

            session_id = _gen_session_id()
            conn.execute(
                """INSERT INTO sessions (session_id, user_id, token, ip_address, user_agent, is_active, expires_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (session_id, user_id, new_token, row["ip_address"], row["user_agent"], expires),
            )

            return TokenResponse(token=new_token, expires_at=expires)

    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """Verify JWT and check session is active. Returns payload or None."""
        payload = verify_jwt(token)
        if not payload:
            return None

        with db_ctx() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE token = ? AND is_active = 1", (token,)
            ).fetchone()
            if not row:
                return None

            # Check session expiry
            try:
                exp = datetime.fromisoformat(row["expires_at"])
                if datetime.utcnow() > exp:
                    conn.execute("UPDATE sessions SET is_active = 0 WHERE token = ?", (token,))
                    return None
            except Exception:
                pass

            return payload

    @staticmethod
    def cleanup_expired():
        """Deactivate expired sessions."""
        with db_ctx() as conn:
            now = datetime.utcnow().isoformat()
            conn.execute(
                "UPDATE sessions SET is_active = 0 WHERE expires_at < ? AND is_active = 1", (now,)
            )

    @staticmethod
    def active_session_count() -> int:
        with db_ctx() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE is_active = 1"
            ).fetchone()[0]
