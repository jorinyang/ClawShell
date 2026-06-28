"""ConfigAutoInjector — inject ClawShell MCP config into detected agents."""
from __future__ import annotations
import json, yaml, shutil, tempfile
from pathlib import Path
from typing import Optional
from local.installer.detector import AgentDetection

# ── MCP config templates ─────────────────────────────────────────────

def _hermes_config() -> dict:
    return {
        "mcp_servers": {
            "clawshell-edge": {
                "command": "python3",
                "args": ["-m", "edge.mcp.edge_server"],
                "cwd": None,  # Will be filled at install time
                "enabled": True,
            },
            "clawshell-memory": {
                "command": "python3",  
                "args": ["-m", "edge.mcp.memory_server"],
                "cwd": None,
                "enabled": True,
            },
        }
    }

def _wukong_config(clawshell_dir: str) -> dict:
    return [
        {
            "name": "clawshell-edge",
            "type": "stdio",
            "command": "python3",
            "args": ["-m", "edge.mcp.edge_server"],
            "cwd": clawshell_dir,
            "env": {},
            "isActive": True,
        },
        {
            "name": "clawshell-memory",
            "type": "stdio",
            "command": "python3",
            "args": ["-m", "edge.mcp.memory_server"],
            "cwd": clawshell_dir,
            "env": {},
            "isActive": True,
        },
    ]

def _openclaw_config() -> dict:
    return {
        "mcp_servers": {
            "clawshell-edge": {
                "command": "python3",
                "args": ["-m", "edge.mcp.edge_server"],
                "enabled": True,
            },
            "clawshell-memory": {
                "command": "python3",
                "args": ["-m", "edge.mcp.memory_server"],
                "enabled": True,
            },
        }
    }

# ── Configurator ──────────────────────────────────────────────────────

class ConfigAutoInjector:
    """Auto-inject ClawShell MCP config into local agent configurations."""

    def __init__(self, clawshell_dir: Optional[str] = None):
        self.clawshell_dir = clawshell_dir or str(Path(__file__).resolve().parents[2])

    def inject_all(self, agents: list[AgentDetection]) -> dict[str, bool]:
        """Inject into all detected agents. Returns {agent: success}."""
        results = {}
        for agent in agents:
            if agent.installed and agent.config_path and not agent.claWSHELL_configured:
                results[agent.name] = self._inject(agent)
            else:
                results[agent.name] = agent.claWSHELL_configured
        return results

    def _inject(self, agent: AgentDetection) -> bool:
        handlers = {
            "hermes": self._inject_hermes,
            "wukong": self._inject_wukong,
            "openclaw": self._inject_openclaw,
            "cline": self._inject_vscode_mcp,
            "cursor": self._inject_cursor,
        }
        handler = handlers.get(agent.name)
        if handler and agent.config_path:
            return handler(agent.config_path)
        return False

    def _inject_hermes(self, config_path: str) -> bool:
        return self._inject_yaml(config_path, _hermes_config(), merge_key="mcp_servers")

    def _inject_openclaw(self, config_path: str) -> bool:
        return self._inject_yaml(config_path, _openclaw_config(), merge_key="mcp_servers")

    def _inject_wukong(self, config_path: str) -> bool:
        try:
            path = Path(config_path)
            if not path.exists():
                return False
            existing = json.loads(path.read_text())
            if isinstance(existing, list):
                existing = [s for s in existing if "clawshell" not in s.get("name", "").lower()]
                new_servers = _wukong_config(self.clawshell_dir)
                existing.extend(new_servers)
                # Backup
                shutil.copy2(path, path.with_suffix(".json.bak"))
                path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
                return True
        except Exception:
            pass
        return False

    def _inject_vscode_mcp(self, config_path: str) -> bool:
        return self._inject_json(config_path, _hermes_config())

    def _inject_cursor(self, config_path: str) -> bool:
        return self._inject_json(config_path, _hermes_config())

    def _inject_yaml(self, config_path: str, template: dict, merge_key: str) -> bool:
        try:
            path = Path(config_path)
            if not path.exists():
                return False
            content = path.read_text()
            existing = yaml.safe_load(content) or {}
            # Set cwd if None
            for svr in template.get(merge_key, {}).values():
                if svr.get("cwd") is None:
                    svr["cwd"] = self.clawshell_dir
            # Preserve existing keys not in our template
            if merge_key in existing and isinstance(existing[merge_key], dict):
                for key, val in template.get(merge_key, {}).items():
                    existing[merge_key][key] = val
            else:
                existing[merge_key] = template[merge_key]
            # Backup
            shutil.copy2(path, path.with_suffix(".yaml.bak"))
            path.write_text(yaml.dump(existing, default_flow_style=False, allow_unicode=True))
            return True
        except Exception:
            return False

    def _inject_json(self, config_path: str, template: dict) -> bool:
        try:
            path = Path(config_path)
            if not path.exists():
                return False
            existing = json.loads(path.read_text())
            mcp_servers = template.get("mcp_servers", {})
            if "mcpServers" not in existing:
                existing["mcpServers"] = {}
            for key, val in mcp_servers.items():
                if val.get("cwd") is None:
                    val["cwd"] = self.clawshell_dir
                existing["mcpServers"][key] = {"command": val["command"], "args": val["args"]}
            shutil.copy2(path, path.with_suffix(".json.bak"))
            path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
            return True
        except Exception:
            return False
