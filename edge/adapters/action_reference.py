"""Action Reference Injector — Pre-action cloud reference for Edge agents.

Before any action execution, the Edge reads cloud insights and broadcasts,
injecting them as context reference files for the local agent framework.
If Cloud is unreachable, writes "autonomous mode" marker.
"""

from __future__ import annotations
import os
import json
import time
from typing import Optional, List, Dict


class ActionReferenceInjector:
    """Inject cloud insights as pre-action reference for agent frameworks."""

    def __init__(self, data_dir: str = "~/.clawshell-edge"):
        self._data_dir = os.path.expanduser(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)

    def get_latest_insights(self) -> List[dict]:
        """Get cached cloud insights."""
        cache = os.path.join(self._data_dir, "cloud_insights.json")
        if os.path.exists(cache):
            try:
                with open(cache) as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def get_latest_broadcasts(self) -> List[dict]:
        """Get cached cloud broadcasts."""
        cache = os.path.join(self._data_dir, "cloud_broadcasts.json")
        if os.path.exists(cache):
            try:
                with open(cache) as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def inject_to_workspace(self, target_path: str,
                            cloud_reachable: bool = True) -> Optional[str]:
        """Write action reference file to a target workspace.

        Args:
            target_path: Path to write the reference file (e.g., ~/.real/workspace/)
            cloud_reachable: Whether Cloud Hub is currently reachable

        Returns path of written file, or None on failure.
        """
        target = os.path.expanduser(target_path)
        os.makedirs(target, exist_ok=True)
        ref_file = os.path.join(target, "clawshell_action_reference.md")

        try:
            if cloud_reachable:
                insights = self.get_latest_insights()
                broadcasts = self.get_latest_broadcasts()

                content = _build_reference_md(insights, broadcasts)
            else:
                content = _build_autonomous_md()

            with open(ref_file, "w", encoding="utf-8") as f:
                f.write(content)

            return ref_file
        except Exception:
            return None


def _build_reference_md(insights: list, broadcasts: list) -> str:
    """Build action reference markdown from cloud data."""
    lines = [
        "# ClawShell Action Reference",
        f"> Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"> Source: Cloud Hub",
        "",
    ]

    if insights:
        lines.append("## Cloud Insights")
        lines.append("")
        for ins in insights[:5]:
            lines.append(f"### {ins.get('title', 'Insight')}")
            lines.append(f"Category: {ins.get('category', 'general')} | Confidence: {ins.get('confidence', 0)}")
            lines.append(f"\n{ins.get('content', '')[:500]}")
            if ins.get("action_suggestion"):
                lines.append(f"\n**Suggested Action**: {ins['action_suggestion']}")
            lines.append("")

    if broadcasts:
        lines.append("## Recent Broadcasts")
        lines.append("")
        for bc in broadcasts[:3]:
            lines.append(f"### {bc.get('title', 'Broadcast')}")
            lines.append(f"Type: {bc.get('broadcast_type', 'announcement')}")
            lines.append(f"\n{bc.get('content', '')[:300]}")
            lines.append("")

    if not insights and not broadcasts:
        lines.append("*No new insights or broadcasts from Cloud Hub.*")

    return "\n".join(lines)


def _build_autonomous_md() -> str:
    """Build autonomous mode marker."""
    return f"""# ClawShell Action Reference — AUTONOMOUS MODE

> Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
> Cloud Hub: **UNREACHABLE**

## Status

Cloud Hub is currently unreachable. Operating in **autonomous mode**.

- All decisions are made locally
- Events will be queued and synced when Cloud becomes available
- No cloud insights available — use local knowledge only

## Recommendations

1. Continue with local task execution
2. Cache all outputs for later sync
3. Check network connectivity to Cloud Hub
4. Retry connection on next sync cycle
"""
