"""Kimi Code CLI bridge."""

from edge.ide_bridge.base import BaseIDEBridge, IDETask, IDEResult
import time


class KimiBridge(BaseIDEBridge):
    IDE_NAME = "kimi_code"
    CLI_COMMAND = "kimi"

    def detect(self) -> bool:
        return self._check_command("kimi")

    def get_capabilities(self) -> list:
        return ["code", "debug", "refactor", "review", "test", "explain"]

    def invoke(self, task: IDETask) -> IDEResult:
        start = time.time()

        if not self.detect():
            return IDEResult(
                task_id=task.task_id, ide_name=self.IDE_NAME,
                success=False, error="Kimi Code CLI not installed",
                duration_seconds=time.time() - start,
            )

        prompt = f"Task: {task.description}"
        if task.context:
            prompt += f"\n\nContext: {task.context}"
        if task.files:
            prompt += f"\n\nRelevant files: {', '.join(task.files)}"

        cmd = ["kimi", "exec", prompt]
        exit_code, stdout, stderr = self._run_command(
            cmd, cwd=task.working_dir or ".", timeout=task.timeout_seconds
        )

        return IDEResult(
            task_id=task.task_id,
            ide_name=self.IDE_NAME,
            success=exit_code == 0,
            output=stdout[:4000],
            error=stderr[:2000] if stderr else None,
            duration_seconds=time.time() - start,
        )
