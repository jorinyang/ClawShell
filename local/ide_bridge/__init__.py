"""IDE Bridge package — Agent CLI IDE integration (Harness Engineering)."""

from local.ide_bridge.base import BaseIDEBridge, IDETask, IDEResult
from local.ide_bridge.codex import CodexBridge, CopilotBridge
from local.ide_bridge.claude_code import (
    ClaudeCodeBridge, KimiCodeBridge, DeepSeekTUIBridge
)
from local.ide_bridge.orchestrator import IDEOrchestrator
from local.ide_bridge.sandbox import IDESandbox

# Auto-detect available bridges
ALL_BRIDGES = [
    CodexBridge(),
    ClaudeCodeBridge(),
    KimiCodeBridge(),
    DeepSeekTUIBridge(),
    CopilotBridge(),
]


def create_orchestrator() -> IDEOrchestrator:
    """Create an IDE orchestrator with all available bridges auto-registered."""
    orch = IDEOrchestrator()
    for bridge in ALL_BRIDGES:
        orch.register_bridge(bridge)
    return orch


def detect_ide_tools() -> list[str]:
    """Detect which Agent CLI IDEs are available."""
    available = []
    for bridge in ALL_BRIDGES:
        if bridge.detect():
            available.append(bridge.get_name())
    return available
from local.ide_bridge.kimi_code import KimiBridge
from local.ide_bridge.copilot import CopilotBridge
from local.ide_bridge.windsurf import WindsurfBridge