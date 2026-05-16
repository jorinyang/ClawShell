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
    """Lazy import of cloud crypto module (only needed for encrypt/decrypt)."""
    try:
        from cloud.auth.crypto import encrypt_value, decrypt_value
        return encrypt_value, decrypt_value
    except ImportError:
        # Edge-only mode: use local XOR fallback
        import hashlib
        import base64
        import secrets as _secrets

        _LOCAL_KEY = hashlib.sha256(
            os.environ.get("CLAW_SHELL_LOCAL_KEY", "clawshell-edge-local-key").encode()
        ).digest()

        def _encrypt(plaintext: str) -> str:
            data = plaintext.encode("utf-8")
            xored = bytes(b ^ _LOCAL_KEY[i % len(_LOCAL_KEY)] for i, b in enumerate(data))
            return "local_xor$" + base64.b64encode(xored).decode("utf-8")

        def _decrypt(encrypted: str) -> str:
            if encrypted.startswith("local_xor$"):
                data = base64.b64decode(encrypted[10:])
                xored = bytes(b ^ _LOCAL_KEY[i % len(_LOCAL_KEY)] for i, b in enumerate(data))
                return xored.decode("utf-8")
            # Also handle xor$ from cloud crypto
            if encrypted.startswith("xor$"):
                data = base64.b64decode(encrypted[4:])
                xored = bytes(b ^ _LOCAL_KEY[i % len(_LOCAL_KEY)] for i, b in enumerate(data))
                return xored.decode("utf-8")
            return encrypted

        return _encrypt, _decrypt


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
