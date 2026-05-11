"""Cloud Hub configuration management.

All config loaded from environment variables with sensible defaults.
Credentials are NEVER hardcoded — use environment variables.
"""

from __future__ import annotations
import os
import json
from typing import Optional


class CloudConfig:
    """Cloud Hub configuration singleton."""

    def __init__(self):
        # ── Server ──────────────────────────────
        self.host: str = os.environ.get("CLAWSHELL_CLOUD_HOST", "0.0.0.0")
        self.port: int = int(os.environ.get("CLAWSHELL_CLOUD_PORT", "8000"))
        self.debug: bool = os.environ.get("CLAWSHELL_DEBUG", "false").lower() == "true"

        # ── Data ────────────────────────────────
        self.data_dir: str = os.environ.get("CLAWSHELL_DATA_DIR", "data")
        self.event_batch_size: int = int(os.environ.get("CLAWSHELL_EVENT_BATCH", "100"))

        # ── Auth ────────────────────────────────
        self.api_token: Optional[str] = os.environ.get("CLAWSHELL_API_TOKEN")
        self.auth_enabled: bool = self.api_token is not None

        # ── Swarm ───────────────────────────────
        self.heartbeat_interval: int = int(os.environ.get("CLAWSHELL_HEARTBEAT_INTERVAL", "30"))
        self.heartbeat_timeout: int = int(os.environ.get("CLAWSHELL_HEARTBEAT_TIMEOUT", "90"))

        # ── Cleanup ──────────────────────────────
        self.event_expiry_days: int = int(os.environ.get("CLAWSHELL_EVENT_EXPIRY_DAYS", "30"))

        # ── MemOS Cloud ──────────────────────────
        self.memos_cloud_url: str = os.environ.get(
            "CLAWSHELL_MEMOS_CLOUD_URL",
            "https://memos.memtensor.cn/api/openmem/v1"
        )
        self.memos_api_key: Optional[str] = os.environ.get("CLAWSHELL_MEMOS_API_KEY")
        self.memos_user_id: str = os.environ.get("CLAWSHELL_MEMOS_USER_ID", "")

        # ── Alibaba Cloud ────────────────────────
        self.oss_endpoint: str = os.environ.get("CLAWSHELL_OSS_ENDPOINT", "")
        self.oss_bucket: str = os.environ.get("CLAWSHELL_OSS_BUCKET", "clawshell-vault")
        self.oss_access_key_id: Optional[str] = os.environ.get("CLAWSHELL_ALIYUN_AK_ID")
        self.oss_access_key_secret: Optional[str] = os.environ.get("CLAWSHELL_ALIYUN_AK_SECRET")

        # ── N8N ──────────────────────────────────
        self.n8n_url: str = os.environ.get("CLAWSHELL_N8N_URL", "http://localhost:5678")
        self.n8n_webhook_url: str = os.environ.get("CLAWSHELL_N8N_WEBHOOK_URL", "")

        # ── GitHub ───────────────────────────────
        self.github_token: Optional[str] = os.environ.get("CLAWSHELL_GITHUB_TOKEN")
        self.github_repo: str = os.environ.get("CLAWSHELL_GITHUB_REPO", "jorinyang/ClawShell")

    def to_dict(self, safe: bool = True) -> dict:
        """Export config as dict. safe=True masks credentials."""
        d = self.__dict__.copy()
        if safe:
            for key in d:
                if any(s in key.lower() for s in ("secret", "token", "key", "password")):
                    if d[key]:
                        d[key] = d[key][:4] + "****" if len(d[key]) > 4 else "****"
        return d

    def to_json(self, safe: bool = True) -> str:
        return json.dumps(self.to_dict(safe), indent=2)


# Global config instance
config = CloudConfig()
