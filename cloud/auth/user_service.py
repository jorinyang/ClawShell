"""User CRUD service with role-based access control."""

from __future__ import annotations
import secrets
import logging
from typing import Optional, List

from cloud.auth.database import db_ctx
from cloud.auth.crypto import hash_password
from cloud.auth.models import UserCreate, UserUpdate, UserResponse

logger = logging.getLogger(__name__)


def _gen_id() -> str:
    return f"usr_{secrets.token_hex(3)}"


def _row_to_user(row) -> UserResponse:
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


class UserService:
    """User CRUD with role-based access control.

    Role hierarchy:
    - core_admin: can add/edit/delete all users
    - admin: can edit non-core_admin users only
    - user: no dashboard access
    """

    @staticmethod
    def get_by_id(user_id: str) -> Optional[UserResponse]:
        with db_ctx() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return _row_to_user(row) if row else None

    @staticmethod
    def get_by_account(account_id: str) -> Optional[dict]:
        """Return raw dict (with password_hash) for auth purposes."""
        with db_ctx() as conn:
            row = conn.execute("SELECT * FROM users WHERE account_id = ?", (account_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def list_users() -> List[UserResponse]:
        with db_ctx() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
            return [_row_to_user(r) for r in rows]

    @staticmethod
    def create_user(data: UserCreate, actor_role: str) -> UserResponse:
        """Create user. Requires actor_role >= admin."""
        if actor_role not in ("core_admin", "admin"):
            raise PermissionError("Only admins can create users")

        with db_ctx() as conn:
            # Check unique account_id
            existing = conn.execute(
                "SELECT user_id FROM users WHERE account_id = ?", (data.account_id,)
            ).fetchone()
            if existing:
                raise ValueError(f"Account '{data.account_id}' already exists")

            # Admin cannot create core_admin
            if actor_role == "admin" and data.role == "core_admin":
                raise PermissionError("Admin cannot create core_admin users")

            user_id = _gen_id()
            pwd_hash = hash_password(data.password)
            conn.execute(
                """INSERT INTO users (user_id, account_id, display_name, password_hash, role, must_change_pwd)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (user_id, data.account_id, data.display_name, pwd_hash, data.role),
            )
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return _row_to_user(row)

    @staticmethod
    def update_user(user_id: str, data: UserUpdate, actor_role: str, actor_id: str) -> UserResponse:
        """Update user. Role-based restrictions apply."""
        with db_ctx() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if not row:
                raise ValueError("User not found")

            target_role = row["role"]

            # Permission checks
            if actor_role == "admin" and target_role == "core_admin":
                raise PermissionError("Admin cannot modify core_admin users")
            if actor_role == "user":
                raise PermissionError("Users cannot modify other users")

            # Admin cannot promote to core_admin
            if actor_role == "admin" and data.role == "core_admin":
                raise PermissionError("Admin cannot promote users to core_admin")

            updates = []
            params = []
            if data.display_name is not None:
                updates.append("display_name = ?")
                params.append(data.display_name)
            if data.role is not None:
                updates.append("role = ?")
                params.append(data.role)
            if data.is_active is not None:
                updates.append("is_active = ?")
                params.append(data.is_active)

            if updates:
                updates.append("updated_at = datetime('now')")
                params.append(user_id)
                conn.execute(
                    f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?", params
                )

            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return _row_to_user(row)

    @staticmethod
    def delete_user(user_id: str, actor_role: str, actor_id: str):
        """Delete user. core_admin can delete all; admin cannot delete core_admin."""
        with db_ctx() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if not row:
                raise ValueError("User not found")

            if user_id == actor_id:
                raise ValueError("Cannot delete yourself")

            target_role = row["role"]
            if actor_role == "admin" and target_role == "core_admin":
                raise PermissionError("Admin cannot delete core_admin users")
            if actor_role not in ("core_admin", "admin"):
                raise PermissionError("Only admins can delete users")

            conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))

    @staticmethod
    def change_password(user_id: str, new_password: str):
        """Force-change a user's password."""
        with db_ctx() as conn:
            pwd_hash = hash_password(new_password)
            conn.execute(
                "UPDATE users SET password_hash = ?, must_change_pwd = 0, updated_at = datetime('now') WHERE user_id = ?",
                (pwd_hash, user_id),
            )

    @staticmethod
    def change_own_password(user_id: str, old_password: str, new_password: str) -> bool:
        """Change password after verifying old password."""
        from cloud.auth.crypto import verify_password
        with db_ctx() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if not row:
                raise ValueError("User not found")
            if not verify_password(old_password, row["password_hash"]):
                raise ValueError("Incorrect current password")
            pwd_hash = hash_password(new_password)
            conn.execute(
                "UPDATE users SET password_hash = ?, must_change_pwd = 0, updated_at = datetime('now') WHERE user_id = ?",
                (pwd_hash, user_id),
            )
            return True

    @staticmethod
    def count_users() -> dict:
        with db_ctx() as conn:
            total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM users WHERE is_active = 1").fetchone()[0]
            return {"total": total, "active": active}
