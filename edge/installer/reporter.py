"""SelfCheckReporter — post-install system self-check and capability report."""
from __future__ import annotations
import json, time, textwrap
from pathlib import Path
from typing import Optional
from edge.installer.detector import SystemDetector, SystemInfo, AgentDetection, IDEDetection

class SelfCheckReporter:
    """Run post-install self-check and generate capability report."""

    def __init__(self, clawshell_dir: Optional[str] = None):
        self.clawshell_dir = Path(clawshell_dir) if clawshell_dir else Path.home() / ".clawshell"
        self.detector = SystemDetector()

    def run_self_check(self) -> dict:
        """Run full self-check. Returns report dict."""
        report = {
            "timestamp": time.time(),
            "installation_path": str(self.clawshell_dir),
            "checks": {},
            "system": {},
            "agents": [],
            "ides": [],
            "capabilities": [],
            "configuration": {},
            "status": "unknown",
        }
        info = self.detector.detect_all()

        # System checks
        report["system"] = {
            "os": info.os_name,
            "version": info.os_version,
            "arch": info.arch,
            "python": info.python_version,
            "cpu": info.cpu_count,
            "memory_gb": info.memory_gb,
            "disk_free_gb": info.disk_free_gb,
        }

        # Component checks
        checks = {
            "clawshell_edge": self._check_edge_installed(),
            "mcp_edge_server": self._check_module("edge.mcp.edge_server"),
            "mcp_memory_server": self._check_module("edge.mcp.memory_server"),
            "mem_palace": self._check_mempalace(),
            "memos_cloud": self._check_memos_cloud(),
            "sync_daemon": self._check_module("edge.sync.sync_daemon"),
            "exoskeleton": self._check_exoskeleton_layers(),
            "cloud_connectivity": self._check_cloud(),
            "python_version": self._check_python(),
        }
        report["checks"] = checks
        all_ok = all(v for v in checks.values() if isinstance(v, bool))

        # Agent detection
        report["agents"] = [{
            "name": a.name,
            "installed": a.installed,
            "config_path": a.config_path,
            "clawshell_configured": a.claWSHELL_configured,
        } for a in info.agents]

        # IDE detection
        report["ides"] = [{
            "name": i.name,
            "installed": i.installed,
            "path": i.path,
        } for i in info.ides]

        # Capabilities
        report["capabilities"] = self._build_capabilities(info)

        # Configuration
        report["configuration"] = self._check_config()

        report["status"] = "healthy" if all_ok else "degraded"
        return report

    def generate_report(self, as_markdown: bool = True) -> str:
        """Generate human-readable report."""
        report = self.run_self_check()
        if as_markdown:
            return self._markdown_report(report)
        return json.dumps(report, indent=2, ensure_ascii=False)

    # ── Checks ──────────────────────────────────────────────────────

    def _check_edge_installed(self) -> bool:
        return (self.clawshell_dir / "edge").is_dir()

    def _check_module(self, mod_path: str) -> bool:
        try:
            import importlib
            importlib.import_module(mod_path)
            return True
        except Exception:
            return False

    def _check_mempalace(self) -> bool:
        try:
            import mempalace
            return True
        except ImportError:
            pass
        return (Path.home() / ".mempalace").is_dir()

    def _check_memos_cloud(self) -> bool:
        try:
            result = __import__("subprocess").run(
                ["pip", "show", "memos-local-plugin"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            pass
        return (Path.home() / ".hermes/plugins/memos-local-plugin").is_dir()

    def _check_exoskeleton_layers(self) -> bool:
        layers = ["layer1", "layer2", "layer3", "layer4"]
        base = self.clawshell_dir / "exoskeleton"
        return all((base / l).is_dir() for l in layers)

    def _check_cloud(self) -> bool:
        try:
            import urllib.request
            req = urllib.request.Request("http://47.239.71.174:8000/health", method="GET")
            resp = urllib.request.urlopen(req, timeout=5)
            return resp.status == 200
        except Exception:
            return False

    def _check_python(self) -> bool:
        import sys
        return sys.version_info >= (3, 10)

    def _check_config(self) -> dict:
        """Check .env and config files."""
        env_path = self.clawshell_dir / ".env"
        env_exists = env_path.exists()
        return {
            "env_file": str(env_path) if env_exists else "missing",
            "env_configured": env_exists,
        }

    # ── Capabilities ─────────────────────────────────────────────────

    def _build_capabilities(self, info: SystemInfo) -> list[dict]:
        caps = []

        # L1: Self-Awareness
        agent_count = sum(1 for a in info.agents if a.installed)
        if agent_count > 0:
            caps.append({"layer": "L1", "capability": "Self-Awareness",
                         "detail": f"Detected {agent_count} AI agents"})

        # L2: Self-Adaptation
        caps.append({"layer": "L2", "capability": "Self-Repair",
                     "detail": "Auto-detect failures + 4 repair strategies"})

        # L3: Self-Organization
        caps.append({"layer": "L3", "capability": "Task Orchestration",
                     "detail": "Global TaskBoard + Workflow Engine"})

        # L4: Multi-Agent Cluster
        if agent_count >= 1:
            caps.append({"layer": "L4", "capability": "Agent Mesh",
                         "detail": f"{agent_count} agents form collaborative mesh"})

        # MCP
        caps.append({"layer": "MCP", "capability": "MCP Protocol",
                     "detail": "STDIO MCP server with 19 tools (edge + memory)"})

        # Memory
        caps.append({"layer": "Memory", "capability": "Triple Memory",
                     "detail": "MemPalace + MemOS Local + MemOS Cloud"})

        # Cloud-Edge
        caps.append({"layer": "CloudEdge", "capability": "Cloud-Edge Sync",
                     "detail": "5-second sync cycle, 9-step protocol"})

        return caps

    # ── Markdown Report ──────────────────────────────────────────────

    def _markdown_report(self, report: dict) -> str:
        lines = []
        lines.append("# ClawShell Edge — Installation Report")
        lines.append("")
        lines.append(f"**Status:** `{report['status']}`")
        lines.append(f"**Installed at:** `{report['installation_path']}`")
        lines.append("")

        # System
        lines.append("## System Information")
        lines.append("| Property | Value |")
        lines.append("|----------|-------|")
        for k, v in report["system"].items():
            lines.append(f"| {k} | {v} |")
        lines.append("")

        # Component Checks
        lines.append("## Component Checks")
        lines.append("| Component | Status |")
        lines.append("|-----------|--------|")
        for comp, ok in report["checks"].items():
            status = "✅" if ok else "❌"
            lines.append(f"| {comp} | {status} |")
        lines.append("")

        # Agents
        if report["agents"]:
            lines.append("## Detected AI Agents")
            lines.append("| Agent | Installed | ClawShell Configured | Config Path |")
            lines.append("|-------|-----------|---------------------|-------------|")
            for a in report["agents"]:
                inst = "✅" if a["installed"] else "❌"
                cfg = "✅" if a["clawshell_configured"] else "—"
                lines.append(f"| {a['name']} | {inst} | {cfg} | {a.get('config_path', '—') or '—'} |")
            lines.append("")

        # IDEs
        if report["ides"]:
            lines.append("## Detected Coding IDEs")
            lines.append("| IDE | Installed |")
            lines.append("|-----|-----------|")
            for i in report["ides"]:
                lines.append(f"| {i['name']} | {'✅' if i['installed'] else '❌'} |")
            lines.append("")

        # Capabilities
        lines.append("## Enabled Capabilities")
        for cap in report["capabilities"]:
            lines.append(f"- **{cap['capability']}** [{cap['layer']}]: {cap['detail']}")
        lines.append("")

        # Next Steps
        lines.append("## Next Steps")
        lines.append("1. Start Edge daemon: `python3 -m edge.sync.sync_daemon`")
        lines.append("2. Verify Cloud connection: `python3 -m edge.mcp.edge_server --health`")
        lines.append("3. Register node: `curl -X POST http://47.239.71.174:8000/api/v1/nodes/register`")
        lines.append("4. Visit Dashboard: https://clawshell.club/login")

        return "\n".join(lines)
