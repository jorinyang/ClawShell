"""Shared credential CRUD service (admin+ only)."""

from __future__ import annotations
import secrets
import logging
from typing import Optional, List

from cloud.auth.database import db_ctx
from cloud.auth.crypto import encrypt_value, decrypt_value, mask_value
from cloud.auth.models import SharedCredentialCreate, SharedCredentialUpdate, SharedCredentialResponse

logger = logging.getLogger(__name__)


def _gen_id() -> str:
    return f"sc_{secrets.token_hex(3)}"


def _row_to_sc(row) -> SharedCredentialResponse:
    enc_val = row["cred_value_enc"]
    try:
        plain = decrypt_value(enc_val)
    except Exception:
        plain = "****"
    return SharedCredentialResponse(
        sc_id=row["sc_id"],
        service=row["service"],
        cred_key=row["cred_key"],
        cred_value_masked=mask_value(plain),
        description=row["description"] or "",
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SharedCredentialService:
    """Shared credential CRUD. Admin+ only."""

    @staticmethod
    def list_all() -> List[SharedCredentialResponse]:
        with db_ctx() as conn:
            rows = conn.execute(
                "SELECT * FROM shared_credentials ORDER BY service, cred_key"
            ).fetchall()
            return [_row_to_sc(r) for r in rows]

    @staticmethod
    def get_by_id(sc_id: str) -> Optional[SharedCredentialResponse]:
        with db_ctx() as conn:
            row = conn.execute(
                "SELECT * FROM shared_credentials WHERE sc_id = ?", (sc_id,)
            ).fetchone()
            return _row_to_sc(row) if row else None

    @staticmethod
    def get_decrypted_value(sc_id: str) -> Optional[str]:
        with db_ctx() as conn:
            row = conn.execute(
                "SELECT cred_value_enc FROM shared_credentials WHERE sc_id = ?", (sc_id,)
            ).fetchone()
            if not row:
                return None
            return decrypt_value(row["cred_value_enc"])

    @staticmethod
    def create(data: SharedCredentialCreate, created_by: str) -> SharedCredentialResponse:
        sc_id = _gen_id()
        enc_value = encrypt_value(data.cred_value)
        with db_ctx() as conn:
            conn.execute(
                """INSERT INTO shared_credentials (sc_id, service, cred_key, cred_value_enc, description, created_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (sc_id, data.service, data.cred_key, enc_value, data.description, created_by),
            )
            row = conn.execute("SELECT * FROM shared_credentials WHERE sc_id = ?", (sc_id,)).fetchone()
            return _row_to_sc(row)

    @staticmethod
    def update(sc_id: str, data: SharedCredentialUpdate) -> SharedCredentialResponse:
        with db_ctx() as conn:
            row = conn.execute(
                "SELECT * FROM shared_credentials WHERE sc_id = ?", (sc_id,)
            ).fetchone()
            if not row:
                raise ValueError("Shared credential not found")

            updates = []
            params = []
            if data.service is not None:
                updates.append("service = ?")
                params.append(data.service)
            if data.cred_key is not None:
                updates.append("cred_key = ?")
                params.append(data.cred_key)
            if data.cred_value is not None:
                updates.append("cred_value_enc = ?")
                params.append(encrypt_value(data.cred_value))
            if data.description is not None:
                updates.append("description = ?")
                params.append(data.description)

            if updates:
                updates.append("updated_at = datetime('now')")
                params.append(sc_id)
                conn.execute(
                    f"UPDATE shared_credentials SET {', '.join(updates)} WHERE sc_id = ?", params
                )

            row = conn.execute("SELECT * FROM shared_credentials WHERE sc_id = ?", (sc_id,)).fetchone()
            return _row_to_sc(row)

    @staticmethod
    def delete(sc_id: str):
        with db_ctx() as conn:
            conn.execute("DELETE FROM shared_credentials WHERE sc_id = ?", (sc_id,))

    @staticmethod
    def count() -> int:
        with db_ctx() as conn:
            return conn.execute("SELECT COUNT(*) FROM shared_credentials").fetchone()[0]
