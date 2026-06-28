"""Agent scanner — discovers individual agent instances within frameworks.

v3.0: Goes beyond framework-level detection to identify specific Agent instances.
Parses config files of each framework to discover: agent profiles, capabilities,
MCP server configs, skills, and injection status.
"""

from __future__ import annotations
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

from shared.types import (
    AgentProfile, InjectionProfile, InjectionType,
)

logger = logging.getLogger(__name__)


class AgentScanner:
    """Scans AI agent frameworks and discovers individual Agent instances.

    Supports: Hermes, Wukong, OpenClaw, Claude Code (IDE), and more.
    Each discovered agent gets an AgentProfile with injection status.
    """

    def __init__(self):
        self._discovered: List[AgentProfile] = []

    # ── Public API ───────────────────────────────────

    def scan_all(self) -> List[AgentProfile]:
        """Scan all known frameworks and return discovered agents."""
        self._discovered = []
        self._scan_hermes()
        self._scan_wukong()
        self._scan_openclaw()
        self._scan_claude_code()
        self._scan_others()
        return self._discovered

    def scan_framework(self, framework: str) -> List[AgentProfile]:
        """Scan a specific framework only."""
        scanners = {
            "hermes": self._scan_hermes,
            "wukong": self._scan_wukong,
            "openclaw": self._scan_openclaw,
            "claude_code": self._scan_claude_code,
        }
        fn = scanners.get(framework)
        if fn:
            fn()
        return [a for a in self._discovered if a.framework == framework]

    # ── Hermes Agent Discovery ───────────────────────

    def _scan_hermes(self):
        root = os.path.expanduser("~/.hermes")
        if not os.path.isdir(root):
            return

        config_path = os.path.join(root, "config.yaml")
        if not os.path.exists(config_path):
            config_path = os.path.join(root, "config.yml")

        cfg = self._read_yaml(config_path)
        agents = self._parse_hermes_agents(cfg, root)
        for agent_data in agents:
            profile = AgentProfile(
                agent_id=f"hermes:{agent_data['name']}",
                framework="hermes",
                agent_type="framework",
                display_name=agent_data.get("display_name", agent_data["name"]),
                config_path=config_path,
                capabilities=agent_data.get("capabilities", []),
                skills=self._scan_hermes_skills(root),
                mcp_servers=self._scan_hermes_mcp(root, cfg),
                injection_status=self._check_hermes_injection(root, cfg),
                status="online" if self._is_process_running("hermes") else "offline",
                node_id=os.environ.get("CLAWSHELL_NODE_ID", ""),
                user_id=os.environ.get("CLAWSHELL_USER_ID", ""),
            )
            self._discovered.append(profile)

        # If no agents defined, create one from root config
        if not agents:
            profile = AgentProfile(
                agent_id=f"hermes:default",
                framework="hermes",
                agent_type="framework",
                display_name="Hermes Default",
                config_path=config_path,
                capabilities=self._infer_hermes_capabilities(cfg),
                skills=self._scan_hermes_skills(root),
                mcp_servers=self._scan_hermes_mcp(root, cfg),
                injection_status=self._check_hermes_injection(root, cfg),
                status="online" if self._is_process_running("hermes") else "offline",
                node_id=os.environ.get("CLAWSHELL_NODE_ID", ""),
                user_id=os.environ.get("CLAWSHELL_USER_ID", ""),
            )
            self._discovered.append(profile)

    def _parse_hermes_agents(self, cfg: dict, root: str) -> List[dict]:
        """Parse agent definitions from Hermes config."""
        agents = []
        if not cfg:
            return agents

        # Hermes config structure: agents: { name: { ... } }
        agents_cfg = cfg.get("agents", {})
        if isinstance(agents_cfg, dict):
            for name, agent_cfg in agents_cfg.items():
                if isinstance(agent_cfg, dict):
                    agents.append({
                        "name": name,
                        "display_name": agent_cfg.get("name", name),
                        "capabilities": agent_cfg.get("capabilities", []),
                    })
        return agents

    def _scan_hermes_skills(self, root: str) -> List[str]:
        skills_dir = os.path.join(root, "skills")
        if not os.path.isdir(skills_dir):
            return []
        skills = []
        for entry in os.listdir(skills_dir):
            skill_path = os.path.join(skills_dir, entry)
            if os.path.isdir(skill_path):
                md = os.path.join(skill_path, "SKILL.md")
                if os.path.exists(md):
                    skills.append(entry)
        return skills

    def _scan_hermes_mcp(self, root: str, cfg: dict) -> List[str]:
        """Discover MCP servers configured in Hermes."""
        servers = []
        # Check mcp.json or mcpServerConfig.json
        for mcp_file in ["mcp.json", "mcpServerConfig.json", "mcp_config.json"]:
            mcp_path = os.path.join(root, mcp_file)
            if os.path.exists(mcp_path):
                try:
                    with open(mcp_path) as f:
                        mcp_cfg = json.load(f)
                    if isinstance(mcp_cfg, dict):
                        mcp_servers = mcp_cfg.get("mcpServers", mcp_cfg)
                        if isinstance(mcp_servers, dict):
                            servers.extend(mcp_servers.keys())
                except Exception:
                    pass

        # Also check config.yaml for mcp section
        if cfg and "mcp" in cfg:
            mcp_cfg = cfg["mcp"]
            if isinstance(mcp_cfg, dict):
                servers.extend(mcp_cfg.keys())

        return list(set(servers))

    def _check_hermes_injection(self, root: str, cfg: dict) -> InjectionProfile:
        """Check 5 injection statuses for Hermes."""
        profile = InjectionProfile()

        # MCP: check if ClawShell MCP server registered
        mcp_file = os.path.join(root, "mcp.json")
        if os.path.exists(mcp_file):
            try:
                with open(mcp_file) as f:
                    mcp_cfg = json.load(f)
                servers = mcp_cfg.get("mcpServers", {})
                if "clawshell" in servers:
                    profile.mcp = True
            except Exception:
                pass

        # Hook: check if clawshell hook registered in config
        if cfg:
            hooks = cfg.get("hooks", cfg.get("event_hooks", []))
            if isinstance(hooks, list):
                for hook in hooks:
                    if isinstance(hook, dict) and "clawshell" in str(hook).lower():
                        profile.hook = True
                        break

        # Config: check config.yaml for clawshell section
        if cfg and cfg.get("clawshell", {}).get("enabled"):
            profile.config = True

        # Loop Skill: check for clawshell cron/loop config
        if cfg:
            cron = cfg.get("cron", cfg.get("loop_skills", cfg.get("scheduled_tasks", {})))
            if isinstance(cron, dict) and "clawshell" in str(cron).lower():
                profile.loop_skill = True

        # Skill: check for clawshell SKILL.md
        skill_md = os.path.join(root, "skills", "clawshell", "SKILL.md")
        if os.path.exists(skill_md):
            profile.skill = True

        return profile

    def _infer_hermes_capabilities(self, cfg: dict) -> List[str]:
        """Infer capabilities from Hermes config (role, tools, skills)."""
        caps = set()
        if not cfg:
            return []
        role = cfg.get("role", cfg.get("agent_role", ""))
        if "code" in str(role).lower():
            caps.add("code")
        if "review" in str(role).lower():
            caps.add("review")
        if "test" in str(role).lower():
            caps.add("test")
        # Tools imply capabilities
        tools = cfg.get("tools", cfg.get("enabled_tools", []))
        if isinstance(tools, list):
            for t in tools:
                if isinstance(t, str):
                    caps.add(t.lower())
        return sorted(caps)

    # ── Wukong Agent Discovery ────────────────────────

    def _scan_wukong(self):
        root = os.path.expanduser("~/.wukong")
        if not os.path.isdir(root):
            return

        users_dir = os.path.join(root, "users")
        if os.path.isdir(users_dir):
            for user_dir in os.listdir(users_dir):
                user_path = os.path.join(users_dir, user_dir)
                if not os.path.isdir(user_path):
                    continue
                self._scan_wukong_user(user_path)

        config_path = os.path.join(root, "config.yaml")
        if os.path.exists(config_path):
            profile = AgentProfile(
                agent_id=f"wukong:{user_dir}" if os.path.isdir(users_dir) else "wukong:default",
                framework="wukong",
                agent_type="framework",
                display_name=user_dir if os.path.isdir(users_dir) else "Wukong Default",
                config_path=config_path,
                capabilities=[],
                skills=[],
                mcp_servers=self._scan_wukong_mcp(root),
                injection_status=InjectionProfile(),
                status="online" if self._is_process_running("wukong") else "offline",
            )
            self._discovered.append(profile)

    def _scan_wukong_user(self, user_path: str):
        mcp_dir = os.path.join(user_path, ".mcp")
        if not os.path.isdir(mcp_dir):
            return
        mcp_cfg = os.path.join(mcp_dir, "mcp.json")
        if not os.path.exists(mcp_cfg):
            return
        try:
            with open(mcp_cfg) as f:
                cfg = json.load(f)
        except Exception:
            return

        servers = cfg.get("mcpServers", {})
        user_name = os.path.basename(user_path)
        profile = AgentProfile(
            agent_id=f"wukong:{user_name}",
            framework="wukong",
            agent_type="framework",
            display_name=user_name,
            config_path=mcp_cfg,
            capabilities=list(servers.keys()),
            skills=[],
            mcp_servers=list(servers.keys()),
            injection_status=self._check_wukong_injection(servers),
            status="online" if self._is_process_running("wukong") else "offline",
        )
        self._discovered.append(profile)

    def _scan_wukong_mcp(self, root: str) -> List[str]:
        mcp_file = os.path.join(root, "mcp.json")
        if not os.path.exists(mcp_file):
            return []
        try:
            with open(mcp_file) as f:
                cfg = json.load(f)
            return list(cfg.get("mcpServers", {}).keys())
        except Exception:
            return []

    def _check_wukong_injection(self, servers: dict) -> InjectionProfile:
        p = InjectionProfile()
        if "clawshell" in servers:
            p.mcp = True
        return p

    # ── OpenClaw Agent Discovery ──────────────────────

    def _scan_openclaw(self):
        for path in ["~/.openclaw", "~/.real"]:
            root = os.path.expanduser(path)
            if not os.path.isdir(root):
                continue
            config_path = os.path.join(root, "config.yaml")
            cfg = self._read_yaml(config_path) if os.path.exists(config_path) else {}
            agents = cfg.get("agents", {})
            if isinstance(agents, dict):
                for name, agent_cfg in agents.items():
                    profile = AgentProfile(
                        agent_id=f"openclaw:{name}",
                        framework="openclaw",
                        agent_type="framework",
                        display_name=agent_cfg.get("name", name) if isinstance(agent_cfg, dict) else name,
                        config_path=config_path,
                        capabilities=agent_cfg.get("capabilities", []) if isinstance(agent_cfg, dict) else [],
                        skills=[],
                        mcp_servers=self._scan_openclaw_mcp(root),
                        injection_status=InjectionProfile(),
                        status="online" if self._is_process_running("openclaw") else "offline",
                    )
                    self._discovered.append(profile)

    def _scan_openclaw_mcp(self, root: str) -> List[str]:
        mcp_file = os.path.join(root, "mcp.json")
        if not os.path.exists(mcp_file):
            return []
        try:
            with open(mcp_file) as f:
                cfg = json.load(f)
            return list(cfg.get("mcpServers", {}).keys())
        except Exception:
            return []

    # ── Claude Code (IDE) Agent Discovery ──────────────

    def _scan_claude_code(self):
        claude_dir = os.path.expanduser("~/.claude")
        if not os.path.isdir(claude_dir):
            return

        # Project-level Claude agents
        projects_dir = os.path.join(claude_dir, "projects")
        if os.path.isdir(projects_dir):
            for proj in os.listdir(projects_dir):
                proj_path = os.path.join(projects_dir, proj)
                if os.path.isdir(proj_path):
                    mcp_file = os.path.join(proj_path, "mcp.json")
                    mcp_servers = []
                    if os.path.exists(mcp_file):
                        try:
                            with open(mcp_file) as f:
                                mcp_servers = list(json.load(f).get("mcpServers", {}).keys())
                        except Exception:
                            pass

                    profile = AgentProfile(
                        agent_id=f"claude_code:{proj}",
                        framework="claude_code",
                        agent_type="ide",
                        display_name=f"Claude Code ({proj})",
                        config_path=os.path.join(proj_path, "settings.json"),
                        capabilities=self._infer_claude_capabilities(proj_path),
                        skills=[],
                        mcp_servers=mcp_servers,
                        injection_status=InjectionProfile(
                            mcp=("clawshell" in mcp_servers),
                        ),
                        status="offline",
                    )
                    self._discovered.append(profile)

    def _infer_claude_capabilities(self, proj_path: str) -> List[str]:
        caps = ["code", "chat"]
        if os.path.exists(os.path.join(proj_path, ".git")):
            caps.append("git")
        return caps

    # ── Other Frameworks ──────────────────────────────

    def _scan_others(self):
        """Quick scan of less common frameworks."""
        frameworks = [
            ("copaw", "~/.copaw", "framework"),
            ("qclaw", "~/.qclaw", "framework"),
            ("hiclaw", "~/.hiclaw", "framework"),
            ("easyclaw", "~/.easyclaw", "framework"),
            ("work_buddy", "~/.workbuddy", "framework"),
        ]
        for name, path, atype in frameworks:
            root = os.path.expanduser(path)
            if os.path.isdir(root):
                profile = AgentProfile(
                    agent_id=f"{name}:default",
                    framework=name,
                    agent_type=atype,
                    display_name=f"{name} Default",
                    config_path=root,
                    capabilities=[],
                    skills=[],
                    mcp_servers=[],
                    injection_status=InjectionProfile(),
                    status="online" if self._is_process_running(name) else "offline",
                )
                self._discovered.append(profile)

    # ── Utilities ─────────────────────────────────────

    @staticmethod
    def _read_yaml(path: str) -> dict:
        if not path or not os.path.exists(path):
            return {}
        try:
            import yaml
            with open(path) as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    @staticmethod
    def _is_process_running(name: str) -> bool:
        try:
            import psutil
            for proc in psutil.process_iter(['name', 'cmdline']):
                try:
                    cmdline = " ".join(proc.info.get('cmdline', []) or []).lower()
                    if name.lower() in cmdline:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            pass
        return False
