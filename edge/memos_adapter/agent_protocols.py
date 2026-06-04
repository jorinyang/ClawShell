"""Agent-specific protocol adapters for MemOS Cloud integration.

Each adapter knows:
  1. Where the agent's config file lives
  2. How to inject MCP server config for that agent
  3. Agent-specific memory hooks (recall before reply, store after)

Supported agents: OpenClaw, Hermes, Wukong, Codex, Claude Code,
                 WorkBuddy, HiClaw, CoPaw, QClaw, OpenHuman
"""

from __future__ import annotations
import os, json, yaml
from pathlib import Path
from typing import Optional, Dict, List, Callable


# ═══════════════════════════════════════════════════════════════════
# Agent Protocol Registry
# ═══════════════════════════════════════════════════════════════════

class AgentProtocol:
    """Base protocol — defines how an agent talks to MemOS Cloud."""

    agent_id: str = ""
    config_paths: List[str] = []
    config_format: str = "json"  # json | yaml | toml

    def detect(self) -> bool:
        """Check if this agent is installed."""
        for p in self.config_paths:
            if Path(os.path.expanduser(p)).exists():
                return True
        return False

    def get_config_path(self) -> Optional[str]:
        for p in self.config_paths:
            expanded = os.path.expanduser(p)
            if Path(expanded).exists():
                return expanded
        return None

    def inject_mcp(self, server_name: str, command: str, args: List[str],
                   env: Optional[Dict[str, str]] = None) -> bool:
        """Inject MCP server config into agent. Subclass must override."""
        raise NotImplementedError

    def read_config(self) -> dict:
        path = self.get_config_path()
        if not path:
            return {}
        with open(path) as f:
            if self.config_format == "yaml":
                return yaml.safe_load(f) or {}
            return json.load(f)


# ═══════════════════════════════════════════════════════════════════
# Agent Implementations
# ═══════════════════════════════════════════════════════════════════

class HermesProtocol(AgentProtocol):
    agent_id = "hermes"
    config_paths = ["~/.hermes/config.yaml", "~/.hermes/config.yml"]
    config_format = "yaml"

    def inject_mcp(self, server_name, command, args, env=None) -> bool:
        path = self.get_config_path()
        if not path:
            return False
        cfg = self.read_config()
        if "mcp_servers" not in cfg:
            cfg["mcp_servers"] = {}
        cfg["mcp_servers"][server_name] = {
            "command": command,
            "args": args,
        }
        if env:
            cfg["mcp_servers"][server_name]["env"] = env
        with open(path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
        return True


class WukongProtocol(AgentProtocol):
    agent_id = "wukong"
    config_paths = []  # Dynamic: found via detector
    config_format = "json"

    def detect(self) -> bool:
        """Wukong config is in Windows User directory, detected by path pattern."""
        base = "/mnt/c/Users"
        for user_dir in Path(base).iterdir() if Path(base).exists() else []:
            pattern = user_dir / ".real" / "users"
            if pattern.exists():
                for uid_dir in pattern.iterdir():
                    mcp = uid_dir / ".mcp" / "mcpServerConfig.json"
                    if mcp.exists():
                        self.config_paths = [str(mcp)]
                        return True
        return False

    def inject_mcp(self, server_name, command, args, env=None) -> bool:
        path = self.get_config_path()
        if not path:
            return False
        cfg = self.read_config()
        if "mcpServers" not in cfg:
            cfg["mcpServers"] = {}
        cfg["mcpServers"][server_name] = {
            "command": command,
            "args": args,
        }
        with open(path, "w") as f:
            json.dump(cfg, f, indent=2)
        return True


class CodexProtocol(AgentProtocol):
    agent_id = "codex"
    config_paths = [
        "~/.codex/config.toml",
        "/mnt/c/Users/Aorus/.codex/config.toml",
    ]
    config_format = "toml"

    def inject_mcp(self, server_name, command, args, env=None) -> bool:
        path = self.get_config_path()
        if not path:
            return False
        lines = []
        with open(path) as f:
            lines = f.readlines()

        # Append MCP server config at end
        section = f'\n[mcp_servers.{server_name}]\n'
        section += f'command = "{command}"\n'
        section += f'args = {json.dumps(args)}\n'
        section += 'startup_timeout_sec = 120\n'
        if env:
            section += f'\n[mcp_servers.{server_name}.env]\n'
            for k, v in env.items():
                section += f'{k} = "{v}"\n'

        with open(path, "a") as f:
            f.write(section)
        return True


class OpenClawProtocol(AgentProtocol):
    agent_id = "openclaw"
    config_paths = ["~/.openclaw/config.yaml", "~/.openclaw/config.yml"]
    config_format = "yaml"

    def inject_mcp(self, server_name, command, args, env=None) -> bool:
        path = self.get_config_path()
        if not path:
            return False
        cfg = self.read_config()
        if "mcp_servers" not in cfg:
            cfg["mcp_servers"] = {}
        cfg["mcp_servers"][server_name] = {
            "command": command,
            "args": args,
        }
        if env:
            cfg["mcp_servers"][server_name]["env"] = env
        with open(path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
        return True


class ClaudeCodeProtocol(AgentProtocol):
    agent_id = "claude_code"
    config_paths = [
        "~/.claude/claude_desktop_config.json",
        "/mnt/c/Users/Aorus/AppData/Roaming/Claude/claude_desktop_config.json",
    ]
    config_format = "json"

    def inject_mcp(self, server_name, command, args, env=None) -> bool:
        path = self.get_config_path()
        if not path:
            return False
        cfg = self.read_config()
        if "mcpServers" not in cfg:
            cfg["mcpServers"] = {}
        cfg["mcpServers"][server_name] = {
            "command": command,
            "args": args,
        }
        with open(path, "w") as f:
            json.dump(cfg, f, indent=2)
        return True


# ── Generic MCP agents (same pattern) ──

class GenericYAMLAgent(AgentProtocol):
    """For WorkBuddy, HiClaw, CoPaw, QClaw, OpenHuman — YAML config agents."""
    agent_id = "generic_yaml"
    config_format = "yaml"

    def __init__(self, agent_id: str, config_paths: List[str]):
        self.agent_id = agent_id
        self.config_paths = config_paths

    def inject_mcp(self, server_name, command, args, env=None) -> bool:
        path = self.get_config_path()
        if not path:
            return False
        cfg = self.read_config()
        cfg.setdefault("mcp_servers", {})[server_name] = {
            "command": command, "args": args,
        }
        if env:
            cfg["mcp_servers"][server_name]["env"] = env
        with open(path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
        return True


# ═══════════════════════════════════════════════════════════════════
# Registry & Factory
# ═══════════════════════════════════════════════════════════════════

ALL_PROTOCOLS: List[AgentProtocol] = [
    HermesProtocol(),
    WukongProtocol(),
    CodexProtocol(),
    OpenClawProtocol(),
    ClaudeCodeProtocol(),
    GenericYAMLAgent("workbuddy", ["~/.workbuddy/config.yaml", "/mnt/c/Users/Aorus/.workbuddy/config.yaml"]),
    GenericYAMLAgent("hiclaw", ["~/.hiclaw/config.yaml", "/mnt/c/Users/Aorus/.hiclaw/config.yaml"]),
    GenericYAMLAgent("copaw", ["~/.copaw/config.yaml", "/mnt/c/Users/Aorus/.copaw/config.yaml"]),
    GenericYAMLAgent("qclaw", ["~/.qclaw/config.yaml", "/mnt/c/Users/Aorus/.qclaw/config.yaml"]),
    GenericYAMLAgent("openhuman", ["~/.openhuman/config.yaml", "/mnt/c/Users/Aorus/.openhuman/config.yaml"]),
    GenericYAMLAgent("cline", ["~/.cline/config.yaml", "/mnt/c/Users/Aorus/.cline/config.yaml"]),
    GenericYAMLAgent("cursor", ["~/.cursor/config.yaml", "/mnt/c/Users/Aorus/.cursor/config.yaml"]),
]


def detect_installed_agents() -> List[AgentProtocol]:
    """Return protocols for all detected agents."""
    return [p for p in ALL_PROTOCOLS if p.detect()]


def inject_to_all(server_name: str, command: str, args: List[str],
                  env: Optional[Dict[str, str]] = None) -> List[str]:
    """Inject MCP config to all detected agents. Returns list of agent_ids injected."""
    injected = []
    for proto in ALL_PROTOCOLS:
        try:
            if proto.detect():
                proto.inject_mcp(server_name, command, args, env)
                injected.append(proto.agent_id)
        except Exception:
            pass  # Skip agents where config injection fails
    return injected
