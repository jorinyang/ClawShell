"""InstallationChecklist — interactive prerequisite validation."""
from __future__ import annotations
import os, sys, textwrap
from pathlib import Path
from typing import Callable, Optional

# ── Checklist ─────────────────────────────────────────────────────────

class InstallationChecklist:
    """Interactive pre-install checklist for ClawShell Edge installation.

    Steps:
      1. Python ≥ 3.10 check
      2. Git check
      3. GitHub account (confirm)
      4. MemPalace repo access (confirm)
      5. MemOS Cloud account + API Key
      6. LLM API Key (DeepSeek / OpenAI)
      7. Accept installation directory
      8. Confirm all prerequisites
    """

    def __init__(self, workdir: Optional[str] = None):
        self.workdir = Path(workdir) if workdir else Path.home() / ".clawshell"
        self.results: dict[str, bool] = {}
        self.values: dict[str, str] = {}
        self.interactive = sys.stdout.isatty()

    def run(self) -> bool:
        """Run all checklist items. Returns True if all pass."""
        self._print_header()
        checks: list[tuple[str, str, Callable[[], bool | str]]] = [
            ("python", "Python ≥ 3.10", self._check_python),
            ("git", "Git installed", self._check_git),
            ("github_account", "GitHub account", self._prompt_github_account),
            ("mempalace_access", "MemPalace repo access", self._prompt_mempalace),
            ("memos_api_key", "MemOS Cloud API Key", self._prompt_memos_key),
            ("llm_api_key", "LLM API Key (DeepSeek / OpenAI)", self._prompt_llm_key),
            ("install_dir", "Installation directory", self._prompt_install_dir),
            ("confirm_all", "Confirm all prerequisites", self._prompt_confirm),
        ]
        all_ok = True
        for step_id, label, check_fn in checks:
            result = check_fn()
            if isinstance(result, str):
                self.values[step_id] = result
                self.results[step_id] = True
                self._print_check(label, True, result)
            elif result:
                self.results[step_id] = True
                self._print_check(label, True, "✓")
            else:
                self.results[step_id] = False
                self._print_check(label, False, "✗")
                all_ok = False
        self._print_footer(all_ok)
        return all_ok

    # ── Checks ──────────────────────────────────────────────────────

    def _check_python(self) -> bool:
        v = sys.version_info
        return v.major >= 3 and v.minor >= 10

    def _check_git(self) -> bool:
        import shutil
        return shutil.which("git") is not None

    def _prompt_github_account(self) -> str | bool:
        val = os.environ.get("GITHUB_USER", "")
        if val:
            return val
        if self.interactive:
            val = input("  GitHub username: ").strip() or "skipped"
        return val or "skipped"

    def _prompt_mempalace(self) -> str | bool:
        val = os.environ.get("MEMPALACE_REPO", "github.com/mempalace/mempalace")
        if self.interactive:
            ans = input(f"  MemPalace repo [{val}]: ").strip()
            val = ans or val
        return val

    def _prompt_memos_key(self) -> str | bool:
        val = os.environ.get("MEMOS_API_KEY", "")
        if val:
            return "*** (from env)"
        if self.interactive:
            ans = input("  MemOS Cloud API Key [mpg-xxx]: ").strip()
            if ans:
                self.values["memos_api_key_raw"] = ans
                return "*** (provided)"
        return "skipped"

    def _prompt_llm_key(self) -> str | bool:
        val = os.environ.get("DEEPSEEK_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
        if val:
            return "*** (from env)"
        if self.interactive:
            ans = input("  LLM API Key [sk-xxx]: ").strip()
            if ans:
                self.values["llm_api_key_raw"] = ans
                return "*** (provided)"
        return "skipped"

    def _prompt_install_dir(self) -> str:
        val = os.environ.get("CLAWSHELL_HOME", str(self.workdir))
        if self.interactive:
            ans = input(f"  Install directory [{val}]: ").strip()
            val = ans or val
        self.workdir = Path(val)
        return str(self.workdir)

    def _prompt_confirm(self) -> bool:
        if not self.interactive:
            return True
        ans = input("\n  Proceed with installation? [Y/n]: ").strip().lower()
        return ans in ("", "y", "yes")

    # ── Display ──────────────────────────────────────────────────────

    def _print_header(self):
        print()
        print("╔══════════════════════════════════════════════════╗")
        print("║   ClawShell Edge — Installation Checklist       ║")
        print("╠══════════════════════════════════════════════════╣")
        print("║ Please complete these prerequisites first:       ║")
        print("║                                                  ║")
        print("║ 1. Register at https://memos.cloud               ║")
        print("║    → Get your MemOS Cloud API Key (mpg-xxx)      ║")
        print("║                                                  ║")
        print("║ 2. Get LLM API Key from DeepSeek or OpenAI        ║")
        print("║    → https://platform.deepseek.com/api_keys      ║")
        print("║    → https://platform.openai.com/api-keys        ║")
        print("║                                                  ║")
        print("║ 3. Access ClawShell repo:                        ║")
        print("║    → https://github.com/jorinyang/ClawShell      ║")
        print("╚══════════════════════════════════════════════════╝")
        print()

    def _print_check(self, label: str, ok: bool, detail: str = ""):
        symbol = "✓" if ok else "✗"
        print(f"  {symbol} {label:<40} {detail}")

    def _print_footer(self, all_ok: bool):
        print()
        if all_ok:
            print("══ All prerequisites confirmed. Starting installation...")
        else:
            print("══ Some prerequisites missing. Please fix and retry.")
        print()
