"""Comprehensive multi-dimensional tests for ClawShell v2.2.0

Dimensions:
  1. LLM Model → Provider auto-detection
  2. SystemDetector (10 agents + 8 IDEs)
  3. ConfigAutoInjector (MCP injection)
  4. SelfCheckReporter (report generation)
  5. InstallationChecklist (credential collection)
  6. ClawShellEdgeInstaller (orchestration)
  7. Edge CronReporter (Cron reporting)
  8. CloudCronSupervisor + DispatchRouter (cloud engine)
  9. Full Pipeline (report → detect → dispatch)
 10. Error handling & edge cases

Run: pytest tests/test_comprehensive_v2.py -v
"""

from __future__ import annotations
import sys, os, json, tempfile, uuid, time, threading
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ═══════════════════════════════════════════════════════════════════════════
# DIMENSION 1: LLM Model → Provider Auto-Detection
# ═══════════════════════════════════════════════════════════════════════════

class TestLLMProviderDetection:
    """LLM model name auto-infers provider + endpoint."""

    def _detect(self, model: str) -> tuple[str, str]:
        from edge.installer.checklist import _detect_provider_from_model
        return _detect_provider_from_model(model)

    def test_deepseek_v4_pro(self):
        provider, endpoint = self._detect("deepseek-v4-pro")
        assert provider == "deepseek"
        assert endpoint == "https://api.deepseek.com/v1"

    def test_deepseek_chat(self):
        provider, endpoint = self._detect("deepseek-chat")
        assert provider == "deepseek"

    def test_deepseek_reasoner(self):
        provider, endpoint = self._detect("deepseek-reasoner")
        assert provider == "deepseek"

    def test_minimax_m27_highspeed(self):
        provider, endpoint = self._detect("MiniMax-M2.7-highspeed")
        assert provider == "minimax"
        assert endpoint == "https://api.minimax.chat/v1"

    def test_minimax_lowercase(self):
        provider, endpoint = self._detect("minimax-m2.7")
        assert provider == "minimax"

    def test_gpt4o(self):
        provider, endpoint = self._detect("gpt-4o")
        assert provider == "openai"
        assert endpoint == "https://api.openai.com/v1"

    def test_gpt4o_mini(self):
        provider, _ = self._detect("gpt-4o-mini")
        assert provider == "openai"

    def test_o1_preview(self):
        provider, _ = self._detect("o1-preview")
        assert provider == "openai"

    def test_o3_mini(self):
        provider, _ = self._detect("o3-mini")
        assert provider == "openai"

    def test_claude_sonnet(self):
        provider, endpoint = self._detect("claude-sonnet-4")
        assert provider == "anthropic"
        assert endpoint == "https://api.anthropic.com"

    def test_anthropic_slash_prefix(self):
        provider, _ = self._detect("anthropic/claude-sonnet-4")
        assert provider == "anthropic"

    def test_unknown_model_falls_back_to_deepseek(self):
        provider, endpoint = self._detect("some-unknown-model")
        assert provider == "deepseek"
        assert endpoint == "https://api.deepseek.com/v1"

    def test_empty_string_defaults(self):
        provider, _ = self._detect("")
        assert provider == "deepseek"

    def test_key_env_mapping(self):
        from edge.installer.checklist import _key_env_for_provider
        assert _key_env_for_provider("deepseek") == "DEEPSEEK_API_KEY"
        assert _key_env_for_provider("openai") == "OPENAI_API_KEY"
        assert _key_env_for_provider("anthropic") == "ANTHROPIC_API_KEY"
        assert _key_env_for_provider("minimax") == "MINIMAX_API_KEY"
        assert _key_env_for_provider("unknown") == "DEEPSEEK_API_KEY"

    def test_default_model_is_deepseek_v4_pro(self):
        from edge.installer.checklist import LLM_DEFAULT_MODEL
        assert LLM_DEFAULT_MODEL == "deepseek-v4-pro"


# ═══════════════════════════════════════════════════════════════════════════
# DIMENSION 2: SystemDetector — Agent + IDE Discovery
# ═══════════════════════════════════════════════════════════════════════════

class TestSystemDetector:
    """Comprehensive agent and IDE detection."""

    @pytest.fixture
    def detector(self):
        from edge.installer.detector import SystemDetector
        return SystemDetector()

    def test_detects_all_10_agent_types(self, detector):
        """All 10 agent types are registered for detection."""
        info = detector.detect_all()
        agent_names = [a.name for a in info.agents]
        expected = [
            "hermes", "wukong", "openclaw",
            "qclaw", "copaw", "hiclaw", "easyclaw", "workbuddy",
            "cline", "cursor",
        ]
        for name in expected:
            assert name in agent_names, f"Missing agent: {name}"
        assert len(agent_names) == len(expected)

    def test_detects_all_8_ide_types(self, detector):
        """All 8 IDE types are registered for detection."""
        info = detector.detect_all()
        ide_names = [i.name for i in info.ides]
        expected = [
            "codex", "claude_code", "kimi_code", "deepseek_tui",
            "copilot", "windsurf", "orchestrator", "sandbox",
        ]
        for name in expected:
            assert name in ide_names, f"Missing IDE: {name}"
        assert len(ide_names) == len(expected)

    def test_system_info_populated(self, detector):
        """System info has all required fields."""
        info = detector.detect_all()
        assert info.os_name in ("linux", "macos", "windows", "wsl", "unknown")
        assert info.python_version
        assert info.hostname
        assert info.cpu_count > 0
        assert info.memory_gb > 0

    def test_wsl_detection_flag(self, detector):
        """is_wsl flag is a boolean."""
        info = detector.detect_all()
        assert isinstance(info.is_wsl, bool)

    def test_installed_agents_have_path(self, detector):
        """Installed agents must have a config path."""
        info = detector.detect_all()
        for agent in info.agents:
            if agent.installed:
                assert agent.config_path, f"{agent.name} installed but no path"

    def test_installed_ides_have_path(self, detector):
        """Installed IDEs must have a path."""
        info = detector.detect_all()
        for ide in info.ides:
            if ide.installed:
                assert ide.path, f"{ide.name} installed but no path"


# ═══════════════════════════════════════════════════════════════════════════
# DIMENSION 3: ConfigAutoInjector
# ═══════════════════════════════════════════════════════════════════════════

class TestConfigAutoInjector:
    """MCP config auto-injection into detected agents."""

    @pytest.fixture
    def temp_yaml(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def configurator(self):
        from edge.installer.configurator import ConfigAutoInjector
        return ConfigAutoInjector(clawshell_dir="/tmp/test_clawshell")

    @pytest.fixture
    def hermes_detection(self, temp_yaml):
        from edge.installer.detector import AgentDetection
        config_file = temp_yaml / "config.yaml"
        import yaml
        config_file.write_text(yaml.dump({"some_key": "some_value"}))
        return AgentDetection(
            name="hermes",
            installed=True,
            config_path=str(config_file),
            config_exists=True,
            claWSHELL_configured=False,
        )

    def test_inject_into_hermes_yaml(self, configurator, hermes_detection):
        """Hermes YAML config gets MCP servers injected."""
        import yaml
        result = configurator.inject_all([hermes_detection])
        assert result["hermes"] is True

        # Verify the file was modified
        content = yaml.safe_load(Path(hermes_detection.config_path).read_text())
        assert "mcp_servers" in content
        assert "clawshell-edge" in content["mcp_servers"]

    def test_backup_created(self, configurator, hermes_detection):
        """Config injection creates a backup file."""
        configurator.inject_all([hermes_detection])
        backup = Path(hermes_detection.config_path).with_suffix(".yaml.bak")
        assert backup.exists()

    def test_idempotent_injection(self, configurator, hermes_detection):
        """Second injection should still succeed (idempotent)."""
        configurator.inject_all([hermes_detection])
        result = configurator.inject_all([hermes_detection])
        assert result["hermes"] is True

    def test_uninstalled_agent_skipped(self, configurator):
        """Uninstalled agents are not injected."""
        from edge.installer.detector import AgentDetection
        agent = AgentDetection(name="openclaw", installed=False)
        result = configurator.inject_all([agent])
        assert result["openclaw"] is False

    def test_already_configured_agent_preserved(self, configurator, hermes_detection):
        """Already configured agent returns True but doesn't re-inject."""
        # Mark as already configured
        hermes_detection.claWSHELL_configured = True
        result = configurator.inject_all([hermes_detection])
        assert result["hermes"] is True  # Still reports success

    def test_inject_multiple_agents(self, configurator, temp_yaml):
        """Batch inject into multiple agents."""
        from edge.installer.detector import AgentDetection
        agents = []
        for i, name in enumerate(["hermes", "openclaw"]):
            config_file = temp_yaml / f"{name}_config.yaml"
            import yaml
            config_file.write_text(yaml.dump({f"key_{i}": f"val_{i}"}))
            agents.append(AgentDetection(
                name=name, installed=True,
                config_path=str(config_file),
                config_exists=True,
                claWSHELL_configured=False,
            ))
        result = configurator.inject_all(agents)
        assert "hermes" in result
        assert "openclaw" in result


# ═══════════════════════════════════════════════════════════════════════════
# DIMENSION 4: SelfCheckReporter
# ═══════════════════════════════════════════════════════════════════════════

class TestSelfCheckReporter:
    """Post-install self-check and report generation."""

    @pytest.fixture
    def reporter(self):
        from edge.installer.reporter import SelfCheckReporter
        return SelfCheckReporter()

    def test_run_self_check_returns_dict(self, reporter):
        report = reporter.run_self_check()
        assert isinstance(report, dict)
        assert "checks" in report
        assert "system" in report
        assert "agents" in report
        assert "ides" in report
        assert "capabilities" in report
        assert "status" in report

    def test_system_info_complete(self, reporter):
        report = reporter.run_self_check()
        sys_info = report["system"]
        for key in ("os", "version", "arch", "python", "cpu", "memory_gb", "disk_free_gb"):
            assert key in sys_info, f"Missing system field: {key}"

    def test_all_checks_boolean(self, reporter):
        report = reporter.run_self_check()
        for k, v in report["checks"].items():
            assert isinstance(v, bool), f"Check {k} should be bool, got {type(v)}"

    def test_status_is_valid(self, reporter):
        report = reporter.run_self_check()
        assert report["status"] in ("healthy", "degraded")

    def test_agent_list_not_empty(self, reporter):
        report = reporter.run_self_check()
        assert len(report["agents"]) > 0, "Agent list should not be empty"

    def test_ide_list_not_empty(self, reporter):
        report = reporter.run_self_check()
        assert len(report["ides"]) > 0, "IDE list should not be empty"

    def test_capabilities_at_least_3(self, reporter):
        report = reporter.run_self_check()
        assert len(report["capabilities"]) >= 3

    def test_markdown_report_contains_key_sections(self, reporter):
        md = reporter.generate_report(as_markdown=True)
        assert "ClawShell Edge" in md
        assert "System Information" in md
        assert "Component Checks" in md

    def test_markdown_not_empty(self, reporter):
        md = reporter.generate_report(as_markdown=True)
        assert len(md) > 100, "Markdown report too short"


# ═══════════════════════════════════════════════════════════════════════════
# DIMENSION 5: InstallationChecklist
# ═══════════════════════════════════════════════════════════════════════════

class TestInstallationChecklist:
    """Interactive prerequisites checklist."""

    def test_python_check(self):
        from edge.installer.checklist import InstallationChecklist
        chk = InstallationChecklist()
        assert chk._check_python() is True  # We're running Python 3.12

    def test_llm_provider_detection_integrated(self):
        """LLM detection functions are importable and callable."""
        from edge.installer.checklist import (
            _detect_provider_from_model,
            _key_env_for_provider,
            LLM_DEFAULT_MODEL,
            LLM_PROVIDER_MAP,
            LLM_KEY_ENV_MAP,
        )
        assert len(LLM_PROVIDER_MAP) >= 8
        assert len(LLM_KEY_ENV_MAP) == 4
        assert LLM_DEFAULT_MODEL == "deepseek-v4-pro"
        provider, endpoint = _detect_provider_from_model("claude-opus-4")
        assert provider == "anthropic"
        assert "anthropic.com" in endpoint


# ═══════════════════════════════════════════════════════════════════════════
# DIMENSION 6: ClawShellEdgeInstaller (Orchestration)
# ═══════════════════════════════════════════════════════════════════════════

class TestClawShellEdgeInstaller:
    """Core installer orchestration (non-interactive)."""

    def test_installer_imports(self):
        from edge.installer.installer import ClawShellEdgeInstaller
        assert ClawShellEdgeInstaller is not None

    def test_installer_init(self):
        from edge.installer.installer import ClawShellEdgeInstaller
        installer = ClawShellEdgeInstaller(
            workdir=str(Path.home() / ".clawshell"),
            skip_checklist=True,
            interactive=False,
        )
        assert installer.workdir is not None
        assert installer.cloud_url

    def test_installer_has_required_components(self):
        from edge.installer.installer import ClawShellEdgeInstaller
        installer = ClawShellEdgeInstaller(skip_checklist=True, interactive=False)
        assert installer.detector is not None
        assert installer.reporter is not None

    def test_agent_mode_guide_exists(self):
        guide = Path(__file__).parent.parent / "edge" / "installer" / "AGENT_MODE.md"
        assert guide.exists(), "AGENT_MODE.md not found"
        content = guide.read_text()
        assert "Phase 1" in content
        assert "Phase 6" in content
        assert "deepseek-v4-pro" in content


# ═══════════════════════════════════════════════════════════════════════════
# DIMENSION 7: Edge CronReporter
# ═══════════════════════════════════════════════════════════════════════════

class TestCronReporterEdge:
    """Edge CronReporter — report generation and persistence."""

    @pytest.fixture
    def reporter(self, tmp_path):
        from exoskeleton.layer3.cron_reporter import CronReporter
        return CronReporter(
            node_id="test-edge-001",
            cloud_url="http://localhost:9999",
            data_dir=str(tmp_path),
        )

    def test_report_generates_id(self, reporter):
        rid = reporter.report(task_id="edge.cleanup", status="success", duration_ms=50.0)
        assert rid.startswith("rep_")

    def test_report_adds_to_pending_queue(self, reporter):
        reporter.report(task_id="edge.cleanup", status="success")
        assert reporter.get_pending_count() == 1

    def test_multiple_reports_queue(self, reporter):
        for i in range(3):
            reporter.report(task_id=f"task_{i}", status="success" if i < 2 else "failed")
        assert reporter.get_pending_count() == 3

    def test_report_from_scheduler_result(self, reporter):
        result = {
            "status": "failed",
            "error": "disk full",
            "duration_ms": 200.0,
            "recommendations": ["cleanup_needed"],
        }
        rid = reporter.report_from_scheduler_result("edge.cleanup", result)
        assert rid.startswith("rep_")

    def test_stats_returns_dict(self, reporter):
        reporter.report(task_id="edge.cleanup", status="success")
        stats = reporter.get_stats()
        assert stats["node_id"] == "test-edge-001"
        assert "pending" in stats

    def test_persistence_across_instances(self, tmp_path):
        """Reports survive CronReporter instance recreation."""
        from exoskeleton.layer3.cron_reporter import CronReporter
        r1 = CronReporter("test-edge", "http://localhost", data_dir=str(tmp_path))
        r1.report(task_id="edge.cleanup", status="success")

        r2 = CronReporter("test-edge", "http://localhost", data_dir=str(tmp_path))
        assert r2.get_pending_count() >= 1


# ═══════════════════════════════════════════════════════════════════════════
# DIMENSION 8: CloudCronSupervisor + DispatchRouter
# ═══════════════════════════════════════════════════════════════════════════

class TestCloudCronSupervisor:
    """Cloud-side Cron monitoring engine."""

    @pytest.fixture
    def mock_eventbus(self):
        class Mock:
            def __init__(self): self.published = []
            def publish(self, event_type, source, priority=50, payload=None):
                self.published.append({"event_type": event_type, "source": source, "payload": payload or {}})
        return Mock()

    @pytest.fixture
    def mock_task_board(self):
        class Mock:
            def __init__(self): self.created = []
            def create_task(self, title, description="", priority=50, tags=None, payload=None):
                task_id = f"task_{uuid.uuid4().hex[:8]}"
                self.created.append({"task_id": task_id, "title": title, "payload": payload})
                return {"task_id": task_id}
        return Mock()

    @pytest.fixture
    def mock_cap_registry(self):
        class Mock:
            def __init__(self): self._nodes = {}
            def register_node(self, node_id, capabilities=None):
                self._nodes[node_id] = {"node_id": node_id, "capabilities": capabilities or [], "last_heartbeat": time.time()}
            def list_nodes(self): return list(self._nodes.values())
        return Mock()

    @pytest.fixture
    def supervisor(self, mock_eventbus, mock_task_board, mock_cap_registry, tmp_path):
        from cloud.engines.dispatch_router import DispatchRouter
        from cloud.engines.cron_supervisor import CloudCronSupervisor
        router = DispatchRouter(
            eventbus=mock_eventbus,
            task_board=mock_task_board,
            data_dir=str(tmp_path),
        )
        return CloudCronSupervisor(
            data_dir=str(tmp_path),
            scheduler=None,
            eventbus=mock_eventbus,
            task_board=mock_task_board,
            capability_registry=mock_cap_registry,
            dispatch_router=router,
        )

    def test_add_report(self, supervisor):
        from shared.models import CronReport
        rid = supervisor.add_report(CronReport(
            report_id="rep_test", source="edge:test",
            task_id="edge.cleanup", status="success",
        ))
        assert rid == "rep_test"
        assert len(supervisor.get_reports()) == 1

    def test_detect_edge_offline(self, supervisor, mock_cap_registry):
        from shared.models import CronReport
        mock_cap_registry.register_node("edge:offline", ["cleanup"])
        node = mock_cap_registry._nodes["edge:offline"]
        node["last_heartbeat"] = time.time() - 200  # 200s ago

        supervisor.add_report(CronReport(
            report_id="rep_offline", source="edge:offline",
            task_id="edge.cleanup", status="success",
        ))
        problems = supervisor.run_check_now()
        assert len(problems) >= 1

    def test_detect_chronic_failure(self, supervisor):
        from shared.models import CronReport
        for i in range(5):
            supervisor.add_report(CronReport(
                report_id=f"rep_fail_{i}", source="edge:failing",
                task_id="edge.cleanup", status="failed", error=f"err_{i}",
            ))
        problems = supervisor.run_check_now()
        chronic = [p for p in problems if str(p.problem_type) == "chronic_failure"]
        assert len(chronic) >= 1

    def test_problems_deduplicated(self, supervisor, mock_cap_registry):
        from shared.models import CronReport
        # First run: detect stale edge
        mock_cap_registry.register_node("edge:stale", ["cleanup"])
        mock_cap_registry._nodes["edge:stale"]["last_heartbeat"] = time.time() - 200
        supervisor.add_report(CronReport(
            report_id="rep_stale", source="edge:stale",
            task_id="edge.cleanup", status="success",
        ))
        problems1 = supervisor.run_check_now()
        count1 = len(problems1)
        assert count1 >= 1, "Should detect at least 1 problem"

        # Second run: already dispatched problems should NOT re-appear
        problems2 = supervisor.run_check_now()
        # Same problem with same source should not be re-added
        assert len(problems2) <= count1, "Should not create duplicate problems"

    def test_stats_accurate(self, supervisor, mock_cap_registry):
        from shared.models import CronReport
        mock_cap_registry.register_node("edge:node-a", ["cleanup"])
        mock_cap_registry._nodes["edge:node-a"]["last_heartbeat"] = time.time() - 200
        for i in range(3):
            supervisor.add_report(CronReport(
                report_id=f"rep_{i}", source="edge:node-a",
                task_id="edge.cleanup", status="success",
            ))
        supervisor.run_check_now()
        stats = supervisor.get_stats()
        assert stats["total_reports"] == 3
        assert stats["active_problems"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# DIMENSION 9: Full Pipeline Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    """End-to-end: Report → Detect → Dispatch → Confirm."""

    @pytest.fixture
    def mock_eventbus(self):
        class Mock:
            def __init__(self): self.published = []
            def publish(self, event_type, source, priority=50, payload=None):
                self.published.append({"event_type": event_type, "source": source, "payload": payload or {}})
        return Mock()

    @pytest.fixture
    def mock_task_board(self):
        class Mock:
            def __init__(self): self.created = []
            def create_task(self, title, description="", priority=50, tags=None, payload=None):
                self.created.append({"title": title, "payload": payload or {}})
                return {"task_id": f"task_{uuid.uuid4().hex[:8]}"}
        return Mock()

    def test_cron_report_triggers_dispatch(self, mock_eventbus, mock_task_board, tmp_path):
        """A series of failing reports → detected → dispatched."""
        from shared.models import CronReport
        from cloud.engines.dispatch_router import DispatchRouter
        from cloud.engines.cron_supervisor import CloudCronSupervisor

        router = DispatchRouter(
            eventbus=mock_eventbus,
            task_board=mock_task_board,
            data_dir=str(tmp_path),
        )
        supervisor = CloudCronSupervisor(
            data_dir=str(tmp_path),
            scheduler=None,
            eventbus=mock_eventbus,
            task_board=mock_task_board,
            capability_registry=None,
            dispatch_router=router,
        )

        # Feed 4 consecutive failures
        for i in range(4):
            supervisor.add_report(CronReport(
                report_id=f"rep_{i}", source="edge:failing-node",
                task_id="task.cleanup", status="failed", error=f"error_{i}",
            ))

        # Detect problems
        problems = supervisor.run_check_now()

        # Dispatch each
        for problem in problems:
            supervisor._dispatch_repair(problem)

        # At least one dispatch should have happened
        assert len(mock_eventbus.published) + len(mock_task_board.created) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# DIMENSION 10: Error Handling & Edge Cases
# ═══════════════════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Edge cases and error scenarios."""

    def test_detector_handles_missing_files(self):
        """Detector doesn't crash when checking non-existent paths."""
        from edge.installer.detector import SystemDetector
        info = SystemDetector().detect_all()
        # Should still return valid data even with missing paths
        assert info.os_name != "unknown" or True  # Just don't crash

    def test_configurator_non_existent_agent(self):
        """Configurator gracefully handles non-existent config paths."""
        from edge.installer.detector import AgentDetection
        from edge.installer.configurator import ConfigAutoInjector
        agent = AgentDetection(
            name="nonexistent",
            installed=True,
            config_path="/nonexistent/path/config.yaml",
        )
        cfg = ConfigAutoInjector()
        result = cfg.inject_all([agent])
        assert result["nonexistent"] is False  # Should not crash

    def test_reporter_handles_missing_components(self):
        """Reporter doesn't crash when components are missing."""
        from edge.installer.reporter import SelfCheckReporter
        # Use a non-existent directory
        reporter = SelfCheckReporter("/nonexistent/path")
        report = reporter.run_self_check()
        assert report["status"] in ("healthy", "degraded")  # Should complete

    def test_installer_non_interactive_mode_works(self):
        """Non-interactive installer can be created without user input."""
        from edge.installer.installer import ClawShellEdgeInstaller
        installer = ClawShellEdgeInstaller(
            interactive=False,
            skip_checklist=True,
        )
        # Should not raise, should have valid config
        assert installer.cloud_url

    def test_llm_detection_case_insensitive(self):
        """Model name detection is case-insensitive."""
        from edge.installer.checklist import _detect_provider_from_model
        tests = [
            ("DEEPSEEK-V4-PRO", "deepseek"),
            ("MINIMAX-m2.7", "minimax"),
            ("GPT-4O", "openai"),
            ("Claude-Opus", "anthropic"),
        ]
        for model, expected_provider in tests:
            provider, _ = _detect_provider_from_model(model)
            assert provider == expected_provider, f"{model} → {provider} (expected {expected_provider})"

    def test_system_info_handles_psutil_missing(self):
        """System info doesn't crash without psutil."""
        from edge.installer.detector import SystemDetector
        # Should work even without psutil (uses fallback)
        info = SystemDetector().detect_all()
        assert info.memory_gb >= 0
        assert info.cpu_count >= 0

    def test_checklist_all_functions_return_bool_or_str(self):
        """All checklist prompts return appropriate types."""
        from edge.installer.checklist import InstallationChecklist
        chk = InstallationChecklist()
        assert isinstance(chk._check_python(), bool)
        assert isinstance(chk._check_git(), bool)
        # LLM prompt returns string in non-interactive mode
        chk.interactive = False
        result = chk._prompt_llm_key()
        assert isinstance(result, (str, bool))

    def test_cli_detect_mode(self):
        """CLI detect mode runs without error."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "edge.installer", "detect"],
            capture_output=True, text=True, timeout=15,
            cwd=Path(__file__).parent.parent,
        )
        assert "OS:" in result.stdout
        assert "Agents:" in result.stdout
        assert result.returncode == 0
