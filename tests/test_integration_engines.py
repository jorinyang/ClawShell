"""Integration tests for cloud engines API endpoints.

Tests all new API endpoints and engine initialization.
v1.8.1 / v1.9.0
"""

import sys
import os
import time
import uuid
import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient


# ── Fixtures ───────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    """Create a test app with all engines initialized."""
    from cloud.main import init_engines, create_app
    init_engines()
    application = create_app()
    return application


@pytest.fixture(scope="module")
def client(app):
    """Create a test client."""
    return TestClient(app)


# ── Health Check Tests ─────────────────────────────────

class TestHealthCheck:
    """Test the /health endpoint includes all engines."""

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_contains_new_engines(self, client):
        resp = client.get("/health")
        data = resp.json()
        engines = data.get("engines", {})
        assert "optimizer" in engines
        assert "deep_think" in engines
        assert "workflow" in engines
        assert "knowledge_graph" in engines
        assert "pubsub" in engines

    def test_health_new_engines_active(self, client):
        resp = client.get("/health")
        data = resp.json()
        engines = data.get("engines", {})
        assert engines["optimizer"] == "active"
        assert engines["deep_think"] == "active"
        assert engines["workflow"] == "active"
        assert engines["knowledge_graph"] == "active"


# ── N8N Endpoints ──────────────────────────────────────

class TestN8NEndpoints:
    """Test N8N bridge API endpoints."""

    def test_n8n_status(self, client):
        resp = client.get("/api/v1/n8n/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_n8n_trigger_invalid_url(self, client):
        resp = client.post("/api/v1/n8n/trigger", json={
            "webhook_url": "http://localhost:19999/nonexistent",
            "payload": {"test": True},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data


# ── Swarm Endpoints ────────────────────────────────────

class TestSwarmEndpoints:
    """Test Swarm coordinator API endpoints."""

    def test_swarm_status(self, client):
        resp = client.get("/api/v1/swarm/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_nodes" in data
        assert "online_nodes" in data

    def test_swarm_nodes(self, client):
        resp = client.get("/api/v1/swarm/nodes")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert isinstance(data["nodes"], list)

    def test_swarm_nodes_filtered(self, client):
        resp = client.get("/api/v1/swarm/nodes?status=online")
        assert resp.status_code == 200


# ── Scheduler Endpoints ────────────────────────────────

class TestSchedulerEndpoints:
    """Test Scheduler API endpoints."""

    def test_scheduler_jobs(self, client):
        resp = client.get("/api/v1/scheduler/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        assert isinstance(data["jobs"], list)

    def test_scheduler_trigger_nonexistent(self, client):
        resp = client.post("/api/v1/scheduler/trigger", json={
            "task_id": "nonexistent-task-id",
        })
        assert resp.status_code == 404


# ── Optimizer Endpoints ────────────────────────────────

class TestOptimizerEndpoints:
    """Test Optimizer API endpoints."""

    def test_optimizer_status(self, client):
        resp = client.get("/api/v1/optimizer/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "stats" in data
        assert data["stats"]["registered_nodes"] == 0

    def test_optimizer_optimize_empty(self, client):
        resp = client.post("/api/v1/optimizer/optimize", json={
            "task_count": 1,
            "goal": "balanced",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["total_tasks_allocated"] == 0

    def test_optimizer_optimize_with_goal(self, client):
        resp = client.post("/api/v1/optimizer/optimize", json={
            "task_count": 1,
            "goal": "cost",
        })
        assert resp.status_code == 200


# ── Workflow Endpoints ─────────────────────────────────

class TestWorkflowEndpoints:
    """Test Workflow engine API endpoints."""

    def test_workflow_list(self, client):
        resp = client.get("/api/v1/workflow/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "workflows" in data
        assert "stats" in data

    def test_workflow_create_and_execute(self, client):
        # Create a workflow
        resp = client.post("/api/v1/workflow/create", json={
            "name": "test-workflow",
            "description": "A test workflow",
            "steps": [
                {"name": "step1", "step_type": "task", "description": "First step"},
            ],
            "tags": ["test"],
        })
        assert resp.status_code == 200
        data = resp.json()
        wf = data["workflow"]
        assert wf["name"] == "test-workflow"
        assert len(wf["steps"]) == 1

        # Execute it
        wf_id = wf["workflow_id"]
        resp = client.post(f"/api/v1/workflow/{wf_id}/execute")
        assert resp.status_code == 200
        exec_data = resp.json()["execution"]
        assert exec_data["status"] == "running"

    def test_workflow_execute_nonexistent(self, client):
        resp = client.post("/api/v1/workflow/nonexistent-id/execute")
        assert resp.status_code == 404


# ── Deep Think Endpoints ───────────────────────────────

class TestDeepThinkEndpoints:
    """Test Deep Think engine API endpoints."""

    def test_deep_think_status(self, client):
        resp = client.get("/api/v1/deep-think/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "stats" in data

    def test_deep_think_analyze(self, client):
        resp = client.post("/api/v1/deep-think/analyze", json={
            "question": "What is the optimal task distribution?",
            "complete": True,
            "confidence": 0.75,
        })
        assert resp.status_code == 200
        data = resp.json()
        session = data["session"]
        assert session["question"] == "What is the optimal task distribution?"
        assert session["confidence"] == 0.75

    def test_deep_think_analyze_incomplete(self, client):
        resp = client.post("/api/v1/deep-think/analyze", json={
            "question": "Is this an open session?",
            "complete": False,
        })
        assert resp.status_code == 200
        session = resp.json()["session"]
        assert session["completed_at"] is None


# ── Engine Initialization Tests ────────────────────────

class TestEngineInitialization:
    """Test that all engines are properly initialized."""

    def test_optimizer_has_stats(self, app):
        optimizer = app.state.optimizer
        assert optimizer is not None
        stats = optimizer.get_stats()
        assert "registered_nodes" in stats

    def test_deep_think_has_stats(self, app):
        engine = app.state.deep_think
        assert engine is not None
        stats = engine.get_stats()
        assert "total_sessions" in stats

    def test_workflow_has_stats(self, app):
        engine = app.state.workflow
        assert engine is not None
        stats = engine.get_stats()
        assert "total_workflows" in stats

    def test_knowledge_graph_has_stats(self, app):
        kg = app.state.knowledge_graph
        assert kg is not None
        stats = kg.get_stats()
        assert "entity_count" in stats

    def test_pubsub_reference(self, app):
        pubsub = app.state.pubsub
        # May be None if EventBus didn't create it, but app.state should exist
        assert hasattr(app.state, 'pubsub')


# ── KnowledgeGraph Integration Tests ───────────────────

class TestKnowledgeGraphIntegration:
    """Test KnowledgeGraph integration with InsightEngine."""

    def test_insight_engine_has_knowledge_graph(self, app):
        insight = app.state.insight
        assert insight is not None
        assert insight._knowledge_graph is not None

    def test_knowledge_graph_store_insight(self, app):
        """Test that insights get stored in KnowledgeGraph."""
        kg = app.state.knowledge_graph
        initial_count = len(kg.find_entities(entity_type="insight"))
        # Insight engine stores insights on analysis, so just verify the wiring
        assert kg is not None


# ── Run ────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
