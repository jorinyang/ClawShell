"""IDE Bridge package — Agent CLI IDE integration (Harness Engineering)."""

from edge.ide_bridge.base import BaseIDEBridge, IDETask, IDEResult
from edge.ide_bridge.codex import CodexBridge, CopilotBridge
from edge.ide_bridge.claude_code import (
    ClaudeCodeBridge, KimiCodeBridge, DeepSeekTUIBridge
)
from edge.ide_bridge.orchestrator import IDEOrchestrator
from edge.ide_bridge.sandbox import IDESandbox

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
