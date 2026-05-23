"""SystemDetector — unified OS + Agent + IDE auto-discovery."""
from __future__ import annotations
import os, sys, platform, shutil, subprocess, json, re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from edge.detector.system import detect_system_info
from edge.detector import detect_all_frameworks, FrameworkInfo

# ── Agent config paths ──────────────────────────────────────────────

KNOWN_AGENT_PATHS: dict[str, list[str]] = {
    # ── Primary agents (config paths) ──
    "hermes": [
        "~/.hermes/config.yaml",
        "~/.hermes/config.yml",
    ],
    "wukong": [
        "/mnt/c/Users/*/.real/users/*/.mcp/mcpServerConfig.json",
        str(Path.home() / ".real/users") + "/*/.mcp/mcpServerConfig.json",
    ],
    "openclaw": [
        "~/.openclaw/config.yaml",
        "~/.openclaw/config.yml",
        "~/.openclaw/openclaw.yaml",
    ],
    # ── OpenClaw ecosystem variants (install paths) ──
    "qclaw": [
        "~/.qclaw/",
    ],
    "copaw": [
        "~/.copaw/",
    ],
    "hiclaw": [
        "~/.hiclaw/",
    ],
    "easyclaw": [
        "~/.easyclaw/",
    ],
    "workbuddy": [
        "~/.workbuddy/",
        "~/.work-buddy/",
    ],
    # ── IDE agents ──
    "cline": [
        "~/.vscode-server/data/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
    ],
    "cursor": [
        "~/.cursor/mcp.json",
    ],
}

KNOWN_IDES: dict[str, list[str]] = {
    # ── Coding CLI agents ──
    "codex": ["codex", "npx @openai/codex"],
    "claude_code": ["claude", "npx @anthropic-ai/claude-code"],
    "kimi_code": ["kimi", "kimi-code"],
    "deepseek_tui": ["deepseek", "deepseek-coder", "deepseek-tui"],
    "copilot": ["gh copilot", "github-copilot-cli"],
    "windsurf": ["windsurf"],
    # ── Orchestrator + Sandbox ──
    "orchestrator": ["orchestrator"],
    "sandbox": ["sandbox"],
}

# ── Dataclasses ──────────────────────────────────────────────────────

@dataclass
class AgentDetection:
    name: str
    installed: bool = False
    config_path: Optional[str] = None
    config_exists: bool = False
    claWSHELL_configured: bool = False

@dataclass  
class IDEDetection:
    name: str
    installed: bool = False
    path: Optional[str] = None

@dataclass
class SystemInfo:
    os_name: str  # linux, macos, windows, wsl
    os_version: str
    arch: str
    python_version: str
    hostname: str
    cpu_count: int
    memory_gb: float
    disk_free_gb: float
    is_wsl: bool = False
    agents: list[AgentDetection] = field(default_factory=list)
    ides: list[IDEDetection] = field(default_factory=list)
    frameworks: list[FrameworkInfo] = field(default_factory=list)

# ── Detector ──────────────────────────────────────────────────────────

class SystemDetector:
    """Comprehensive system discovery: OS → Agents → IDEs → Frameworks."""
    
    def detect_all(self) -> SystemInfo:
        sys_data = detect_system_info()
        info = SystemInfo(
            os_name=sys_data.get("os_type", "unknown"),
            os_version=sys_data.get("os_full", ""),
            arch=sys_data.get("architecture", ""),
            python_version=sys_data.get("python_version", ""),
            hostname=sys_data.get("hostname", ""),
            cpu_count=sys_data.get("cpu_count", 0),
            memory_gb=round(sys_data.get("memory_total_mb", 0) / 1024, 1),
            disk_free_gb=sys_data.get("disk_free_gb", 0),
            is_wsl=sys_data.get("is_wsl", False),
        )
        info.agents = self._detect_agents()
        info.ides = self._detect_ides()
        try:
            info.frameworks = detect_all_frameworks()
        except Exception:
            pass
        return info

    def _detect_agents(self) -> list[AgentDetection]:
        results = []
        for agent_name, path_patterns in KNOWN_AGENT_PATHS.items():
            detection = AgentDetection(name=agent_name)
            for pattern in path_patterns:
                expanded = os.path.expanduser(pattern)
                candidate = self._resolve_path(expanded)
                if candidate:
                    detection.installed = True
                    detection.config_path = str(candidate)
                    detection.config_exists = True
                    detection.claWSHELL_configured = self._check_clawshell_config(candidate)
                    break
            results.append(detection)
        return results

    def _detect_ides(self) -> list[IDEDetection]:
        results = []
        for ide_name, commands in KNOWN_IDES.items():
            detection = IDEDetection(name=ide_name)
            for cmd in commands:
                path = shutil.which(cmd) or self._which_npx(cmd)
                if path:
                    detection.installed = True
                    detection.path = path
                    break
            results.append(detection)
        return results

    def _resolve_path(self, pattern: str) -> Optional[Path]:
        if "*" in pattern:
            try:
                import glob
                matches = glob.glob(pattern, recursive=True)
                return Path(matches[0]) if matches else None
            except Exception:
                pass
        p = Path(pattern)
        return p if p.exists() else None

    def _check_clawshell_config(self, config_path: Path) -> bool:
        try:
            content = config_path.read_text()
            return "clawshell" in content.lower()
        except Exception:
            return False

    @staticmethod
    def _which_npx(cmd: str) -> Optional[str]:
        if cmd.startswith("npx "):
            # NPX commands are available if npx exists
            if shutil.which("npx"):
                return f"npx:{cmd[4:]}"
        return None
