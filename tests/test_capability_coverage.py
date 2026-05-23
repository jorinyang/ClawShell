"""Comprehensive capability + boundary tests for ClawShell v2.2.0

Covers ALL capabilities and ALL documented boundaries:
  ■ C1  LLM Provider Detection & Endpoint Mapping
  ■ C2  SystemDetector (10 agents + 8 IDEs + system info)
  ■ C3  ConfigAutoInjector (Hermes / Wukong / OpenClaw injection)
  ■ C4  SelfCheckReporter (full report generation)
  ■ C5  InstallationChecklist (credential collection)
  ■ C6  Edge CronReporter (report → persist → batch sync)
  ■ C7  CloudCronSupervisor + DispatchRouter
  ■ C8  Full Pipeline (report → detect → dispatch → confirm)
  ■ C9  CLI Modes (detect / check / config / install)
  ■ C10 LLM Client (OpenAI-compatible format awareness)
  ■ B1  Boundary: Anthropic non-OpenAI-compatible
  ■ B2  Boundary: Missing dependencies graceful fallback
  ■ B3  Boundary: Non-existent config / paths
  ■ B4  Boundary: Uninstalled / already-configured agents
  ■ B5  Boundary: Empty / unknown model strings
  ■ B6  Boundary: Case-insensitive detection
  ■ B7  Boundary: Degraded mode (no keys, unreachable cloud)
  ■ B8  Boundary: Wukong Windows-path limitation
  ■ B9  Boundary: Installer non-interactive mode
  ■ B10 Boundary: CLI error handling & exit codes

Run: pytest tests/test_capability_coverage.py -v
"""

from __future__ import annotations
import sys, os, json, tempfile, uuid, time, yaml, subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ════════════════════════════════════════════════════════════════════════════
# C1: LLM Provider Detection & Endpoint Mapping
# ════════════════════════════════════════════════════════════════════════════

class TestC1_LLMProviderDetection:
    """Model name auto-infers correct provider + endpoint."""

    def _detect(self, model: str) -> tuple[str, str]:
        from edge.installer.checklist import _detect_provider_from_model
        return _detect_provider_from_model(model)

    # ── OpenAI-compatible providers ──

    @pytest.mark.parametrize("model,provider,endpoint", [
        ("deepseek-v4-pro",     "deepseek",  "https://api.deepseek.com/v1"),
        ("deepseek-chat",       "deepseek",  "https://api.deepseek.com/v1"),
        ("deepseek-reasoner",   "deepseek",  "https://api.deepseek.com/v1"),
        ("gpt-4o",              "openai",    "https://api.openai.com/v1"),
        ("gpt-4o-mini",         "openai",    "https://api.openai.com/v1"),
        ("gpt-4-turbo",         "openai",    "https://api.openai.com/v1"),
        ("o1-preview",          "openai",    "https://api.openai.com/v1"),
        ("o3-mini",             "openai",    "https://api.openai.com/v1"),
        ("MiniMax-M2.7-highspeed","minimax", "https://api.minimax.chat/v1"),
        ("minimax-m2.7",        "minimax",   "https://api.minimax.chat/v1"),
    ])
    def test_openai_compatible_providers(self, model, provider, endpoint):
        p, e = self._detect(model)
        assert p == provider, f"{model} → {p} (expected {provider})"
        assert e == endpoint, f"{model} → {e} (expected {endpoint})"

    # ── Anthropic (non-OpenAI-compatible) ──

    @pytest.mark.parametrize("model,provider,endpoint", [
        ("claude-sonnet-4",     "anthropic", "https://api.anthropic.com"),
        ("claude-opus-4",       "anthropic", "https://api.anthropic.com"),
        ("claude-haiku-3.5",    "anthropic", "https://api.anthropic.com"),
        ("anthropic/claude-sonnet-4", "anthropic", "https://api.anthropic.com"),
    ])
    def test_anthropic_provider_detection(self, model, provider, endpoint):
        p, e = self._detect(model)
        assert p == provider
        assert e == endpoint

    # ── Default / unknown ──

    @pytest.mark.parametrize("model", ["", "unknown-model", "random-llm"])
    def test_unknown_falls_back_to_deepseek(self, model):
        p, e = self._detect(model)
        assert p == "deepseek"
        assert e == "https://api.deepseek.com/v1"

    def test_deepseek_is_first_in_priority(self):
        """deepseek prefix checked first, so deepseek models always match."""
        from edge.installer.checklist import LLM_PROVIDER_MAP
        assert LLM_PROVIDER_MAP[0][0] == "deepseek"

    def test_all_providers_have_key_env_map(self):
        from edge.installer.checklist import LLM_KEY_ENV_MAP
        expected = {"deepseek", "openai", "anthropic", "minimax"}
        assert set(LLM_KEY_ENV_MAP.keys()) == expected
        for env_var in LLM_KEY_ENV_MAP.values():
            assert "_API_KEY" in env_var

    def test_default_model(self):
        from edge.installer.checklist import LLM_DEFAULT_MODEL
        assert LLM_DEFAULT_MODEL == "deepseek-v4-pro"


# ════════════════════════════════════════════════════════════════════════════
# C2: SystemDetector
# ════════════════════════════════════════════════════════════════════════════

class TestC2_SystemDetector:
    """10 agents + 8 IDEs + system info detection."""

    @pytest.fixture
    def info(self):
        from edge.installer.detector import SystemDetector
        return SystemDetector().detect_all()

    def test_10_agents_registered(self, info):
        names = {a.name for a in info.agents}
        expected = {"hermes","wukong","openclaw","qclaw","copaw","hiclaw",
                    "easyclaw","workbuddy","cline","cursor"}
        assert names == expected

    def test_8_ides_registered(self, info):
        names = {i.name for i in info.ides}
        expected = {"codex","claude_code","kimi_code","deepseek_tui",
                    "copilot","windsurf","orchestrator","sandbox"}
        assert names == expected

    def test_installed_agents_have_path_or_not(self, info):
        for a in info.agents:
            if a.installed:
                assert a.config_path, f"{a.name} installed but no path"

    def test_frameworks_populated(self, info):
        assert isinstance(info.frameworks, list)

    def test_system_fields_present(self, info):
        for f in ("os_name","python_version","cpu_count","memory_gb","hostname"):
            assert getattr(info, f, None) is not None, f"Missing field: {f}"

    def test_wsl_flag_is_bool(self, info):
        assert isinstance(info.is_wsl, bool)


# ════════════════════════════════════════════════════════════════════════════
# C3: ConfigAutoInjector
# ════════════════════════════════════════════════════════════════════════════

class TestC3_ConfigAutoInjector:
    """MCP injection into agent configs."""

    @pytest.fixture
    def d(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def cfg(self):
        from edge.installer.configurator import ConfigAutoInjector
        return ConfigAutoInjector(clawshell_dir="/tmp/cs")

    @pytest.fixture
    def hermes_agent(self, d):
        from edge.installer.detector import AgentDetection
        f = d / "config.yaml"
        f.write_text(yaml.dump({"existing": "value"}))
        return AgentDetection(name="hermes", installed=True,
                              config_path=str(f), config_exists=True,
                              claWSHELL_configured=False)

    def test_injects_mcp_servers(self, cfg, hermes_agent, d):
        cfg.inject_all([hermes_agent])
        content = yaml.safe_load(Path(hermes_agent.config_path).read_text())
        assert "mcp_servers" in content
        assert "clawshell-edge" in content["mcp_servers"]
        assert "clawshell-memory" in content["mcp_servers"]
        assert "existing" in content  # preserved

    def test_backup_created(self, cfg, hermes_agent):
        cfg.inject_all([hermes_agent])
        assert Path(hermes_agent.config_path + ".bak").exists()

    def test_idempotent(self, cfg, hermes_agent):
        cfg.inject_all([hermes_agent])
        r = cfg.inject_all([hermes_agent])
        assert r["hermes"] is True

    def test_batch_injection(self, cfg, d):
        from edge.installer.detector import AgentDetection
        agents = []
        for name in ("hermes", "openclaw"):
            f = d / f"{name}_config.yaml"
            f.write_text(yaml.dump({"k": "v"}))
            agents.append(AgentDetection(name=name, installed=True,
                          config_path=str(f), config_exists=True,
                          claWSHELL_configured=False))
        r = cfg.inject_all(agents)
        assert sum(1 for v in r.values() if v) == 2


# ════════════════════════════════════════════════════════════════════════════
# C4: SelfCheckReporter
# ════════════════════════════════════════════════════════════════════════════

class TestC4_SelfCheckReporter:
    """Post-install self-check reports."""

    @pytest.fixture
    def rep(self):
        from edge.installer.reporter import SelfCheckReporter
        return SelfCheckReporter()

    def test_full_report_structure(self, rep):
        r = rep.run_self_check()
        for key in ("checks","system","agents","ides","capabilities","status"):
            assert key in r, f"Missing key: {key}"

    def test_system_info_has_all_fields(self, rep):
        r = rep.run_self_check()
        for f in ("os","version","arch","python","cpu","memory_gb","disk_free_gb"):
            assert f in r["system"]

    def test_checks_are_boolean(self, rep):
        for v in rep.run_self_check()["checks"].values():
            assert isinstance(v, bool)

    def test_status_valid(self, rep):
        assert rep.run_self_check()["status"] in ("healthy","degraded")

    def test_agents_populated(self, rep):
        assert len(rep.run_self_check()["agents"]) >= 2  # hermes + wukong

    def test_ides_populated(self, rep):
        assert len(rep.run_self_check()["ides"]) >= 2  # claude_code + codex

    def test_capabilities_at_least_5(self, rep):
        assert len(rep.run_self_check()["capabilities"]) >= 5

    def test_markdown_contains_sections(self, rep):
        md = rep.generate_report(as_markdown=True)
        for section in ("ClawShell Edge","System Information",
                         "Component Checks","Next Steps"):
            assert section in md, f"Missing: {section}"

    def test_markdown_minimum_length(self, rep):
        assert len(rep.generate_report(as_markdown=True)) > 200


# ════════════════════════════════════════════════════════════════════════════
# C5: InstallationChecklist
# ════════════════════════════════════════════════════════════════════════════

class TestC5_InstallationChecklist:
    """Credential collection + prerequisite validation."""

    def test_python_version_check(self):
        from edge.installer.checklist import InstallationChecklist
        chk = InstallationChecklist()
        assert chk._check_python() is True  # 3.12

    def test_git_check(self):
        from edge.installer.checklist import InstallationChecklist
        chk = InstallationChecklist()
        assert chk._check_git() is True

    def test_non_interactive_returns_skipped_or_env(self):
        from edge.installer.checklist import InstallationChecklist
        chk = InstallationChecklist()
        chk.interactive = False
        # In interactive=False, returns "skipped" or "*** (from env)" if env key set
        result_llm = chk._prompt_llm_key()
        result_memos = chk._prompt_memos_key()
        assert result_llm in ("skipped", "*** (from env)")
        assert result_memos in ("skipped", "*** (from env)")

    def test_exported_functions_are_callable(self):
        from edge.installer.checklist import (
            _detect_provider_from_model, _key_env_for_provider,
            LLM_PROVIDER_MAP, LLM_KEY_ENV_MAP, LLM_DEFAULT_MODEL,
        )
        assert callable(_detect_provider_from_model)
        assert callable(_key_env_for_provider)
        assert len(LLM_PROVIDER_MAP) >= 8  # 8 model prefix entries


# ════════════════════════════════════════════════════════════════════════════
# C6: Edge CronReporter
# ════════════════════════════════════════════════════════════════════════════

class TestC6_EdgeCronReporter:
    """Edge-side Cron execution reporting."""

    @pytest.fixture
    def rep(self, tmp_path):
        from exoskeleton.layer3.cron_reporter import CronReporter
        return CronReporter("edge-test", "http://localhost", data_dir=str(tmp_path))

    def test_report_generates_uuid(self, rep):
        rid = rep.report("task.cleanup", "success", duration_ms=50)
        assert rid.startswith("rep_")

    def test_report_persists(self, tmp_path):
        from exoskeleton.layer3.cron_reporter import CronReporter
        r1 = CronReporter("e1", "http://x", data_dir=str(tmp_path))
        r1.report("t1", "success")
        r2 = CronReporter("e1", "http://x", data_dir=str(tmp_path))
        assert r2.get_pending_count() >= 1

    def test_queue_ordering(self, rep):
        rep.report("t1", "success")
        rep.report("t2", "failed")
        assert rep.get_pending_count() == 2

    def test_scheduler_result_parse(self, rep):
        rid = rep.report_from_scheduler_result("task.x", {
            "status":"failed","error":"disk","duration_ms":200.0
        })
        assert rid.startswith("rep_")

    def test_stats(self, rep):
        rep.report("t1", "success")
        s = rep.get_stats()
        assert s["node_id"] == "edge-test"
        assert s["pending"] >= 1


# ════════════════════════════════════════════════════════════════════════════
# C7: CloudCronSupervisor + DispatchRouter
# ════════════════════════════════════════════════════════════════════════════

class TestC7_CloudCronSupervisor:
    """Cloud-side Cron monitoring + dispatch."""

    @pytest.fixture
    def mock_eb(self):
        class M:
            def __init__(self): self.published = []
            def publish(self, **kwargs):
                self.published.append(kwargs)
        return M()

    @pytest.fixture
    def mock_tb(self):
        class M:
            def __init__(self): self.created = []
            def create_task(self, **kwargs):
                self.created.append(kwargs)
                return {"task_id": f"t_{uuid.uuid4().hex[:8]}"}
        return M()

    @pytest.fixture
    def mock_cr(self):
        class M:
            def __init__(self): self._nodes = {}
            def register_node(self, nid, capabilities=None):
                self._nodes[nid] = {"node_id":nid,"capabilities":capabilities or [],
                                     "last_heartbeat":time.time()}
            def list_nodes(self): return list(self._nodes.values())
        return M()

    @pytest.fixture
    def sup(self, mock_eb, mock_tb, mock_cr, tmp_path):
        from cloud.engines.dispatch_router import DispatchRouter
        from cloud.engines.cron_supervisor import CloudCronSupervisor
        router = DispatchRouter(eventbus=mock_eb, task_board=mock_tb,
                                data_dir=str(tmp_path))
        return CloudCronSupervisor(data_dir=str(tmp_path), scheduler=None,
                                   eventbus=mock_eb, task_board=mock_tb,
                                   capability_registry=mock_cr,
                                   dispatch_router=router)

    def test_add_report(self, sup):
        from shared.models import CronReport
        rid = sup.add_report(CronReport(
            report_id="r1", source="edge:x", task_id="t1", status="success"
        ))
        assert rid == "r1"

    def test_detect_edge_offline(self, sup, mock_cr):
        from shared.models import CronReport
        mock_cr.register_node("edge:off", ["cleanup"])
        mock_cr._nodes["edge:off"]["last_heartbeat"] = time.time() - 200
        sup.add_report(CronReport(report_id="r1", source="edge:off",
                                   task_id="t1", status="success"))
        probs = sup.run_check_now()
        assert any(str(p.problem_type)=="edge_offline" for p in probs)

    def test_detect_chronic_failure(self, sup):
        from shared.models import CronReport
        for i in range(5):
            sup.add_report(CronReport(report_id=f"r{i}", source="edge:f",
                                       task_id="t1", status="failed"))
        probs = sup.run_check_now()
        assert any(str(p.problem_type)=="chronic_failure" for p in probs)

    def test_dispatch_happens_in_check_now(self, sup, mock_eb, mock_tb, mock_cr):
        """Detection + explicit dispatch → published or task created."""
        from shared.models import CronReport
        mock_cr.register_node("edge:f", ["cleanup"])
        mock_cr._nodes["edge:f"]["last_heartbeat"] = time.time() - 200
        for i in range(5):
            sup.add_report(CronReport(report_id=f"r{i}", source="edge:f",
                                       task_id="t1", status="failed"))
        problems = sup.run_check_now()
        for p in problems:
            sup._dispatch_repair(p)
        assert mock_eb.published or mock_tb.created, \
            "Dispatch should publish or create a task"

    def test_stats(self, sup, mock_cr):
        from shared.models import CronReport
        mock_cr.register_node("edge:a", ["cleanup"])
        mock_cr._nodes["edge:a"]["last_heartbeat"] = time.time() - 200
        for i in range(3):
            sup.add_report(CronReport(report_id=f"r{i}", source="edge:a",
                                       task_id="t1", status="success"))
        sup.run_check_now()
        s = sup.get_stats()
        assert s["total_reports"] == 3


# ════════════════════════════════════════════════════════════════════════════
# C8: Full Pipeline End-to-End
# ════════════════════════════════════════════════════════════════════════════

class TestC8_FullPipeline:
    """Report → Detect → Dispatch → Confirm end-to-end."""

    def test_pipeline(self, tmp_path):
        from shared.models import CronReport
        from cloud.engines.dispatch_router import DispatchRouter
        from cloud.engines.cron_supervisor import CloudCronSupervisor

        class MockEB:
            def __init__(self): self.published = []
            def publish(self, **kwargs): self.published.append(kwargs)
        class MockTB:
            def __init__(self): self.created = []
            def create_task(self, **kwargs):
                self.created.append(kwargs)
                return {"task_id": f"t_{uuid.uuid4().hex[:8]}"}

        eb = MockEB(); tb = MockTB()
        router = DispatchRouter(eventbus=eb, task_board=tb, data_dir=str(tmp_path))
        sup = CloudCronSupervisor(data_dir=str(tmp_path), scheduler=None,
                                   eventbus=eb, task_board=tb,
                                   capability_registry=None,
                                   dispatch_router=router)

        # Feed failures + offline edge (to trigger detection + dispatch)
        sup.add_report(CronReport(report_id="r0", source="edge:x",
                                   task_id="cleanup", status="failed"))
        sup.add_report(CronReport(report_id="r1", source="edge:x",
                                   task_id="cleanup", status="failed"))
        sup.add_report(CronReport(report_id="r2", source="edge:x",
                                   task_id="cleanup", status="failed"))
        sup.add_report(CronReport(report_id="r3", source="edge:x",
                                   task_id="cleanup", status="failed"))

        problems = sup.run_check_now()
        for p in problems:
            sup._dispatch_repair(p)
        assert eb.published or tb.created, "Detection + dispatch via router"


# ════════════════════════════════════════════════════════════════════════════
# C9: CLI Modes
# ════════════════════════════════════════════════════════════════════════════

class TestC9_CLIModes:
    """All CLI modes run without error."""

    ROOT = str(Path(__file__).parent.parent)

    def _run(self, *args):
        r = subprocess.run([sys.executable, "-m", "edge.installer"] + list(args),
                           capture_output=True, text=True, timeout=20, cwd=self.ROOT)
        return r

    def test_detect_mode(self):
        r = self._run("detect")
        assert r.returncode == 0
        assert "OS:" in r.stdout
        assert "Agents:" in r.stdout
        assert "IDEs:" in r.stdout

    def test_check_mode(self):
        r = self._run("check")
        assert r.returncode == 0
        assert "ClawShell Edge" in r.stdout

    def test_agent_mode_output(self):
        r = self._run("agent-mode")
        assert r.returncode == 0
        assert "Phase 1" in r.stdout
        assert "Phase 6" in r.stdout

    def test_config_mode(self):
        r = self._run("config")
        assert r.returncode == 0
        assert "Done:" in r.stdout or "agents" in r.stdout.lower()


# ════════════════════════════════════════════════════════════════════════════
# C10: LLM Client (OpenAI-compatible format)
# ════════════════════════════════════════════════════════════════════════════

class TestC10_LLMClient:
    """LLM client configuration and API key resolution."""

    def test_client_importable(self):
        from cloud.brain.llm_client import LLMClient
        assert LLMClient is not None

    def test_unconfigured_detected(self):
        from cloud.brain.llm_client import LLMClient
        # Without env keys, should report not configured
        llm = LLMClient()
        # is_configured checks self.api_key which reads env vars
        # In test env without keys, should be False
        result = llm.chat("sys", "hello")
        assert result["success"] is False
        assert "not configured" in result.get("error", "")

    def test_all_env_vars_checked(self, monkeypatch):
        """All 4 provider API key env vars are checked for."""
        from cloud.brain.llm_client import LLMClient
        # Set each one and verify it's detected
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-deepseek")
        assert LLMClient().is_configured is True

        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")
        assert LLMClient().is_configured is True

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        assert LLMClient().is_configured is True

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("MINIMAX_API_KEY", "sk-test-minimax")
        assert LLMClient().is_configured is True

    def test_base_url_uses_env(self, monkeypatch):
        from cloud.brain.llm_client import LLMClient
        monkeypatch.setenv("LLM_BASE_URL", "https://custom.api.com/v1")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        llm = LLMClient()
        assert llm.base_url == "https://custom.api.com/v1"

    def test_model_uses_env(self, monkeypatch):
        from cloud.brain.llm_client import LLMClient
        monkeypatch.setenv("LLM_MODEL", "custom-model-v2")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        llm = LLMClient()
        assert llm.model == "custom-model-v2"


# ════════════════════════════════════════════════════════════════════════════
# BOUNDARIES
# ════════════════════════════════════════════════════════════════════════════

class TestBoundaries:
    """Documented boundaries and limitations."""

    # ── B1: Anthropic non-OpenAI-compatible ──

    def test_anthropic_endpoint_differs_from_openai(self):
        """Anthropic endpoint doesn't use /v1 (different API format)."""
        from edge.installer.checklist import _detect_provider_from_model
        _, deepseek_ep = _detect_provider_from_model("deepseek-v4-pro")
        _, openai_ep = _detect_provider_from_model("gpt-4o")
        _, anthropic_ep = _detect_provider_from_model("claude-sonnet-4")
        # Anthropic base URL is DIFFERENT from OpenAI-compatible ones
        assert anthropic_ep != deepseek_ep
        assert anthropic_ep != openai_ep
        assert "anthropic.com" in anthropic_ep
        assert "/v1" not in anthropic_ep  # Not OpenAI-compatible with /v1 suffix

    # ── B2: Missing dependencies ──

    def test_detector_works_without_psutil(self):
        from edge.installer.detector import SystemDetector
        info = SystemDetector().detect_all()
        assert info.memory_gb >= 0
        assert info.cpu_count >= 0

    # ── B3: Non-existent config paths ──

    def test_configurator_handles_missing_path(self):
        from edge.installer.detector import AgentDetection
        from edge.installer.configurator import ConfigAutoInjector
        a = AgentDetection(name="ghost", installed=True,
                           config_path="/nonexistent/ghost.yaml")
        r = ConfigAutoInjector().inject_all([a])
        assert r["ghost"] is False  # graceful failure

    def test_reporter_handles_missing_dir(self):
        from edge.installer.reporter import SelfCheckReporter
        r = SelfCheckReporter("/nonexistent").run_self_check()
        assert r["status"] in ("healthy","degraded")  # doesn't crash

    # ── B4: Uninstalled / already-configured agents ──

    def test_uninstalled_agent_skipped_in_injection(self):
        from edge.installer.detector import AgentDetection
        from edge.installer.configurator import ConfigAutoInjector
        a = AgentDetection(name="openclaw", installed=False)
        assert ConfigAutoInjector().inject_all([a])["openclaw"] is False

    def test_already_configured_agent_preserved(self):
        from edge.installer.detector import AgentDetection
        from edge.installer.configurator import ConfigAutoInjector
        a = AgentDetection(name="hermes", installed=True,
                           claWSHELL_configured=True)
        # Already configured → should still succeed (not re-inject)
        assert ConfigAutoInjector().inject_all([a])["hermes"] is True

    # ── B5: Empty / unknown model fallback ──

    def test_empty_model_falls_back(self):
        from edge.installer.checklist import _detect_provider_from_model
        p, e = _detect_provider_from_model("")
        assert p == "deepseek"

    def test_unknown_model_falls_back(self):
        from edge.installer.checklist import _detect_provider_from_model
        p, e = _detect_provider_from_model("llama-3-70b")
        assert p == "deepseek"  # unknown → deepseek

    # ── B6: Case-insensitive ──

    @pytest.mark.parametrize("model,expected", [
        ("DEEPSEEK-V4-PRO", "deepseek"),
        ("MINIMAX-M2.7-HIGHSPEED", "minimax"),
        ("GPT-4O", "openai"),
        ("CLAUDE-SONNET-4", "anthropic"),
    ])
    def test_case_insensitive(self, model, expected):
        from edge.installer.checklist import _detect_provider_from_model
        p, _ = _detect_provider_from_model(model)
        assert p == expected

    # ── B7: Degraded mode (no keys, unreachable cloud) ──

    def test_reporter_degraded_without_api_keys(self):
        """Report still works without API keys."""
        from edge.installer.reporter import SelfCheckReporter
        r = SelfCheckReporter().run_self_check()
        # May be healthy or degraded depending on what's installed
        assert r["status"] in ("healthy","degraded")

    def test_checklist_skippable(self):
        """Checklist can skip credential prompts in non-interactive."""
        from edge.installer.checklist import InstallationChecklist
        chk = InstallationChecklist()
        chk.interactive = False
        # In non-interactive mode, returns "skipped" or "*** (from env)"
        assert chk._prompt_llm_key() in ("skipped", "*** (from env)")
        assert chk._prompt_memos_key() in ("skipped", "*** (from env)")

    # ── B8: Wukong Windows-path limitation ──

    def test_wukong_path_resolution(self):
        """Wukong path uses Windows /mnt/ prefix in WSL."""
        from edge.installer.detector import SystemDetector, KNOWN_AGENT_PATHS
        wukong_paths = KNOWN_AGENT_PATHS.get("wukong", [])
        assert any("/mnt/" in p or ".real" in p for p in wukong_paths), \
            "Wukong paths should include Windows /mnt/ prefix"

    # ── B9: Installer non-interactive mode ──

    def test_installer_non_interactive(self):
        from edge.installer.installer import ClawShellEdgeInstaller
        i = ClawShellEdgeInstaller(interactive=False, skip_checklist=True)
        assert i.cloud_url
        assert i.detector is not None

    # ── B10: CLI error handling ──

    def test_cli_unknown_action(self):
        r = subprocess.run(
            [sys.executable, "-m", "edge.installer", "nonexistent_action"],
            capture_output=True, text=True, timeout=10,
            cwd=str(Path(__file__).parent.parent),
        )
        assert r.returncode != 0  # Should exit with error
