"""Credential CRUD service with AES-GCM encryption."""

from __future__ import annotations
import secrets
import logging
from typing import Optional, List, Dict

from cloud.auth.database import db_ctx
from cloud.auth.crypto import encrypt_value, decrypt_value, mask_value
from cloud.auth.models import CredentialCreate, CredentialUpdate, CredentialResponse, CredentialSyncResponse, SharedCredentialResponse

logger = logging.getLogger(__name__)


def _gen_id() -> str:
    return f"cred_{secrets.token_hex(3)}"


def _row_to_cred(row, decrypt: bool = False) -> CredentialResponse:
    enc_val = row["cred_value_enc"]
    try:
        plain = decrypt_value(enc_val)
    except Exception:
        plain = "****"
    return CredentialResponse(
        cred_id=row["cred_id"],
        user_id=row["user_id"],
        service=row["service"],
        cred_key=row["cred_key"],
        cred_value_masked=mask_value(plain),
        description=row["description"] or "",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_shared(row) -> SharedCredentialResponse:
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


class CredentialService:
    """Credential CRUD with AES-GCM encryption."""

    @staticmethod
    def get_user_credentials(user_id: str) -> List[CredentialResponse]:
        with db_ctx() as conn:
            rows = conn.execute(
                "SELECT * FROM credentials WHERE user_id = ? ORDER BY service, cred_key", (user_id,)
            ).fetchall()
            return [_row_to_cred(r) for r in rows]

    @staticmethod
    def get_credential(cred_id: str, user_id: str) -> Optional[CredentialResponse]:
        with db_ctx() as conn:
            row = conn.execute(
                "SELECT * FROM credentials WHERE cred_id = ? AND user_id = ?", (cred_id, user_id)
            ).fetchone()
            return _row_to_cred(row) if row else None

    @staticmethod
    def get_decrypted_value(cred_id: str, user_id: str) -> Optional[str]:
        """Get raw decrypted value (for edge sync)."""
        with db_ctx() as conn:
            row = conn.execute(
                "SELECT cred_value_enc FROM credentials WHERE cred_id = ? AND user_id = ?",
                (cred_id, user_id),
            ).fetchone()
            if not row:
                return None
            return decrypt_value(row["cred_value_enc"])

    @staticmethod
    def create_credential(user_id: str, data: CredentialCreate) -> CredentialResponse:
        cred_id = _gen_id()
        enc_value = encrypt_value(data.cred_value)
        with db_ctx() as conn:
            conn.execute(
                """INSERT INTO credentials (cred_id, user_id, service, cred_key, cred_value_enc, description)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (cred_id, user_id, data.service, data.cred_key, enc_value, data.description),
            )
            row = conn.execute("SELECT * FROM credentials WHERE cred_id = ?", (cred_id,)).fetchone()
            return _row_to_cred(row)

    @staticmethod
    def update_credential(cred_id: str, user_id: str, data: CredentialUpdate) -> CredentialResponse:
        with db_ctx() as conn:
            row = conn.execute(
                "SELECT * FROM credentials WHERE cred_id = ? AND user_id = ?", (cred_id, user_id)
            ).fetchone()
            if not row:
                raise ValueError("Credential not found")

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
                params.extend([cred_id, user_id])
                conn.execute(
                    f"UPDATE credentials SET {', '.join(updates)} WHERE cred_id = ? AND user_id = ?",
                    params,
                )

            row = conn.execute("SELECT * FROM credentials WHERE cred_id = ?", (cred_id,)).fetchone()
            return _row_to_cred(row)

    @staticmethod
    def delete_credential(cred_id: str, user_id: str):
        with db_ctx() as conn:
            conn.execute(
                "DELETE FROM credentials WHERE cred_id = ? AND user_id = ?", (cred_id, user_id)
            )

    @staticmethod
    def sync_credentials(user_id: str) -> CredentialSyncResponse:
        """Return user creds + shared creds grouped by service."""
        # User credentials
        with db_ctx() as conn:
            urows = conn.execute(
                "SELECT * FROM credentials WHERE user_id = ? ORDER BY service, cred_key", (user_id,)
            ).fetchall()
            srows = conn.execute(
                "SELECT * FROM shared_credentials ORDER BY service, cred_key"
            ).fetchall()

        user_creds: Dict[str, List[CredentialResponse]] = {}
        for r in urows:
            cred = _row_to_cred(r)
            user_creds.setdefault(cred.service, []).append(cred)

        shared_creds: Dict[str, List[SharedCredentialResponse]] = {}
        for r in srows:
            cred = _row_to_shared(r)
            shared_creds.setdefault(cred.service, []).append(cred)

        return CredentialSyncResponse(
            user_credentials=user_creds,
            shared_credentials=shared_creds,
        )

    @staticmethod
    def count_credentials() -> int:
        with db_ctx() as conn:
            return conn.execute("SELECT COUNT(*) FROM credentials").fetchone()[0]
