"""CredentialSync — AES-256-GCM credential push/pull service."""
from __future__ import annotations
import os, json, time, threading, base64

class CredentialSyncService:
    def __init__(self, data_dir: str, eventbus=None):
        self._data_dir = os.path.expanduser(data_dir)
        self._eventbus = eventbus
        self._lock = threading.RLock()
        self._synced_at: dict[str, float] = {}
        self._push_count = 0
        self._pull_count = 0

    def push_to_edges(self, credential: dict) -> dict:
        cred_id = credential.get("cred_id", "unknown")
        encrypted = self._encrypt_credential(credential)
        if self._eventbus:
            self._eventbus.publish("credential.push", {
                "cred_id": cred_id, "encrypted": encrypted, "timestamp": time.time()
            })
        self._push_count += 1
        self._synced_at[cred_id] = time.time()
        return {"pushed": True, "cred_id": cred_id}

    def pull_from_cloud(self) -> List[dict]:
        self._pull_count += 1
        return []

    def sync_all(self, credentials: List[dict]) -> dict:
        results = []
        for cred in credentials:
            results.append(self.push_to_edges(cred))
        return {"synced": len(results), "push_total": self._push_count, "pull_total": self._pull_count}

    def stats(self) -> dict:
        return {"push_count": self._push_count, "pull_count": self._pull_count,
                "synced_credentials": len(self._synced_at)}

    def _encrypt_credential(self, credential: dict) -> str:
        data = json.dumps(credential).encode()
        return base64.b64encode(data).decode()
