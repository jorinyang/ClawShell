"""Credential CRUD service with AES-GCM encryption.

Supports 3 credential types:
- api-key: name, api_key, base_url
- access-key: name, access_key_id, access_key_secret
- token-plan: name, api_key, base_url, model
- legacy: old-style single value (backward compat)
"""

from __future__ import annotations
import json
import secrets
import logging
from typing import Optional, List, Dict

from cloud.auth.database import db_ctx
from cloud.auth.crypto import encrypt_value, decrypt_value, mask_value
from cloud.auth.models import (
    CredentialCreate, CredentialUpdate, CredentialResponse,
    CredentialSyncResponse, SharedCredentialCreate, SharedCredentialUpdate,
    SharedCredentialResponse,
    CRED_TYPE_API_KEY, CRED_TYPE_ACCESS_KEY, CRED_TYPE_TOKEN_PLAN, CRED_TYPE_LEGACY,
)

logger = logging.getLogger(__name__)


def _gen_id(prefix: str = "cred") -> str:
    return f"{prefix}_{secrets.token_hex(3)}"


def _mask_field(value: Optional[str]) -> Optional[str]:
    """Mask a single sensitive field."""
    if value is None:
        return None
    return mask_value(value)


def _build_encrypted_json(cred_type: str, **kwargs) -> str:
    """Build a JSON payload from type-specific fields and encrypt it."""
    data: Dict[str, str] = {}

    if cred_type == CRED_TYPE_API_KEY:
        if kwargs.get("api_key"):
            data["api_key"] = kwargs["api_key"]
        if kwargs.get("base_url"):
            data["base_url"] = kwargs["base_url"]

    elif cred_type == CRED_TYPE_ACCESS_KEY:
        if kwargs.get("access_key_id"):
            data["access_key_id"] = kwargs["access_key_id"]
        if kwargs.get("access_key_secret"):
            data["access_key_secret"] = kwargs["access_key_secret"]

    elif cred_type == CRED_TYPE_TOKEN_PLAN:
        if kwargs.get("api_key"):
            data["api_key"] = kwargs["api_key"]
        if kwargs.get("base_url"):
            data["base_url"] = kwargs["base_url"]
        if kwargs.get("model"):
            data["model"] = kwargs["model"]

    json_str = json.dumps(data, separators=(",", ":"))
    return encrypt_value(json_str)


def _decrypt_and_parse(enc_value: str, cred_type: str) -> Dict:
    """Decrypt value and parse into type-specific fields."""
    try:
        plain = decrypt_value(enc_value)
    except Exception:
        return {}

    # If this is a legacy credential, the plain value is just a raw string
    if cred_type == CRED_TYPE_LEGACY:
        return {"cred_value_masked": mask_value(plain)}

    # Try to parse as JSON (new typed credentials)
    try:
        data = json.loads(plain)
        if isinstance(data, dict):
            # Mask sensitive fields
            result = {}
            for key, val in data.items():
                if key in ("api_key", "access_key_secret"):
                    result[key] = mask_value(val) if val else None
                else:
                    result[key] = val
            return result
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: treat as legacy raw value
    return {"cred_value_masked": mask_value(plain)}


def _row_to_cred(row, decrypt: bool = False) -> CredentialResponse:
    """Convert a DB row to CredentialResponse."""
    cred_type = row["cred_type"] if "cred_type" in row.keys() else CRED_TYPE_LEGACY
    enc_val = row["cred_value_enc"]

    fields = _decrypt_and_parse(enc_val, cred_type)

    # Name: for new typed creds, it's in the decrypted JSON or stored in cred_key
    name = row["cred_key"] or ""

    return CredentialResponse(
        cred_id=row["cred_id"],
        user_id=row["user_id"],
        service=row["service"],
        cred_type=cred_type,
        name=name,
        description=row["description"] or "",
        api_key=fields.get("api_key"),
        base_url=fields.get("base_url"),
        access_key_id=fields.get("access_key_id"),
        access_key_secret=fields.get("access_key_secret"),
        model=fields.get("model"),
        cred_key=row["cred_key"],
        cred_value_masked=fields.get("cred_value_masked"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_shared(row) -> SharedCredentialResponse:
    """Convert a DB row to SharedCredentialResponse."""
    cred_type = row["cred_type"] if "cred_type" in row.keys() else CRED_TYPE_LEGACY
    enc_val = row["cred_value_enc"]

    fields = _decrypt_and_parse(enc_val, cred_type)
    name = row["cred_key"] or ""

    return SharedCredentialResponse(
        sc_id=row["sc_id"],
        service=row["service"],
        cred_type=cred_type,
        name=name,
        description=row["description"] or "",
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        api_key=fields.get("api_key"),
        base_url=fields.get("base_url"),
        access_key_id=fields.get("access_key_id"),
        access_key_secret=fields.get("access_key_secret"),
        model=fields.get("model"),
        cred_key=row["cred_key"],
        cred_value_masked=fields.get("cred_value_masked"),
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
        """Get raw decrypted value (for edge sync). Returns JSON string for typed creds."""
        with db_ctx() as conn:
            row = conn.execute(
                "SELECT cred_value_enc, cred_type FROM credentials WHERE cred_id = ? AND user_id = ?",
                (cred_id, user_id),
            ).fetchone()
            if not row:
                return None
            return decrypt_value(row["cred_value_enc"])

    @staticmethod
    def get_decrypted_dict(cred_id: str, user_id: str) -> Optional[Dict]:
        """Get decrypted credential as a dict with all fields."""
        with db_ctx() as conn:
            row = conn.execute(
                "SELECT * FROM credentials WHERE cred_id = ? AND user_id = ?",
                (cred_id, user_id),
            ).fetchone()
            if not row:
                return None
            cred_type = row["cred_type"] if "cred_type" in row.keys() else CRED_TYPE_LEGACY
            fields = _decrypt_and_parse(row["cred_value_enc"], cred_type)
            fields["name"] = row["cred_key"]
            fields["service"] = row["service"]
            fields["cred_type"] = cred_type
            # For sensitive fields, return the raw decrypted value
            try:
                plain = decrypt_value(row["cred_value_enc"])
                if cred_type != CRED_TYPE_LEGACY:
                    parsed = json.loads(plain)
                    if isinstance(parsed, dict):
                        fields.update(parsed)
            except Exception:
                pass
            return fields

    @staticmethod
    def create_credential(user_id: str, data: CredentialCreate) -> CredentialResponse:
        cred_id = _gen_id()

        # Build encrypted JSON from type-specific fields
        enc_value = _build_encrypted_json(
            data.cred_type,
            api_key=data.api_key,
            base_url=data.base_url,
            access_key_id=data.access_key_id,
            access_key_secret=data.access_key_secret,
            model=data.model,
        )

        # Store name in cred_key column for backward compat and easy querying
        cred_key = data.name

        with db_ctx() as conn:
            conn.execute(
                """INSERT INTO credentials (cred_id, user_id, service, cred_key, cred_value_enc, cred_type, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cred_id, user_id, data.service, cred_key, enc_value, data.cred_type, data.description),
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

            cred_type = row["cred_type"] if "cred_type" in row.keys() else CRED_TYPE_LEGACY
            updates = []
            params = []

            if data.service is not None:
                updates.append("service = ?")
                params.append(data.service)

            if data.name is not None:
                updates.append("cred_key = ?")
                params.append(data.name)

            if data.description is not None:
                updates.append("description = ?")
                params.append(data.description)

            # Check if any type-specific fields were updated
            type_fields_updated = any(
                getattr(data, f, None) is not None
                for f in ("api_key", "base_url", "access_key_id", "access_key_secret", "model")
            )

            if type_fields_updated and cred_type != CRED_TYPE_LEGACY:
                # Merge existing decrypted data with updates
                try:
                    plain = decrypt_value(row["cred_value_enc"])
                    existing = json.loads(plain) if plain else {}
                except Exception:
                    existing = {}

                # Apply updates to existing data
                for field in ("api_key", "base_url", "access_key_id", "access_key_secret", "model"):
                    val = getattr(data, field, None)
                    if val is not None:
                        existing[field] = val

                json_str = json.dumps(existing, separators=(",", ":"))
                enc_value = encrypt_value(json_str)
                updates.append("cred_value_enc = ?")
                params.append(enc_value)
            elif type_fields_updated and cred_type == CRED_TYPE_LEGACY:
                # Can't update type-specific fields on legacy creds
                pass

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


class SharedCredentialService:
    """Shared credential CRUD with AES-GCM encryption."""

    @staticmethod
    def list_all() -> List[SharedCredentialResponse]:
        with db_ctx() as conn:
            rows = conn.execute(
                "SELECT * FROM shared_credentials ORDER BY service, cred_key"
            ).fetchall()
            return [_row_to_shared(r) for r in rows]

    @staticmethod
    def create(created_by: str, data: SharedCredentialCreate) -> SharedCredentialResponse:
        sc_id = _gen_id("sc")

        if data.cred_type == CRED_TYPE_LEGACY:
            enc_value = encrypt_value(data.cred_value or "")
        else:
            enc_value = _build_encrypted_json(
                data.cred_type,
                api_key=data.api_key,
                base_url=data.base_url,
                access_key_id=data.access_key_id,
                access_key_secret=data.access_key_secret,
                model=data.model,
            )

        cred_key = data.name or data.cred_key or ""

        with db_ctx() as conn:
            conn.execute(
                """INSERT INTO shared_credentials (sc_id, service, cred_key, cred_value_enc, cred_type, description, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sc_id, data.service, cred_key, enc_value, data.cred_type, data.description, created_by),
            )
            row = conn.execute("SELECT * FROM shared_credentials WHERE sc_id = ?", (sc_id,)).fetchone()
            return _row_to_shared(row)

    @staticmethod
    def update(sc_id: str, data: SharedCredentialUpdate) -> SharedCredentialResponse:
        with db_ctx() as conn:
            row = conn.execute(
                "SELECT * FROM shared_credentials WHERE sc_id = ?", (sc_id,)
            ).fetchone()
            if not row:
                raise ValueError("Shared credential not found")

            cred_type = row["cred_type"] if "cred_type" in row.keys() else CRED_TYPE_LEGACY
            updates = []
            params = []

            if data.service is not None:
                updates.append("service = ?")
                params.append(data.service)
            if data.name is not None:
                updates.append("cred_key = ?")
                params.append(data.name)
            elif data.cred_key is not None:
                updates.append("cred_key = ?")
                params.append(data.cred_key)
            if data.description is not None:
                updates.append("description = ?")
                params.append(data.description)

            type_fields_updated = any(
                getattr(data, f, None) is not None
                for f in ("api_key", "base_url", "access_key_id", "access_key_secret", "model", "cred_value")
            )

            if type_fields_updated:
                if cred_type == CRED_TYPE_LEGACY and data.cred_value is not None:
                    enc_value = encrypt_value(data.cred_value)
                    updates.append("cred_value_enc = ?")
                    params.append(enc_value)
                elif cred_type != CRED_TYPE_LEGACY:
                    try:
                        plain = decrypt_value(row["cred_value_enc"])
                        existing = json.loads(plain) if plain else {}
                    except Exception:
                        existing = {}

                    for field in ("api_key", "base_url", "access_key_id", "access_key_secret", "model"):
                        val = getattr(data, field, None)
                        if val is not None:
                            existing[field] = val

                    json_str = json.dumps(existing, separators=(",", ":"))
                    enc_value = encrypt_value(json_str)
                    updates.append("cred_value_enc = ?")
                    params.append(enc_value)

            if updates:
                updates.append("updated_at = datetime('now')")
                params.append(sc_id)
                conn.execute(
                    f"UPDATE shared_credentials SET {', '.join(updates)} WHERE sc_id = ?",
                    params,
                )

            row = conn.execute("SELECT * FROM shared_credentials WHERE sc_id = ?", (sc_id,)).fetchone()
            return _row_to_shared(row)

    @staticmethod
    def delete(sc_id: str):
        with db_ctx() as conn:
            conn.execute("DELETE FROM shared_credentials WHERE sc_id = ?", (sc_id,))

    @staticmethod
    def count() -> int:
        with db_ctx() as conn:
            return conn.execute("SELECT COUNT(*) FROM shared_credentials").fetchone()[0]
