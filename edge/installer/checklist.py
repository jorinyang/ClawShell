"""InstallationChecklist — interactive prerequisite validation."""
from __future__ import annotations
import os, sys, textwrap
from pathlib import Path
from typing import Callable, Optional

# ── LLM Model → Provider Auto-Detection ───────────────────────────────

# Provider defaults per model prefix (order matters: check most specific first)
LLM_PROVIDER_MAP: list[tuple[str, str, str]] = [
    # (model_prefix, provider, endpoint)
    # OpenAI-compatible endpoints (use /chat/completions):
    ("deepseek",          "deepseek",  "https://api.deepseek.com/v1"),
    ("gpt-",              "openai",    "https://api.openai.com/v1"),
    ("o1-",               "openai",    "https://api.openai.com/v1"),
    ("o3-",               "openai",    "https://api.openai.com/v1"),
    ("MiniMax-",          "minimax",   "https://api.minimax.chat/v1"),
    ("minimax-",          "minimax",   "https://api.minimax.chat/v1"),
    # Anthropic uses non-OpenAI-compatible API (/v1/messages, different format).
    # Requires an Anthropic adapter or compatibility proxy.
    ("claude-",           "anthropic", "https://api.anthropic.com"),
    ("anthropic/",        "anthropic", "https://api.anthropic.com"),
]

LLM_DEFAULT_MODEL = "deepseek-v4-pro"
LLM_KEY_ENV_MAP: dict[str, str] = {
    "deepseek":  "DEEPSEEK_API_KEY",
    "openai":    "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "minimax":   "MINIMAX_API_KEY",
}

def _detect_provider_from_model(model: str) -> tuple[str, str]:
    """Infer (provider, endpoint) from model name prefix. Falls back to deepseek."""
    model_lower = model.lower()
    for prefix, provider, endpoint in LLM_PROVIDER_MAP:
        if model_lower.startswith(prefix.lower()):
            return provider, endpoint
    return "deepseek", "https://api.deepseek.com/v1"

def _key_env_for_provider(provider: str) -> str:
    """Return the environment variable name for a given provider."""
    return LLM_KEY_ENV_MAP.get(provider, "DEEPSEEK_API_KEY")

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
        # Check all known env vars
        for env_var in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "MINIMAX_API_KEY"):
            val = os.environ.get(env_var, "")
            if val:
                return "*** (from env)"
        if self.interactive:
            model = input("  Model [default: deepseek-v4-pro]: ").strip()
            if not model:
                model = "deepseek-v4-pro"
            provider, endpoint = _detect_provider_from_model(model)
            ans = input("  API Key [sk-xxx]: ").strip()
            self.values["llm_provider"] = provider
            self.values["llm_model"] = model
            self.values["llm_endpoint"] = endpoint
            self.values["llm_api_key_env"] = _key_env_for_provider(provider)
            if ans:
                self.values["llm_api_key_raw"] = ans
                return f"{provider}/{model} *** (provided)"
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
        print("║                                                  ║")
        print("║ 💡 Recommended: Obsidian for multi-device         ║")
        print("║    knowledge sync via clawshell.club/couchdb     ║")
        print("║    → https://obsidian.md/download                ║")
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
