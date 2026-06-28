"""ClawShell Edge Installer — v2.2.0

Provides:
  - CLI mode: python3 -m edge.installer install
  - Agent mode: Provide AGENT_MODE.md to AI agent
  - One-liner: curl -fsSL https://clawshell.club/install.sh | bash

Auto-detects OS (Linux/macOS/Windows/WSL), local AI agents,
and coding IDEs. Installs ClawShell Edge with memory plugins
(MemPalace + MemOS Cloud) in one shot.
"""
from local.installer.installer import ClawShellEdgeInstaller
from local.installer.detector import SystemDetector
from local.installer.configurator import ConfigAutoInjector
from local.installer.checklist import InstallationChecklist
from local.installer.reporter import SelfCheckReporter

__all__ = [
    "ClawShellEdgeInstaller",
    "SystemDetector",
    "ConfigAutoInjector", 
    "InstallationChecklist",
    "SelfCheckReporter",
]
