"""Claude Code CLI bridge."""

from edge.ide_bridge.base import BaseIDEBridge, IDETask, IDEResult
import time


class ClaudeCodeBridge(BaseIDEBridge):
    IDE_NAME = "claude_code"
    CLI_COMMAND = "claude"

    def detect(self) -> bool:
        return self._check_command("claude")

    def get_capabilities(self) -> list:
        return ["code", "debug", "refactor", "review", "test", "explain", "architect"]

    def invoke(self, task: IDETask) -> IDEResult:
        start = time.time()

        if not self.detect():
            return IDEResult(
                task_id=task.task_id, ide_name=self.IDE_NAME,
                success=False, error="Claude Code CLI not installed",
                duration_seconds=time.time() - start,
            )

        prompt = task.description
        if task.context:
            prompt = f"{task.context}\n\n---\n\nTask: {prompt}"

        cmd = ["claude", "--print", "--output-format", "text", prompt]
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


class KimiCodeBridge(BaseIDEBridge):
    """Kimi Code agent CLI bridge."""
    IDE_NAME = "kimi_code"
    CLI_COMMAND = "kimi"

    def detect(self) -> bool:
        return self._check_command("kimi")

    def get_capabilities(self) -> list:
        return ["code", "debug", "explain"]

    def invoke(self, task: IDETask) -> IDEResult:
        start = time.time()

        if not self.detect():
            return IDEResult(
                task_id=task.task_id, ide_name=self.IDE_NAME,
                success=False, error="Kimi Code CLI not installed",
                duration_seconds=time.time() - start,
            )

        cmd = ["kimi", "agent", task.description]
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


class DeepSeekTUIBridge(BaseIDEBridge):
    """DeepSeek TUI CLI bridge."""
    IDE_NAME = "deepseek_tui"
    CLI_COMMAND = "deepseek"

    def detect(self) -> bool:
        return self._check_command("deepseek")

    def get_capabilities(self) -> list:
        return ["code", "debug", "explain", "review"]

    def invoke(self, task: IDETask) -> IDEResult:
        start = time.time()

        if not self.detect():
            return IDEResult(
                task_id=task.task_id, ide_name=self.IDE_NAME,
                success=False, error="DeepSeek TUI not installed",
                duration_seconds=time.time() - start,
            )

        # DeepSeek TUI uses --non-interactive for CLI mode
        cmd = ["deepseek", "--non-interactive", "--prompt", task.description]
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
