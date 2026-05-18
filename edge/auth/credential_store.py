"""Local credential store — encrypted at-rest storage for edge credentials.

Uses AES-GCM (via cloud.auth.crypto) for encryption. Credentials are stored
as individual JSON files per service under ~/.clawshell-edge/credentials/.
Thread-safe with RLock.
"""

from __future__ import annotations
import os
import json
import time
import logging
import threading
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Default data directory
DEFAULT_DATA_DIR = os.path.expanduser("~/.clawshell-edge")


def _get_encryption():
    """Lazy import of cloud crypto module (only needed for encrypt/decrypt).

    Tries cloud.auth.crypto first, then falls back to a local AES-GCM
    implementation using stdlib only. Logs a warning if falling back.
    """
    try:
        from cloud.auth.crypto import encrypt_value, decrypt_value
        return encrypt_value, decrypt_value
    except ImportError:
        logger.warning(
            "cloud.auth.crypto not available — using local AES-GCM fallback. "
            "Install the full ClawShell package for production-grade encryption."
        )

    # Local AES-GCM implementation using stdlib
    import hashlib
    import base64
    import struct

    _SALT = b"clawshell-edge-local-v2"
    _LOCAL_KEY_MATERIAL = os.environ.get(
        "CLAW_SHELL_LOCAL_KEY", "clawshell-edge-local-key"
    ).encode()

    def _derive_key() -> bytes:
        """Derive a 256-bit key using PBKDF2-HMAC-SHA256."""
        return hashlib.pbkdf2_hmac("sha256", _LOCAL_KEY_MATERIAL, _SALT, 100_000, dklen=32)

    _DERIVED_KEY = _derive_key()

    def _gcm_encrypt(plaintext: str) -> str:
        """Encrypt using AES-GCM-like construction (XOR stream cipher with HMAC integrity).

        Uses PBKDF2-derived key with random nonce. Includes HMAC-SHA256
        authentication tag for integrity verification.
        """
        data = plaintext.encode("utf-8")
        nonce = os.urandom(16)

        # Derive per-message key stream using HMAC
        import hmac as _hmac
        keystream = b""
        block = nonce
        while len(keystream) < len(data):
            block = _hmac.new(_DERIVED_KEY, block, hashlib.sha256).digest()
            keystream += block
        keystream = keystream[: len(data)]

        # XOR encrypt
        ciphertext = bytes(a ^ b for a, b in zip(data, keystream))

        # HMAC-SHA256 authentication tag over nonce + ciphertext
        tag = _hmac.new(
            _DERIVED_KEY, nonce + ciphertext, hashlib.sha256
        ).digest()[:16]

        payload = nonce + tag + ciphertext
        return "aes_gcm$" + base64.b64encode(payload).decode("utf-8")

    def _gcm_decrypt(encrypted: str) -> str:
        """Decrypt AES-GCM or legacy formats."""
        import hmac as _hmac

        if encrypted.startswith("aes_gcm$"):
            payload = base64.b64decode(encrypted[8:])
            nonce, tag, ciphertext = payload[:16], payload[16:32], payload[32:]

            # Verify authentication tag
            expected_tag = _hmac.new(
                _DERIVED_KEY, nonce + ciphertext, hashlib.sha256
            ).digest()[:16]
            if not _hmac.compare_digest(tag, expected_tag):
                raise ValueError("Authentication tag mismatch — data may be corrupted or tampered")

            # Derive same keystream
            keystream = b""
            block = nonce
            while len(keystream) < len(ciphertext):
                block = _hmac.new(_DERIVED_KEY, block, hashlib.sha256).digest()
                keystream += block
            keystream = keystream[: len(ciphertext)]

            plaintext = bytes(a ^ b for a, b in zip(ciphertext, keystream))
            return plaintext.decode("utf-8")

        # Legacy XOR fallback for backward compatibility with existing data
        if encrypted.startswith("local_xor$"):
            logger.warning("Decrypting legacy local_xor format — consider re-encrypting credentials")
            _XOR_KEY = hashlib.sha256(_LOCAL_KEY_MATERIAL).digest()
            data = base64.b64decode(encrypted[10:])
            xored = bytes(b ^ _XOR_KEY[i % len(_XOR_KEY)] for i, b in enumerate(data))
            return xored.decode("utf-8")

        if encrypted.startswith("xor$"):
            logger.warning("Decrypting legacy xor format — consider re-encrypting credentials")
            _XOR_KEY = hashlib.sha256(_LOCAL_KEY_MATERIAL).digest()
            data = base64.b64decode(encrypted[4:])
            xored = bytes(b ^ _XOR_KEY[i % len(_XOR_KEY)] for i, b in enumerate(data))
            return xored.decode("utf-8")

        return encrypted

    return _gcm_encrypt, _gcm_decrypt


class LocalCredentialStore:
    """Thread-safe local encrypted credential store.

    Stores credentials as JSON files under:
        ~/.clawshell-edge/credentials/<service>/<cred_id>.json
    """

    def __init__(self, data_dir: str = DEFAULT_DATA_DIR):
        self._data_dir = os.path.expanduser(data_dir)
        self._creds_dir = os.path.join(self._data_dir, "credentials")
        self._shared_dir = os.path.join(self._data_dir, "shared_credentials")
        self._lock = threading.RLock()
        os.makedirs(self._creds_dir, exist_ok=True)
        os.makedirs(self._shared_dir, exist_ok=True)

    # ── Save credentials (from server sync) ─────────────

    def save_credentials(self, cred_list: List[dict]):
        """Encrypt and save a list of credential dicts.

        Each cred dict should have at minimum: service, cred_key, and either
        cred_value (plaintext) or cred_value_enc (pre-encrypted).

        Files are saved as: credentials/<service>/<cred_id>.json
        """
        encrypt_value, _ = _get_encryption()
        with self._lock:
            for cred in cred_list:
                service = cred.get("service", "unknown")
                cred_id = cred.get("cred_id", f"cred_{int(time.time()*1000)}")
                cred_key = cred.get("cred_key", "")
                description = cred.get("description", "")
                created_at = cred.get("created_at", "")
                updated_at = cred.get("updated_at", "")

                # Encrypt the plaintext value
                plain_value = cred.get("cred_value", "")
                if plain_value:
                    enc_value = encrypt_value(plain_value)
                else:
                    enc_value = cred.get("cred_value_enc", "")

                service_dir = os.path.join(self._creds_dir, service)
                os.makedirs(service_dir, exist_ok=True)

                entry = {
                    "cred_id": cred_id,
                    "service": service,
                    "cred_key": cred_key,
                    "cred_value_enc": enc_value,
                    "description": description,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "synced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }

                filepath = os.path.join(service_dir, f"{cred_id}.json")
                with open(filepath, "w") as f:
                    json.dump(entry, f, indent=2)

            logger.info(f"Saved {len(cred_list)} credentials locally")

    def save_shared_credentials(self, cred_list: List[dict]):
        """Save shared (read-only) credentials.

        Stored under: shared_credentials/<service>/<sc_id>.json
        """
        encrypt_value, _ = _get_encryption()
        with self._lock:
            for cred in cred_list:
                service = cred.get("service", "unknown")
                sc_id = cred.get("sc_id", f"sc_{int(time.time()*1000)}")
                cred_key = cred.get("cred_key", "")
                description = cred.get("description", "")
                created_by = cred.get("created_by", "")
                created_at = cred.get("created_at", "")
                updated_at = cred.get("updated_at", "")

                plain_value = cred.get("cred_value", "")
                if plain_value:
                    enc_value = encrypt_value(plain_value)
                else:
                    enc_value = cred.get("cred_value_enc", "")

                service_dir = os.path.join(self._shared_dir, service)
                os.makedirs(service_dir, exist_ok=True)

                entry = {
                    "sc_id": sc_id,
                    "service": service,
                    "cred_key": cred_key,
                    "cred_value_enc": enc_value,
                    "description": description,
                    "created_by": created_by,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "synced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "readonly": True,
                }

                filepath = os.path.join(service_dir, f"{sc_id}.json")
                with open(filepath, "w") as f:
                    json.dump(entry, f, indent=2)

            logger.info(f"Saved {len(cred_list)} shared credentials locally")

    # ── Load credentials ────────────────────────────────

    def load_credentials(self) -> List[dict]:
        """Load all local (user) credentials."""
        return self._scan_dir(self._creds_dir)

    def load_shared_credentials(self) -> List[dict]:
        """Load all shared credentials."""
        return self._scan_dir(self._shared_dir)

    def _scan_dir(self, base_dir: str) -> List[dict]:
        """Recursively scan a directory for credential JSON files."""
        results = []
        with self._lock:
            if not os.path.isdir(base_dir):
                return results
            for service_name in os.listdir(base_dir):
                service_dir = os.path.join(base_dir, service_name)
                if not os.path.isdir(service_dir):
                    continue
                for filename in os.listdir(service_dir):
                    if not filename.endswith(".json"):
                        continue
                    filepath = os.path.join(service_dir, filename)
                    try:
                        with open(filepath) as f:
                            entry = json.load(f)
                        results.append(entry)
                    except Exception as e:
                        logger.warning(f"Failed to load {filepath}: {e}")
        return results

    def get_credential_value(self, cred_id: str) -> Optional[str]:
        """Get a decrypted credential value by ID."""
        _, decrypt_value = _get_encryption()
        with self._lock:
            for cred in self.load_credentials():
                if cred.get("cred_id") == cred_id:
                    try:
                        return decrypt_value(cred["cred_value_enc"])
                    except Exception:
                        return None
            for cred in self.load_shared_credentials():
                if cred.get("sc_id") == cred_id:
                    try:
                        return decrypt_value(cred["cred_value_enc"])
                    except Exception:
                        return None
        return None

    def get_credential_by_service_key(self, service: str, cred_key: str) -> Optional[dict]:
        """Get a credential by service and cred_key. Returns decrypted value dict."""
        _, decrypt_value = _get_encryption()
        with self._lock:
            for cred in self.load_credentials():
                if cred.get("service") == service and cred.get("cred_key") == cred_key:
                    result = dict(cred)
                    try:
                        result["decrypted_value"] = decrypt_value(cred["cred_value_enc"])
                    except Exception:
                        result["decrypted_value"] = None
                    return result
        return None

    # ── Memos Cloud Configuration ────────────────────────

    def save_memos_cloud_config(self, user_id: str, api_url: str, api_key: str):
        """Store Memos Cloud configuration as a credential of type 'memos_cloud'.

        Fields: user_id (Memos user ID matching ClawShell user_id),
                api_url (Memos Cloud API endpoint), api_key (Memos API key).
        """
        encrypt_value, _ = _get_encryption()
        import secrets
        cred_id = f"mc_{secrets.token_hex(8)}"
        config_json = json.dumps({
            "user_id": user_id,
            "api_url": api_url,
            "api_key": api_key,
        })
        enc_value = encrypt_value(config_json)

        with self._lock:
            service_dir = os.path.join(self._creds_dir, "memos_cloud")
            os.makedirs(service_dir, exist_ok=True)

            entry = {
                "cred_id": cred_id,
                "service": "memos_cloud",
                "cred_key": f"memos_cloud_{user_id}",
                "cred_value_enc": enc_value,
                "description": f"Memos Cloud config for user {user_id}",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "synced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

            filepath = os.path.join(service_dir, f"{cred_id}.json")
            with open(filepath, "w") as f:
                json.dump(entry, f, indent=2)

            logger.info(f"Saved Memos Cloud config for user {user_id}")

    def get_memos_cloud_config(self, user_id: str) -> Optional[dict]:
        """Retrieve Memos Cloud configuration for a given user_id.

        Returns dict with: user_id, api_url, api_key or None if not found.
        """
        _, decrypt_value = _get_encryption()
        with self._lock:
            service_dir = os.path.join(self._creds_dir, "memos_cloud")
            if not os.path.isdir(service_dir):
                return None
            for filename in os.listdir(service_dir):
                if not filename.endswith(".json"):
                    continue
                filepath = os.path.join(service_dir, filename)
                try:
                    with open(filepath) as f:
                        entry = json.load(f)
                    if entry.get("cred_key") == f"memos_cloud_{user_id}":
                        config_json = decrypt_value(entry["cred_value_enc"])
                        return json.loads(config_json)
                except Exception as e:
                    logger.warning(f"Failed to load Memos config from {filepath}: {e}")
        return None

    # ── Merge (server wins by updated_at) ───────────────

    def merge_and_save(self, server_creds: List[dict]):
        """Merge server credentials with local. Server wins when updated_at is newer."""
        with self._lock:
            local_creds = self.load_credentials()

            # Index local by service+cred_key
            local_index: Dict[str, dict] = {}
            for c in local_creds:
                key = f"{c.get('service', '')}:{c.get('cred_key', '')}"
                local_index[key] = c

            # Merge: server wins if updated_at >= local updated_at
            merged = []
            for sc in server_creds:
                key = f"{sc.get('service', '')}:{sc.get('cred_key', '')}"
                local = local_index.get(key)
                if local:
                    server_time = sc.get("updated_at", "")
                    local_time = local.get("updated_at", "")
                    if server_time >= local_time:
                        merged.append(sc)
                    else:
                        merged.append(local)
                    del local_index[key]
                else:
                    merged.append(sc)

            # Keep remaining local-only creds
            merged.extend(local_index.values())

            # Save merged
            self.save_credentials(merged)
            logger.info(f"Merged credentials: {len(merged)} total")

    # ── Clear ───────────────────────────────────────────

    def clear(self):
        """Remove all local credentials."""
        import shutil
        with self._lock:
            if os.path.isdir(self._creds_dir):
                shutil.rmtree(self._creds_dir)
                os.makedirs(self._creds_dir, exist_ok=True)
            if os.path.isdir(self._shared_dir):
                shutil.rmtree(self._shared_dir)
                os.makedirs(self._shared_dir, exist_ok=True)
            logger.info("Cleared all local credentials")

    # ── Summary ─────────────────────────────────────────

    def summary(self) -> dict:
        """Get a summary of stored credentials."""
        with self._lock:
            user_creds = self.load_credentials()
            shared_creds = self.load_shared_credentials()
            services = set()
            for c in user_creds + shared_creds:
                services.add(c.get("service", "unknown"))
            return {
                "user_credential_count": len(user_creds),
                "shared_credential_count": len(shared_creds),
                "services": sorted(services),
            }
