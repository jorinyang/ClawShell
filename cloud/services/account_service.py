"""AccountService — User account management service."""
from __future__ import annotations
import os, json, time, threading, hashlib

class AccountService:
    def __init__(self, data_dir: str):
        self._data_dir = os.path.expanduser(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)
        self._users_file = os.path.join(self._data_dir, "users.json")
        self._lock = threading.RLock()
        self._load()

    def create_user(self, account_id: str, password: str, role: str = "user") -> dict:
        h = hashlib.sha256(password.encode()).hexdigest()
        user = {"account_id": account_id, "password_hash": h, "role": role,
                "created_at": time.time(), "is_active": True}
        with self._lock:
            self._users[account_id] = user
            self._save()
        return {k: v for k, v in user.items() if k != "password_hash"}

    def get_user(self, account_id: str) -> dict | None:
        return self._users.get(account_id)

    def list_users(self) -> list:
        return [{k: v for k, v in u.items() if k != "password_hash"}
                for u in self._users.values()]

    def _load(self):
        try:
            with open(self._users_file) as f:
                self._users = json.load(f)
        except Exception:
            self._users = {}

    def _save(self):
        with open(self._users_file, "w") as f:
            json.dump(self._users, f, indent=2)
