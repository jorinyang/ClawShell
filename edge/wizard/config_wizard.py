"""Edge Brain config wizard — interactive setup + login flow."""

from __future__ import annotations
import os
import json
import uuid
import getpass
from typing import Dict


class ConfigWizard:
    """Interactive configuration wizard for Edge Brain setup.

    Stores config at ~/.clawshell-edge/config.json
    Stores session (token, user) for persistent login.
    """

    CONFIG_FILE = "~/.clawshell-edge/config.json"
    SESSION_FILE = "~/.clawshell-edge/session.json"

    def __init__(self):
        self._config_path = os.path.expanduser(self.CONFIG_FILE)
        self._session_path = os.path.expanduser(self.SESSION_FILE)

    # ── Config ──────────────────────────────────────────

    def load_config(self) -> dict:
        """Load existing config or return defaults."""
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path) as f:
                    return json.load(f)
            except Exception:
                pass

        return {
            "cloud_url": "http://localhost:8000",
            "edge_token": "",
            "node_id": f"edge-{uuid.uuid4().hex[:8]}",
            "node_name": "",
            "sync_interval": 5,
            "auto_register": True,
            "ecosystem_components": [],
            "account_id": "",
        }

    def save_config(self, config: dict):
        """Save configuration."""
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        with open(self._config_path, "w") as f:
            json.dump(config, f, indent=2)

    def configure(self, answers: dict) -> dict:
        """Apply configuration from provided answers."""
        config = self.load_config()
        config.update(answers)
        self.save_config(config)
        return config

    # ── Session Persistence ─────────────────────────────

    def save_session(self, token: str, user: dict):
        """Save login session (token + user info) for persistent auth."""
        os.makedirs(os.path.dirname(self._session_path), exist_ok=True)
        session = {
            "token": token,
            "user": user,
            "saved_at": __import__("time").time(),
        }
        with open(self._session_path, "w") as f:
            json.dump(session, f, indent=2)
        # Also update config with token
        config = self.load_config()
        config["edge_token"] = token
        self.save_config(config)

    def load_session(self) -> dict:
        """Load saved session. Returns {} if no valid session."""
        if not os.path.exists(self._session_path):
            return {}
        try:
            with open(self._session_path) as f:
                session = json.load(f)
            if session.get("token"):
                return session
        except Exception:
            pass
        return {}

    def clear_session(self):
        """Clear saved session (logout)."""
        if os.path.exists(self._session_path):
            os.remove(self._session_path)
        config = self.load_config()
        config["edge_token"] = ""
        self.save_config(config)

    def get_token(self) -> str:
        """Get the current saved token, or empty string."""
        session = self.load_session()
        return session.get("token", "")

    # ── Interactive Login Flow ──────────────────────────

    def interactive_login(self) -> dict:
        """Interactive login flow. Returns session dict or raises."""
        from edge.auth.client import AuthClient

        config = self.load_config()
        cloud_url = config.get("cloud_url", "http://localhost:8000")

        print(f"\n🔐 ClawShell Login")
        print(f"   Cloud Hub: {cloud_url}\n")

        account_id = input("   Account ID: ").strip()
        if not account_id:
            raise ValueError("Account ID is required")

        password = getpass.getpass("   Password: ")
        if not password:
            raise ValueError("Password is required")

        client = AuthClient(cloud_url)
        result = client.login(account_id, password)

        if not result.get("success"):
            error = result.get("error", "Login failed")
            detail = result.get("detail", {})
            if isinstance(detail, dict) and detail.get("detail"):
                error = detail["detail"]
            raise ConnectionError(f"Login failed: {error}")

        token = result["token"]
        user = result["user"]

        # Save session
        self.save_session(token, user)

        # Update config with account_id
        config["account_id"] = account_id
        self.save_config(config)

        must_change = result.get("must_change_pwd", 0)
        if must_change:
            print("\n⚠️  Password change required!")
            print("   Run: clawshell change-password")

        print(f"\n✅ Logged in as: {user.get('display_name', account_id)}")
        return {"token": token, "user": user}

    def interactive_register(self) -> dict:
        """Interactive registration flow."""
        from edge.auth.client import AuthClient

        config = self.load_config()
        cloud_url = config.get("cloud_url", "http://localhost:8000")

        print(f"\n📝 ClawShell Registration")
        print(f"   Cloud Hub: {cloud_url}\n")

        account_id = input("   Account ID: ").strip()
        if not account_id:
            raise ValueError("Account ID is required")

        display_name = input("   Display Name: ").strip()
        if not display_name:
            display_name = account_id

        password = getpass.getpass("   Password (min 6 chars): ")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters")

        password2 = getpass.getpass("   Confirm Password: ")
        if password != password2:
            raise ValueError("Passwords do not match")

        client = AuthClient(cloud_url)
        resp = client._request(
            "POST",
            "/api/v2/auth/register",
            body={
                "account_id": account_id,
                "display_name": display_name,
                "password": password,
            },
        )

        if "user_id" in resp:
            print(f"\n✅ Account created: {account_id}")
            print("   Now logging in...")
            return self.interactive_login()
        else:
            error = resp.get("detail", resp.get("error", "Registration failed"))
            raise ConnectionError(f"Registration failed: {error}")

    # ── Connection Test ─────────────────────────────────

    def test_connection(self, cloud_url: str, edge_token: str = "") -> dict:
        """Test connection to Cloud Hub."""
        import urllib.request
        import urllib.error

        url = f"{cloud_url.rstrip('/')}/health"
        headers = {}
        if edge_token:
            headers["Authorization"] = f"Bearer {edge_token}"

        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read().decode())
            return {
                "success": True,
                "status": resp.status,
                "version": data.get("version", "unknown"),
                "engines": data.get("engines", {}),
            }
        except urllib.error.HTTPError as e:
            return {"success": False, "error": f"HTTP {e.code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
