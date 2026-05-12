"""Hermes adapter — inject ClawShell into Hermes Agent (~/.hermes)."""

import os
import json
import yaml
from edge.adapters.base import BaseAdapter


class HermesAdapter(BaseAdapter):
    FRAMEWORK_NAME = "hermes"

    def __init__(self, config_path: str = "~/.hermes"):
        self._root = os.path.expanduser(config_path)

    def detect(self) -> bool:
        return os.path.isdir(self._root)

    def inject(self, config: dict) -> bool:
        """Inject ClawShell skill + config + env."""
        try:
            # 1. Install clawshell-edge skill
            skill_dir = os.path.join(self._root, "skills", "clawshell")
            os.makedirs(skill_dir, exist_ok=True)
            skill_md = os.path.join(skill_dir, "SKILL.md")
            if not os.path.exists(skill_md):
                with open(skill_md, "w") as f:
                    f.write(_CLAWSHELL_SKILL_CONTENT)

            # 2. Update config.yaml
            cfg_file = os.path.join(self._root, "config.yaml")
            cfg = {}
            if os.path.exists(cfg_file):
                with open(cfg_file) as f:
                    cfg = yaml.safe_load(f) or {}

            cfg.setdefault("clawshell", {})
            cfg["clawshell"]["enabled"] = True
            cfg["clawshell"]["cloud_url"] = config.get("cloud_url", "http://localhost:8000")
            cfg["clawshell"]["edge_token"] = config.get("edge_token", "")

            with open(cfg_file, "w") as f:
                yaml.dump(cfg, f, default_flow_style=False)

            # 3. Set env
            env_file = os.path.join(self._root, ".env")
            env_lines = []
            if os.path.exists(env_file):
                with open(env_file) as f:
                    env_lines = f.read().strip().split("\n")

            env_vars = {
                "CLAWSHELL_CLOUD_URL": config.get("cloud_url", ""),
                "CLAWSHELL_EDGE_TOKEN": config.get("edge_token", ""),
            }
            existing_keys = set()
            new_lines = []
            for line in env_lines:
                if "=" in line:
                    key = line.split("=")[0]
                    existing_keys.add(key)
                    if key in env_vars:
                        new_lines.append(f"{key}={env_vars[key]}")
                    else:
                        new_lines.append(line)
            for key, val in env_vars.items():
                if key not in existing_keys and val:
                    new_lines.append(f"{key}={val}")

            with open(env_file, "w") as f:
                f.write("\n".join(new_lines) + "\n")

            return True
        except Exception:
            return False

    def verify(self) -> dict:
        issues = []
        if not os.path.isdir(self._root):
            issues.append("Hermes config not found")

        skill_md = os.path.join(self._root, "skills", "clawshell", "SKILL.md")
        if not os.path.exists(skill_md):
            issues.append("ClawShell skill not installed")

        cfg_file = os.path.join(self._root, "config.yaml")
        if os.path.exists(cfg_file):
            with open(cfg_file) as f:
                cfg = yaml.safe_load(f) or {}
            if not cfg.get("clawshell", {}).get("enabled"):
                issues.append("ClawShell not enabled in config")
        else:
            issues.append("Config not found")

        return {
            "framework": self.FRAMEWORK_NAME,
            "injected": len(issues) == 0,
            "issues": issues,
        }

    def rollback(self) -> bool:
        try:
            # Remove skill
            import shutil
            skill_dir = os.path.join(self._root, "skills", "clawshell")
            if os.path.exists(skill_dir):
                shutil.rmtree(skill_dir)

            # Disable in config
            cfg_file = os.path.join(self._root, "config.yaml")
            if os.path.exists(cfg_file):
                with open(cfg_file) as f:
                    cfg = yaml.safe_load(f) or {}
                if "clawshell" in cfg:
                    cfg["clawshell"]["enabled"] = False
                    with open(cfg_file, "w") as f:
                        yaml.dump(cfg, f)
            return True
        except Exception:
            return False


_CLAWSHELL_SKILL_CONTENT = """---
name: clawshell-edge
description: ClawShell 2.0 Edge Brain — cloud-edge sync, multi-agent orchestration
version: 1.9.1
---

# ClawShell Edge Brain

## Core Functions

1. **Sync with Cloud Hub**: Automatically sync events, tasks, insights, and broadcasts
2. **Action Reference**: Pull cloud insights before each action execution
3. **Health Reporting**: Report edge health metrics to Cloud every 50s
4. **Offline Mode**: Operate autonomously when Cloud is unreachable

## Usage

This skill is auto-injected by the ClawShell Hermes Adapter.
Do not modify manually — use `clawshell-edge config` to update settings.
"""
