"""OpenAI Codex CLI bridge."""

from edge.ide_bridge.base import BaseIDEBridge, IDETask, IDEResult
import time


class CodexBridge(BaseIDEBridge):
    IDE_NAME = "codex"
    CLI_COMMAND = "codex"

    def detect(self) -> bool:
        return self._check_command("codex")

    def get_capabilities(self) -> list:
        return ["code", "debug", "refactor", "review", "test", "explain"]

    def invoke(self, task: IDETask) -> IDEResult:
        start = time.time()

        if not self.detect():
            return IDEResult(
                task_id=task.task_id, ide_name=self.IDE_NAME,
                success=False, error="Codex CLI not installed",
                duration_seconds=time.time() - start,
            )

        # Build prompt
        prompt = f"Task: {task.description}"
        if task.context:
            prompt += f"\n\nContext: {task.context}"
        if task.files:
            prompt += f"\n\nRelevant files: {', '.join(task.files)}"

        cmd = ["codex", "exec", prompt]
        exit_code, stdout, stderr = self._run_command(
            cmd, cwd=task.working_dir or ".", timeout=task.timeout_seconds
        )

        return IDEResult(
            task_id=task.task_id,
            ide_name=self.IDE_NAME,
            success=(exit_code == 0),
            output=stdout[:5000],
            error=stderr[:2000],
            duration_seconds=time.time() - start,
        )


class CopilotBridge(BaseIDEBridge):
    """GitHub Copilot CLI bridge (via --acp protocol)."""
    IDE_NAME = "copilot"
    CLI_COMMAND = "copilot"

    def detect(self) -> bool:
        return self._check_command("copilot")

    def get_capabilities(self) -> list:
        return ["code", "explain", "suggest"]

    def invoke(self, task: IDETask) -> IDEResult:
        start = time.time()

        if not self.detect():
            return IDEResult(
                task_id=task.task_id, ide_name=self.IDE_NAME,
                success=False, error="Copilot CLI not installed",
                duration_seconds=time.time() - start,
            )

        prompt = task.description
        cmd = ["copilot", "--acp", "--stdio"]
        exit_code, stdout, stderr = self._run_command(
            cmd, cwd=task.working_dir or ".", timeout=task.timeout_seconds
        )

        return IDEResult(
            task_id=task.task_id,
            ide_name=self.IDE_NAME,
            success=(exit_code == 0),
            output=stdout[:5000],
            error=stderr[:2000],
            duration_seconds=time.time() - start,
        )
