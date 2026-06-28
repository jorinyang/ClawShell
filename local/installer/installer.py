"""ClawShellEdgeInstaller — unified Edge installation engine."""
import os, sys, subprocess, time
from pathlib import Path
from typing import Optional
from local.installer.detector import SystemDetector
from local.installer.configurator import ConfigAutoInjector
from local.installer.checklist import InstallationChecklist
from local.installer.reporter import SelfCheckReporter

CLAWSHELL_REPO = "https://github.com/jorinyang/ClawShell.git"

class ClawShellEdgeInstaller:
    """Complete Edge installation orchestrator."""

    def __init__(self, workdir=None, cloud_url="http://47.239.71.174:8000",
                 interactive=True, skip_checklist=False):
        self.workdir = Path(workdir) if workdir else Path.home() / ".clawshell"
        self.cloud_url = cloud_url
        self.interactive = interactive
        self.skip_checklist = skip_checklist
        self.detector = SystemDetector()
        self.reporter = SelfCheckReporter(str(self.workdir))
        self.configurator = None
        self._env_values = {}

    def install(self):
        start = time.time()
        steps = {}
        print("")
        print("=" * 50)
        print("ClawShell Edge Installer v2.2.0")
        print("=" * 50)

        print("\n[1/6] Scanning system...")
        info = self.detector.detect_all()
        ac = sum(1 for a in info.agents if a.installed)
        ic = sum(1 for i in info.ides if i.installed)
        print(f"       OS: {info.os_name} | Python: {info.python_version}")
        print(f"       Agents: {ac} | IDEs: {ic}")
        steps["scan"] = "ok"

        if not self.skip_checklist:
            print("\n[2/6] Prerequisites...")
            chk = InstallationChecklist(workdir=str(self.workdir))
            if not chk.run():
                sys.exit(1)
            self._env_values = {k: v for k, v in chk.values.items() if v}
            self.workdir = chk.workdir
        steps["checklist"] = "ok"

        print("\n[3/6] Cloning ClawShell...")
        if not self._clone_repo(CLAWSHELL_REPO, str(self.workdir)):
            steps["clone"] = "failed"
            return self._report(steps, start)
        steps["clone"] = "ok"

        print("\n[4/6] Installing dependencies...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "pyyaml", "requests", "aiohttp"],
                           capture_output=True, timeout=120)
            steps["deps"] = "ok"
        except Exception:
            steps["deps"] = "partial"

        print("\n[5/6] Configuring agents...")
        self.configurator = ConfigAutoInjector(clawshell_dir=str(self.workdir))
        results = self.configurator.inject_all(info.agents)
        configured = [a for a, ok in results.items() if ok]
        print(f"       Injected: {configured if configured else 'none'}")
        steps["config"] = "ok" if configured else "none"

        # MemOS Cloud adapter — inject to all detected agents
        memos_key = self.checklist.values.get("MEMOS_API_KEY") or os.environ.get("MEMOS_API_KEY", "")
        if memos_key:
            print("       Installing MemOS Cloud adapter to all agents...")
            try:
                from local.memos_adapter.installer_hook import install_memos_to_all_agents
                memos_result = install_memos_to_all_agents(api_key=memos_key)
                print(f"       MemOS injected to: {memos_result['injected_agents']}")
                steps["memos"] = f"ok ({len(memos_result['injected_agents'])} agents)"
            except Exception as e:
                print(f"       MemOS skip: {e}")
                steps["memos"] = "skipped"
        else:
            steps["memos"] = "no-key"

        print("\n[6/6] Self-check...")
        report = self.reporter.run_self_check()
        print(f"       Status: {report['status']}")
        steps["self_check"] = report["status"]
        return self._report(steps, start)

    def _clone_repo(self, url, dest):
        dp = Path(dest)
        if dp.exists() and (dp / ".git").exists():
            print("       Already cloned, updating...")
            try:
                subprocess.run(["git", "-C", str(dp), "pull", "--ff-only"],
                               capture_output=True, timeout=30)
                return True
            except Exception:
                pass
        try:
            subprocess.run(["git", "clone", url, str(dp)], capture_output=False, timeout=120)
            return dp.exists()
        except Exception as e:
            print(f"       Clone error: {e}")
            return False

    def _report(self, steps, start_time):
        elapsed = round(time.time() - start_time, 1)
        all_ok = all(v == "ok" for v in steps.values())
        r = {
            "version": "2.2.0",
            "elapsed": elapsed,
            "steps": steps,
            "status": "complete" if all_ok else "partial",
            "path": str(self.workdir),
        }
        print("")
        print("=" * 50)
        print(f"Installation {'complete' if all_ok else 'partial'}")
        print(f"Time: {elapsed}s | Status: {r['status']}")
        print("=" * 50)
        return r
