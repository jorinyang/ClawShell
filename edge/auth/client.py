"""Auth HTTP client — stdlib-only (urllib) REST client for ClawShell Cloud auth API.

Thread-safe. All methods accept and return plain dicts.
"""

from __future__ import annotations
import json
import logging
import threading
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger(__name__)


class AuthClient:
    """HTTP client for ClawShell Cloud auth endpoints.

    Uses only stdlib urllib — zero external dependencies.
    All public methods are thread-safe (internal RLock).
    """

    def __init__(self, cloud_url: str, timeout: int = 30):
        self._base_url = cloud_url.rstrip("/")
        self._timeout = timeout
        self._lock = threading.RLock()

    # ── Low-level HTTP ──────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None,
        token: Optional[str] = None,
    ) -> dict:
        """Execute an HTTP request. Returns parsed JSON or error dict."""
        url = f"{self._base_url}{path}"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(body).encode("utf-8") if body else None

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            resp = urllib.request.urlopen(req, timeout=self._timeout)
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read().decode("utf-8"))
            except Exception:
                detail = {"detail": str(e)}
            return {"success": False, "error": f"HTTP {e.code}", "detail": detail}
        except urllib.error.URLError as e:
            return {"success": False, "error": f"Connection failed: {e.reason}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Auth API ────────────────────────────────────────

    def login(self, account_id: str, password: str) -> dict:
        """Authenticate with cloud hub.

        Returns:
            {success, token, user, must_change_pwd} or {success: False, error}
        """
        with self._lock:
            resp = self._request(
                "POST",
                "/api/v1/auth/login",
                body={"account_id": account_id, "password": password},
            )
            if "token" in resp:
                return {
                    "success": True,
                    "token": resp["token"],
                    "user": resp.get("user", {}),
                    "must_change_pwd": resp.get("must_change_pwd", 0),
                }
            return {"success": False, "error": resp.get("error", "Login failed"), "detail": resp.get("detail", {})}

    def logout(self, token: str) -> dict:
        """Revoke session on cloud hub."""
        with self._lock:
            resp = self._request("POST", "/api/v1/auth/logout", token=token)
            return {"success": resp.get("status") == "ok" or "error" not in resp}

    def refresh(self, token: str) -> dict:
        """Refresh a JWT token.

        Returns:
            {success, token, expires_at} or {success: False, error}
        """
        with self._lock:
            resp = self._request("POST", "/api/v1/auth/refresh", token=token)
            if "token" in resp:
                return {
                    "success": True,
                    "token": resp["token"],
                    "expires_at": resp.get("expires_at", ""),
                }
            return {"success": False, "error": resp.get("error", "Refresh failed")}

    def change_password(self, token: str, old_password: str, new_password: str) -> dict:
        """Change current user's password."""
        with self._lock:
            resp = self._request(
                "PUT",
                "/api/v1/auth/password",
                body={"old_password": old_password, "new_password": new_password},
                token=token,
            )
            if resp.get("status") == "ok":
                return {"success": True}
            return {"success": False, "error": resp.get("error", "Password change failed"), "detail": resp.get("detail", {})}

    def me(self, token: str) -> dict:
        """Get current user info.

        Returns:
            {success, user_id, account_id, display_name, role, ...} or {success: False, error}
        """
        with self._lock:
            resp = self._request("GET", "/api/v1/auth/me", token=token)
            if "user_id" in resp:
                return {"success": True, **resp}
            return {"success": False, "error": resp.get("error", "Failed to get user info")}

    def sync_credentials(self, token: str) -> dict:
        """Sync credentials from cloud.

        Returns:
            {success, user_credentials, shared_credentials} or {success: False, error}
        """
        with self._lock:
            resp = self._request("GET", "/api/v1/credentials/sync", token=token)
            if "user_credentials" in resp or "shared_credentials" in resp:
                return {
                    "success": True,
                    "user_credentials": resp.get("user_credentials", {}),
                    "shared_credentials": resp.get("shared_credentials", {}),
                }
            return {"success": False, "error": resp.get("error", "Sync failed"), "detail": resp.get("detail", {})}
