"""Integration tests for v2.1 CronSupervisor and DispatchRouter.

Tests the complete pipeline:
  CronReport ingestion → Problem detection → Repair dispatch → Layer fallback

Run with: pytest tests/test_integration_cron_supervisor.py -v
"""

from __future__ import annotations

import sys
import os
import time
import uuid
import threading
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from shared.models import (
    CronReport, Problem, ProblemType,
    DispatchLayer, DispatchResult, DispatchRecord,
)
from cloud.engines.dispatch_router import DispatchRouter, CLOUD_REPAIR_ACTIONS
from cloud.engines.cron_supervisor import CloudCronSupervisor
from exoskeleton.layer3.cron_reporter import CronReporter


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def mock_eventbus():
    """Minimal mock EventBus that just records publishes."""
    class MockEventBus:
        def __init__(self):
            self.published = []

        def publish(self, event_type, source, priority=50, payload=None):
            self.published.append({
                "event_type": event_type,
                "source": source,
                "priority": priority,
                "payload": payload or {},
            })

    return MockEventBus()


@pytest.fixture
def mock_task_board():
    """Minimal mock GlobalTaskBoard."""
    class MockTaskBoard:
        def __init__(self):
            self.created_tasks = []

        def create_task(self, title, description="", priority=50, tags=None, payload=None):
            task_id = f"task_{uuid.uuid4().hex[:8]}"
            self.created_tasks.append({
                "task_id": task_id,
                "title": title,
                "description": description,
                "priority": priority,
                "tags": tags or [],
                "payload": payload or {},
            })
            return {"task_id": task_id}

        def list_tasks(self):
            return self.created_tasks

    return MockTaskBoard()


@pytest.fixture
def mock_capability_registry():
    """Minimal mock CapabilityRegistry."""
    class MockCapReg:
        def __init__(self):
            self._nodes = {}

        def register_node(self, node_id, capabilities=None):
            self._nodes[node_id] = {
                "node_id": node_id,
                "capabilities": capabilities or [],
                "last_heartbeat": time.time(),
            }

        def list_nodes(self):
            return list(self._nodes.values())

    return MockCapReg()


@pytest.fixture
def dispatch_router(mock_eventbus, mock_task_board, temp_dir):
    return DispatchRouter(
        eventbus=mock_eventbus,
        task_board=mock_task_board,
        data_dir=temp_dir,
    )


@pytest.fixture
def cron_supervisor(mock_eventbus, mock_task_board, mock_capability_registry, dispatch_router, temp_dir):
    supervisor = CloudCronSupervisor(
        data_dir=temp_dir,
        scheduler=None,  # Will use problem detection without scheduler
        eventbus=mock_eventbus,
        task_board=mock_task_board,
        capability_registry=mock_capability_registry,
        dispatch_router=dispatch_router,
    )
    return supervisor


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: DispatchRouter — Layer Selection
# ═══════════════════════════════════════════════════════════════════════════════

class TestDispatchRouterLayerSelection:
    """Test that the right layer is selected for each problem type."""

    def test_edge_offline_selects_taskboard(self, dispatch_router):
        """Edge offline should go directly to TaskBoard (EventBus can't reach)."""
        problem = Problem(
            problem_id="prob_001",
            problem_type=ProblemType.EDGE_OFFLINE,
            source="edge:wsl-test",
            severity=90,
            title="Edge offline",
            description="Edge has gone dark",
        )
        layer = dispatch_router._select_layer(problem)
        assert layer == DispatchLayer.TASKBOARD

    def test_global_anomaly_selects_eventbus(self, dispatch_router):
        """Global anomaly should go to EventBus for broadcast."""
        problem = Problem(
            problem_id="prob_002",
            problem_type=ProblemType.GLOBAL_ANOMALY,
            source="cloud",
            severity=90,
            title="Global anomaly",
            description="All edges affected",
        )
        layer = dispatch_router._select_layer(problem)
        assert layer == DispatchLayer.EVENTBUS

    def test_normal_edge_problem_selects_eventbus(self, dispatch_router):
        """Normal edge problem starts with EventBus."""
        problem = Problem(
            problem_id="prob_003",
            problem_type=ProblemType.CHRONIC_FAILURE,
            source="edge:wsl-test",
            severity=80,
            title="Chronic failure",
            description="Task keeps failing",
        )
        layer = dispatch_router._select_layer(problem)
        assert layer == DispatchLayer.EVENTBUS

    def test_cloud_engine_degraded_selects_eventbus(self, dispatch_router):
        """Cloud engine problems use EventBus."""
        problem = Problem(
            problem_id="prob_004",
            problem_type=ProblemType.ENGINE_DEGRADED,
            source="cloud",
            severity=70,
            title="Engine degraded",
            description="Engine performance degraded",
        )
        layer = dispatch_router._select_layer(problem)
        assert layer == DispatchLayer.EVENTBUS


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: DispatchRouter — Dispatch Execution
# ═══════════════════════════════════════════════════════════════════════════════

class TestDispatchRouterDispatch:
    """Test dispatch execution on each layer."""

    def test_eventbus_dispatch_publishes_event(self, dispatch_router, mock_eventbus):
        """EventBus dispatch should publish to the event bus."""
        problem = Problem(
            problem_id="prob_005",
            problem_type=ProblemType.SYNC_LAG,
            source="edge:wsl-test",
            severity=60,
            title="Sync lag detected",
            description="Edge sync is behind",
            repair_action="force_sync",
        )
        record = dispatch_router.dispatch(problem, "force_sync")

        assert record.result == DispatchResult.SUCCESS
        assert record.layer == DispatchLayer.EVENTBUS
        assert len(mock_eventbus.published) == 1
        evt = mock_eventbus.published[0]
        assert evt["event_type"] == "repair.sync_lag"
        assert evt["payload"]["target"] == "edge:wsl-test"

    def test_taskboard_dispatch_creates_task(self, dispatch_router, mock_task_board):
        """TaskBoard dispatch should create a repair task."""
        problem = Problem(
            problem_id="prob_006",
            problem_type=ProblemType.EDGE_OFFLINE,
            source="edge:wsl-test",
            severity=90,
            title="Edge offline",
            description="Edge has gone dark",
            repair_action="redistribute_tasks",
        )
        record = dispatch_router.dispatch(problem, "redistribute_tasks")

        assert record.result == DispatchResult.SUCCESS
        assert record.layer == DispatchLayer.TASKBOARD
        assert len(mock_task_board.created_tasks) == 1
        task = mock_task_board.created_tasks[0]
        assert "Auto-Repair" in task["title"]
        assert task["payload"]["problem_id"] == "prob_006"

    def test_confirm_marks_record_success(self, dispatch_router):
        """confirm() should mark dispatch as success."""
        problem = Problem(
            problem_id="prob_007",
            problem_type=ProblemType.SYNC_LAG,
            source="edge:wsl-test",
            severity=60,
            title="Sync lag",
            description="Edge sync is behind",
        )
        record = dispatch_router.dispatch(problem, "force_sync")
        ok = dispatch_router.confirm(record.dispatch_id)

        assert ok is True
        updated = dispatch_router._records[record.dispatch_id]
        assert updated.result == DispatchResult.SUCCESS

    def test_report_failure_triggers_fallback(self, dispatch_router):
        """report_failure() should trigger automatic fallback to next layer."""
        problem = Problem(
            problem_id="prob_008",
            problem_type=ProblemType.CHRONIC_FAILURE,
            source="edge:wsl-test",
            severity=80,
            title="Chronic failure",
            description="Task keeps failing",
        )
        # First dispatch via EventBus
        record1 = dispatch_router.dispatch(problem, "broadcast_fix")
        assert record1.layer == DispatchLayer.EVENTBUS

        # Report failure → should fallback to TaskBoard
        record2 = dispatch_router.report_failure(record1.dispatch_id, "Edge couldn't process")

        # record2 is the new fallback dispatch
        assert record2.layer == DispatchLayer.TASKBOARD
        assert record2.problem_id == "prob_008"

    def test_dispatch_to_specific_layer(self, dispatch_router, mock_task_board):
        """dispatch_to_layer() should force a specific layer."""
        problem = Problem(
            problem_id="prob_009",
            problem_type=ProblemType.CHRONIC_FAILURE,
            source="edge:wsl-test",
            severity=80,
            title="Chronic failure",
            description="Task keeps failing",
        )
        # Force TaskBoard even though EventBus would be selected
        record = dispatch_router.dispatch_to_layer(
            problem, "schedule_maintenance", DispatchLayer.TASKBOARD
        )
        assert record.layer == DispatchLayer.TASKBOARD
        assert len(mock_task_board.created_tasks) == 1

    def test_stats_tracking(self, dispatch_router):
        """Stats should correctly track dispatch outcomes."""
        problem1 = Problem(
            problem_id="prob_010",
            problem_type=ProblemType.SYNC_LAG,
            source="edge:node-a",
            severity=60,
            title="Sync lag",
            description="Edge sync is behind",
        )
        dispatch_router.dispatch(problem1, "force_sync")

        problem2 = Problem(
            problem_id="prob_011",
            problem_type=ProblemType.EDGE_OFFLINE,
            source="edge:node-b",
            severity=90,
            title="Edge offline",
            description="Edge has gone dark",
        )
        dispatch_router.dispatch(problem2, "redistribute_tasks")

        stats = dispatch_router.get_stats()
        assert stats["total"] == 2
        assert stats["success"] == 2
        assert stats["by_layer"][DispatchLayer.EVENTBUS] == 1
        assert stats["by_layer"][DispatchLayer.TASKBOARD] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: CloudCronSupervisor — Report Ingestion
# ═══════════════════════════════════════════════════════════════════════════════

class TestCloudCronSupervisorIngestion:
    """Test CronReport ingestion and aggregation."""

    def test_add_report_stores_it(self, cron_supervisor):
        """add_report() should store report and return report_id."""
        from datetime import datetime, timezone

        report = CronReport(
            report_id="rep_test_001",
            source="edge:wsl-test",
            task_id="edge.cleanup",
            status="success",
            duration_ms=123.4,
        )
        rid = cron_supervisor.add_report(report)
        assert rid == "rep_test_001"

        reports = cron_supervisor.get_reports()
        assert len(reports) == 1
        assert reports[0].report_id == "rep_test_001"

    def test_add_report_filters_by_source(self, cron_supervisor):
        """get_reports(source=) should filter correctly."""
        from datetime import datetime, timezone

        for src in ["edge:node-a", "edge:node-a", "edge:node-b"]:
            cron_supervisor.add_report(CronReport(
                report_id=f"rep_{src.replace(':', '_')}",
                source=src,
                task_id="edge.cleanup",
                status="success",
            ))

        node_a_reports = cron_supervisor.get_reports(source="edge:node-a")
        assert len(node_a_reports) == 2

        node_b_reports = cron_supervisor.get_reports(source="edge:node-b")
        assert len(node_b_reports) == 1

    def test_get_stats(self, cron_supervisor):
        """Stats should reflect report count and problem state."""
        cron_supervisor.add_report(CronReport(
            report_id="rep_stats_001",
            source="edge:node-a",
            task_id="edge.cleanup",
            status="success",
        ))

        stats = cron_supervisor.get_stats()
        assert stats["total_reports"] == 1
        assert stats["sources"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: CloudCronSupervisor — Problem Detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestCloudCronSupervisorDetection:
    """Test the 5 detection rules."""

    def test_detect_edge_offline(self, cron_supervisor, mock_capability_registry):
        """Should detect when edge node stops sending heartbeats."""
        # Register an edge and set its last heartbeat to 5 minutes ago
        mock_capability_registry.register_node("edge:stale-node", ["cleanup"])
        node = mock_capability_registry._nodes["edge:stale-node"]
        node["last_heartbeat"] = time.time() - 500  # 500s ago (> 60s threshold)

        # Add some reports so source exists
        cron_supervisor.add_report(CronReport(
            report_id="rep_stale",
            source="edge:stale-node",
            task_id="edge.cleanup",
            status="success",
        ))

        problems = cron_supervisor._detect_edge_offline(cron_supervisor._reports)
        assert len(problems) >= 1
        offline_probs = [p for p in problems if p.problem_type == ProblemType.EDGE_OFFLINE]
        assert len(offline_probs) >= 1
        assert "stale-node" in offline_probs[0].source

    def test_detect_chronic_failures(self, cron_supervisor):
        """Should detect tasks with 3+ consecutive failures."""
        source = "edge:failing-node"
        for i in range(5):
            cron_supervisor.add_report(CronReport(
                report_id=f"rep_fail_{i}",
                source=source,
                task_id="edge.cleanup",
                status="failed",
                error=f"error_{i}",
            ))

        problems = cron_supervisor._detect_chronic_failures(cron_supervisor._reports)
        chronic = [p for p in problems if p.problem_type == ProblemType.CHRONIC_FAILURE]
        assert len(chronic) >= 1

    def test_detect_sync_lag(self, cron_supervisor):
        """Should detect edges with stale report timestamps."""
        from datetime import datetime, timezone, timedelta

        old_time = datetime.now(timezone.utc) - timedelta(seconds=400)
        cron_supervisor.add_report(CronReport(
            report_id="rep_lagged",
            source="edge:lagged-node",
            task_id="edge.cleanup",
            status="success",
            executed_at=old_time,
        ))

        problems = cron_supervisor._detect_sync_lag(cron_supervisor._reports)
        lag_probs = [p for p in problems if p.problem_type == ProblemType.SYNC_LAG]
        assert len(lag_probs) >= 1
        assert "lagged-node" in lag_probs[0].source

    def test_run_check_now_triggers_detection(self, cron_supervisor, mock_capability_registry):
        """run_check_now() should return detected problems."""
        # Add a failing edge
        mock_capability_registry.register_node("edge:offline-edge", ["cleanup"])
        node = mock_capability_registry._nodes["edge:offline-edge"]
        node["last_heartbeat"] = time.time() - 200  # Offline

        cron_supervisor.add_report(CronReport(
            report_id="rep_offline",
            source="edge:offline-edge",
            task_id="edge.cleanup",
            status="failed",
            error="node unreachable",
        ))

        problems = cron_supervisor.run_check_now()
        assert len(problems) >= 1  # At least edge_offline + chronic_failure

    def test_problems_are_deduplicated(self, cron_supervisor, mock_capability_registry):
        """Running check twice should not create duplicate problems."""
        mock_capability_registry.register_node("edge:stale2", ["cleanup"])
        node = mock_capability_registry._nodes["edge:stale2"]
        node["last_heartbeat"] = time.time() - 200

        cron_supervisor.add_report(CronReport(
            report_id="rep_stale2",
            source="edge:stale2",
            task_id="edge.cleanup",
            status="success",
        ))

        # Run check twice
        cron_supervisor.run_check_now()
        count1 = len(cron_supervisor.get_problems())

        cron_supervisor.run_check_now()
        count2 = len(cron_supervisor.get_problems())

        # Should not duplicate
        assert count2 == count1


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: Edge CronReporter
# ═══════════════════════════════════════════════════════════════════════════════

class TestCronReporter:
    """Test edge CronReporter functionality."""

    def test_report_generates_report_id(self, temp_dir):
        """report() should generate and return a report_id."""
        reporter = CronReporter(
            node_id="test-edge",
            cloud_url="http://localhost:9999",  # Won't actually connect
            data_dir=temp_dir,
        )
        rid = reporter.report(
            task_id="edge.cleanup",
            status="success",
            duration_ms=50.0,
        )
        assert rid.startswith("rep_")
        assert reporter.get_pending_count() == 1

    def test_report_persists_to_disk(self, temp_dir):
        """report() should persist pending reports to disk."""
        reporter1 = CronReporter(
            node_id="test-edge",
            cloud_url="http://localhost:9999",
            data_dir=temp_dir,
        )
        reporter1.report(task_id="edge.cleanup", status="success")

        # Create new instance — should reload from disk
        reporter2 = CronReporter(
            node_id="test-edge",
            cloud_url="http://localhost:9999",
            data_dir=temp_dir,
        )
        assert reporter2.get_pending_count() >= 1

    def test_report_from_scheduler_result(self, temp_dir):
        """report_from_scheduler_result() should extract fields correctly."""
        reporter = CronReporter(
            node_id="test-edge",
            cloud_url="http://localhost:9999",
            data_dir=temp_dir,
        )
        result = {
            "status": "failed",
            "error": "disk full",
            "duration_ms": 200.0,
            "cpu_avg": 0.8,
            "recommendations": ["cleanup_needed"],
        }
        rid = reporter.report_from_scheduler_result("edge.cleanup", result)
        assert rid.startswith("rep_")
        assert reporter.get_pending_count() == 1

    def test_stats(self, temp_dir):
        """get_stats() should return correct metrics."""
        reporter = CronReporter(
            node_id="test-edge",
            cloud_url="http://localhost:9999",
            data_dir=temp_dir,
        )
        reporter.report(task_id="edge.cleanup", status="success")
        stats = reporter.get_stats()
        assert stats["node_id"] == "test-edge"
        assert stats["pending"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: Full Pipeline (Report → Detect → Dispatch)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    """End-to-end test: report flows through to dispatch."""

    def test_report_triggers_dispatch(self, cron_supervisor, mock_eventbus, mock_task_board):
        """A failing report should eventually trigger dispatch."""
        # Add 3 consecutive failures to trigger chronic_failure
        for i in range(3):
            cron_supervisor.add_report(CronReport(
                report_id=f"rep_fail_{i}",
                source="edge:failing",
                task_id="edge.cleanup",
                status="failed",
                error=f"error_{i}",
            ))

        # Run check — should find chronic_failure
        problems = cron_supervisor.run_check_now()

        # Dispatch each problem
        for problem in problems:
            if problem.dispatch_status == "pending":
                cron_supervisor._dispatch_repair(problem)

        # At least one dispatch should have happened
        assert len(mock_eventbus.published) + len(mock_task_board.created_tasks) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# TEST: REST API (when app is available)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def app_with_supervisor():
    """Create app with CronSupervisor registered."""
    from cloud.main import init_engines, create_app
    import os
    os.makedirs("/tmp/clawshell_test_data", exist_ok=True)
    init_engines()
    application = create_app()
    return application


@pytest.fixture(scope="module")
def client_with_supervisor(app_with_supervisor):
    return TestClient(app_with_supervisor)


class TestCronSupervisorAPI:
    """Test the CronSupervisor REST API endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self, client_with_supervisor):
        self.client = client_with_supervisor

    def test_get_reports(self):
        """GET /api/v1/cron-supervisor/reports should return report list."""
        resp = self.client.get("/api/v1/cron-supervisor/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert "reports" in data
        assert "count" in data

    def test_get_problems(self):
        """GET /api/v1/cron-supervisor/problems should return problem list."""
        resp = self.client.get("/api/v1/cron-supervisor/problems")
        assert resp.status_code == 200
        data = resp.json()
        assert "problems" in data
        assert "count" in data

    def test_trigger_check(self):
        """POST /api/v1/cron-supervisor/check should trigger immediate check."""
        resp = self.client.post("/api/v1/cron-supervisor/check")
        assert resp.status_code == 200
        data = resp.json()
        assert "triggered_at" in data
        assert "problems_found" in data
        assert "problems" in data

    def test_get_stats(self):
        """GET /api/v1/cron-supervisor/stats should return stats."""
        resp = self.client.get("/api/v1/cron-supervisor/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "supervisor" in data
        assert "dispatch" in data

    def test_ingest_single_report(self):
        """POST /api/v1/cron-supervisor/reports should ingest report."""
        from datetime import datetime, timezone
        report = {
            "report_id": f"rep_api_{uuid.uuid4().hex[:8]}",
            "source": "edge:api-test",
            "task_id": "edge.cleanup",
            "status": "success",
            "duration_ms": 42.0,
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }
        resp = self.client.post("/api/v1/cron-supervisor/reports", json=report)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ingested"

    def test_ingest_batch_reports(self):
        """POST /api/v1/cron-supervisor/reports/batch should ingest batch."""
        from datetime import datetime, timezone
        reports = [
            {
                "report_id": f"rep_batch_{i}",
                "source": "edge:batch-test",
                "task_id": "edge.cleanup",
                "status": "success",
                "duration_ms": 10.0,
                "scheduled_at": datetime.now(timezone.utc).isoformat(),
                "executed_at": datetime.now(timezone.utc).isoformat(),
            }
            for i in range(3)
        ]
        resp = self.client.post("/api/v1/cron-supervisor/reports/batch", json={"reports": reports})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ingested"] == 3
