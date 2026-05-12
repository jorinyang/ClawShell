"""ClawShell shared configuration — YAML + ENV 3-level config.

Design: Based on MacOS v2.1 shared/config.py.
Adapted for Main's cloud/edge config needs.

Priority: ENV > YAML file > defaults
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional


class Config:
    """3-level configuration loader: defaults < YAML file < environment variables."""
    
    def __init__(self, defaults: Optional[dict] = None):
        self._defaults = defaults or {}
        self._data: dict = {}
        self._load_env()
    
    def load_yaml(self, path: str) -> int:
        """Load and merge a YAML config file. Returns number of keys loaded."""
        p = Path(path)
        if not p.exists():
            return 0
        try:
            import yaml
            with open(p, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            count = 0
            for k, v in data.items():
                if k not in self._data:
                    self._data[k] = v
                    count += 1
            return count
        except ImportError:
            return 0
        except Exception:
            return 0
    
    def _load_env(self):
        """Load from environment variables (CLASHELL_* prefix)."""
        for key, val in os.environ.items():
            if key.startswith("CLAWSHELL_") or key in (
                "JWT_SECRET", "OSS_BUCKET", "OSS_ENDPOINT",
                "GITHUB_TOKEN", "MEMOS_CLOUD_API_KEY",
                "ALIBABA_CLOUD_ACCESS_KEY_ID", "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
            ):
                self._data[key.lower()] = val
    
    def get(self, key: str, default=None):
        """Get config value with fallback chain."""
        return self._data.get(key) or self._defaults.get(key) or default
    
    def __getattr__(self, key: str):
        return self.get(key)
    
    def to_dict(self) -> dict:
        """Export all config as dict (secrets masked)."""
        result = {}
        for k, v in {**self._defaults, **self._data}.items():
            if any(s in k.lower() for s in ("secret", "token", "key", "password")):
                result[k] = "***" if v else ""
            else:
                result[k] = v
        return result


# Global config instance
config = Config(defaults={
    "host": "0.0.0.0",
    "port": 8000,
    "data_dir": "data",
    "log_level": "INFO",
    "n8n_url": "http://localhost:5678",
    "debug": False,
})
