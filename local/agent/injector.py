"""Agent injector — unified 5-way injection for all agent types.

Executes injection for each of the 5 methods:
  MCP — Register ClawShell MCP server (mcp.json / mcpServerConfig.json)
  Hook — Register event hooks (config.yaml hooks section)
  Config — Write clawshell config section (config.yaml)
  Loop Skill — Register cron/loop task for periodic clawshell sync
  Skill — Install clawshell SKILL.md into skills/ directory

Flow: scan → report injection status → inject missing → verify → report
"""

from __future__ import annotations
import json
import logging
import os
import shutil
from typing import Any, Dict, List, Optional

from shared.types import AgentProfile, InjectionProfile, InjectionType

logger = logging.getLogger(__name__)

# Skill content injected into agent skill directories
CLAWSHELL_SKILL = """---
name: clawshell
description: ClawShell v3.0 — pluggable exoskeleton for AI agents
version: 3.0
---

# ClawShell Exoskeleton

## What This Does
- Syncs agent events, tasks, and insights with ClawShell Cloud Hub
- Provides cross-agent collaboration via AgentMesh
- Auto-discovers other agents on the same device
- Syncs knowledge and skills from your GitHub repos

## Configuration
- Cloud URL: {cloud_url}
- Agent ID: {agent_id}
- Node ID: {node_id}

## Commands
- `/clawshell status` — Show injection and sync status
- `/clawshell agents` — List discovered agents
- `/clawshell sync` — Force a sync cycle
"""


class AgentInjector:
    """Runs injection for a specific agent profile."""

    def __init__(self, cloud_url: str = "http://localhost:8000",
                 edge_token: str = ""):
        self._cloud_url = cloud_url
        self._edge_token = edge_token

    # ── Main API ─────────────────────────────────────

    def inject_all(self, agent: AgentProfile) -> InjectionProfile:
        """Run all 5 injection methods. Returns new InjectionProfile."""
        result = InjectionProfile(
            mcp=self._inject_mcp(agent),
            hook=self._inject_hook(agent),
            config=self._inject_config(agent),
            loop_skill=self._inject_loop_skill(agent),
            skill=self._inject_skill(agent),
        )
        logger.info("Injection for %s: %d/5 injected (missing: %s)",
                     agent.agent_id, result.injected_count(), result.missing())
        return result

    def inject_missing(self, agent: AgentProfile) -> InjectionProfile:
        """Inject only methods that are currently missing."""
        status = agent.injection_status
        result = InjectionProfile(
            mcp=status.mcp or self._inject_mcp(agent),
            hook=status.hook or self._inject_hook(agent),
            config=status.config or self._inject_config(agent),
            loop_skill=status.loop_skill or self._inject_loop_skill(agent),
            skill=status.skill or self._inject_skill(agent),
        )
        return result

    # ── MCP Injection ─────────────────────────────────

    def _inject_mcp(self, agent: AgentProfile) -> bool:
        """Register ClawShell MCP server in agent's MCP config."""
        config_dir = self._resolve_config_dir(agent)
        if not config_dir:
            return False

        for mcp_filename in ["mcp.json", "mcpServerConfig.json"]:
            mcp_path = os.path.join(config_dir, mcp_filename)
            if os.path.exists(mcp_path):
                return self._patch_mcp_json(mcp_path)

        # No MCP config found — create one
        mcp_path = os.path.join(config_dir, "mcp.json")
        return self._patch_mcp_json(mcp_path)

    def _patch_mcp_json(self, path: str) -> bool:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            cfg = {}
            if os.path.exists(path):
                with open(path) as f:
                    cfg = json.load(f)
            cfg.setdefault("mcpServers", {})
            cfg["mcpServers"]["clawshell"] = {
                "command": "clawshell-edge",
                "args": ["mcp", "--cloud-url", self._cloud_url],
                "description": "ClawShell v3.0 exoskeleton",
            }
            with open(path, "w") as f:
                json.dump(cfg, f, indent=2)
            return True
        except Exception as e:
            logger.error("MCP inject failed for %s: %s", path, e)
            return False

    # ── Hook Injection ────────────────────────────────

    def _inject_hook(self, agent: AgentProfile) -> bool:
        """Register ClawShell event hook in agent's config."""
        config_dir = self._resolve_config_dir(agent)
        if not config_dir:
            return False

        config_path = self._find_yaml_config(config_dir)
        if not config_path:
            return False

        try:
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}

            cfg.setdefault("hooks", [])
            hooks = cfg["hooks"]

            # Check if clawshell hook exists
            for hook in hooks:
                if isinstance(hook, dict) and hook.get("name") == "clawshell":
                    return True  # Already injected

            hooks.append({
                "name": "clawshell",
                "on": ["pre_action", "post_action", "session_start", "session_end"],
                "command": "clawshell-edge hook --event {event_type}",
                "description": "ClawShell event hook",
            })

            with open(config_path, "w") as f:
                yaml.dump(cfg, f, default_flow_style=False)
            return True
        except Exception as e:
            logger.error("Hook inject failed for %s: %s", agent.agent_id, e)
            return False

    # ── Config Injection ──────────────────────────────

    def _inject_config(self, agent: AgentProfile) -> bool:
        """Write clawshell config section into agent's config.yaml."""
        config_dir = self._resolve_config_dir(agent)
        if not config_dir:
            return False

        config_path = self._find_yaml_config(config_dir)
        if not config_path:
            config_path = os.path.join(config_dir, "config.yaml")

        try:
            import yaml
            cfg = {}
            if os.path.exists(config_path):
                with open(config_path) as f:
                    cfg = yaml.safe_load(f) or {}

            cfg["clawshell"] = {
                "enabled": True,
                "cloud_url": self._cloud_url,
                "edge_token": self._edge_token,
                "agent_id": agent.agent_id,
            }

            with open(config_path, "w") as f:
                yaml.dump(cfg, f, default_flow_style=False)
            return True
        except Exception as e:
            logger.error("Config inject failed for %s: %s", agent.agent_id, e)
            return False

    # ── Loop Skill Injection ──────────────────────────

    def _inject_loop_skill(self, agent: AgentProfile) -> bool:
        """Register a periodic sync task (cron/loop skill)."""
        config_dir = self._resolve_config_dir(agent)
        if not config_dir:
            return False

        config_path = self._find_yaml_config(config_dir)
        if not config_path:
            return False

        try:
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}

            cfg.setdefault("scheduled_tasks", {})
            cfg["scheduled_tasks"]["clawshell_sync"] = {
                "interval_seconds": 300,
                "command": "clawshell-edge sync --once",
                "description": "ClawShell periodic sync",
                "enabled": True,
            }

            with open(config_path, "w") as f:
                yaml.dump(cfg, f, default_flow_style=False)
            return True
        except Exception as e:
            logger.error("Loop skill inject failed for %s: %s", agent.agent_id, e)
            return False

    # ── Skill Injection ───────────────────────────────

    def _inject_skill(self, agent: AgentProfile) -> bool:
        """Install clawshell SKILL.md into the agent's skills directory."""
        config_dir = self._resolve_config_dir(agent)
        if not config_dir:
            return False

        skills_dir = os.path.join(config_dir, "skills", "clawshell")
        try:
            os.makedirs(skills_dir, exist_ok=True)
            content = CLAWSHELL_SKILL.format(
                cloud_url=self._cloud_url,
                agent_id=agent.agent_id,
                node_id=agent.node_id,
            )
            skill_path = os.path.join(skills_dir, "SKILL.md")
            with open(skill_path, "w") as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error("Skill inject failed for %s: %s", agent.agent_id, e)
            return False

    # ── Helpers ───────────────────────────────────────

    def _resolve_config_dir(self, agent: AgentProfile) -> str:
        """Get the config directory for an agent."""
        if agent.config_path:
            if os.path.isfile(agent.config_path):
                return os.path.dirname(agent.config_path)
            if os.path.isdir(agent.config_path):
                return agent.config_path

        # Fallback: derive from framework name
        framework_dirs = {
            "hermes": "~/.hermes",
            "wukong": "~/.wukong",
            "openclaw": "~/.openclaw",
            "copaw": "~/.copaw",
            "qclaw": "~/.qclaw",
            "hiclaw": "~/.hiclaw",
            "easyclaw": "~/.easyclaw",
            "work_buddy": "~/.workbuddy",
            "claude_code": "~/.claude",
        }
        default = framework_dirs.get(agent.framework, f"~/.{agent.framework}")
        return os.path.expanduser(default)

    @staticmethod
    def _find_yaml_config(directory: str) -> str:
        """Find config.yaml or config.yml in directory."""
        for name in ["config.yaml", "config.yml"]:
            path = os.path.join(directory, name)
            if os.path.exists(path):
                return path
        return ""
