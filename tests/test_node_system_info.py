"""Tests for node system info storage and health report updates.

Verifies that:
- Registration with system info stores hostname, ip_address, os, os_version, etc.
- Health report updates system info in both registry and SQLite
"""

import sys
import os
import time
import json
import tempfile
import sqlite3

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")

import pytest


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Use a temp SQLite database for each test."""
    db_path = str(tmp_path / "test_clawshell.db")
    monkeypatch.setenv("CLAWSHELL_DB_PATH", db_path)
    # Reset the thread-local connection so it picks up the new path
    from cloud.auth import database
    database.DB_PATH = db_path
    import threading
    database._local = threading.local()
    database.init_database()
    yield


@pytest.fixture
def registry(tmp_path):
    """Create a fresh CapabilityRegistry for each test."""
    from cloud.engines.capability_registry import CapabilityRegistry
    reg = CapabilityRegistry(data_dir=str(tmp_path / "data"))
    return reg


@pytest.fixture
def app(registry):
    """Create a minimal FastAPI app with the nodes router."""
    from fastapi import FastAPI
    from cloud.routers.nodes import router

    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.state.capability_registry = registry
    application.state.topology = None
    return application


@pytest.fixture
def client(app):
    """Create a test client."""
    from fastapi.testclient import TestClient
    return TestClient(app)


# ── Test: Register with system info stores in SQLite ──────────────

def test_register_stores_system_info_in_sqlite(client, registry):
    """Registering a node with system info should persist hostname,
    ip_address, os, os_version, python_version, cpu_count, memory_total_mb
    to the SQLite edge_nodes table."""
    payload = {
        "node_id": "node-sys-001",
        "node_name": "edge-pi",
        "node_type": "edge",
        "ip_address": "192.168.1.100",
        "hostname": "raspberrypi",
        "os": "Linux",
        "os_version": "6.1.0-rpi7-rpi-v8",
        "python_version": "3.11.2",
        "cpu_count": 4,
        "memory_total_mb": 8192,
        "capabilities": ["inference"],
    }

    resp = client.post("/api/v1/nodes/register", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    # Verify in-memory registry
    node = registry.get_node("node-sys-001")
    assert node is not None
    assert node["hostname"] == "raspberrypi"
    assert node["ip_address"] == "192.168.1.100"
    assert node["os"] == "Linux"
    assert node["os_version"] == "6.1.0-rpi7-rpi-v8"

    # Verify SQLite
    from cloud.auth.database import db_ctx
    with db_ctx() as conn:
        row = conn.execute(
            "SELECT * FROM edge_nodes WHERE node_id = ?",
            ("node-sys-001",)
        ).fetchone()
    assert row is not None
    assert row["hostname"] == "raspberrypi"
    assert row["ip_address"] == "192.168.1.100"
    assert row["os"] == "Linux"
    assert row["os_version"] == "6.1.0-rpi7-rpi-v8"
    assert row["python_version"] == "3.11.2"
    assert row["cpu_count"] == 4
    assert row["memory_total_mb"] == 8192


def test_register_stores_minimal_system_info(client, registry):
    """Registering with only some system info fields should still work,
    with missing fields defaulting to empty/zero."""
    payload = {
        "node_id": "node-min-001",
        "node_name": "edge-minimal",
        "hostname": "mini-host",
        "ip_address": "10.0.0.5",
    }

    resp = client.post("/api/v1/nodes/register", json=payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    from cloud.auth.database import db_ctx
    with db_ctx() as conn:
        row = conn.execute(
            "SELECT * FROM edge_nodes WHERE node_id = ?",
            ("node-min-001",)
        ).fetchone()
    assert row is not None
    assert row["hostname"] == "mini-host"
    assert row["ip_address"] == "10.0.0.5"
    assert row["os"] == ""  # not provided, defaults to empty
    assert row["os_version"] == ""
    assert row["cpu_count"] == 0
    assert row["memory_total_mb"] == 0


# ── Test: Health report updates system info ───────────────────────

def test_health_report_updates_system_info(client, registry):
    """Health report with system info fields should update both registry
    and SQLite."""
    # First register the node
    registry.register({
        "node_id": "node-hr-001",
        "node_name": "edge-hr",
        "ip_address": "192.168.1.50",
    })

    # Now send a health report with updated system info
    health_payload = {
        "node_id": "node-hr-001",
        "metrics": {"cpu_percent": 45.0, "memory_percent": 60.0},
        "hostname": "updated-host",
        "ip_address": "192.168.1.99",
        "os": "Linux",
        "os_version": "22.04",
    }

    resp = client.post("/api/v1/health/report", json=health_payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verify registry updated
    node = registry.get_node("node-hr-001")
    assert node["hostname"] == "updated-host"
    assert node["ip_address"] == "192.168.1.99"
    assert node["os"] == "Linux"
    assert node["os_version"] == "22.04"

    # Verify SQLite updated
    from cloud.auth.database import db_ctx
    with db_ctx() as conn:
        row = conn.execute(
            "SELECT * FROM edge_nodes WHERE node_id = ?",
            ("node-hr-001",)
        ).fetchone()
    assert row is not None
    assert row["hostname"] == "updated-host"
    assert row["ip_address"] == "192.168.1.99"
    assert row["os"] == "Linux"
    assert row["os_version"] == "22.04"


def test_health_report_auto_registers_with_system_info(client, registry):
    """Health report from an unknown node should auto-register it
    and store system info."""
    health_payload = {
        "node_id": "node-auto-001",
        "metrics": {"cpu_percent": 10.0},
        "hostname": "auto-host",
        "ip_address": "172.16.0.1",
        "os": "Darwin",
        "os_version": "23.4.0",
    }

    resp = client.post("/api/v1/health/report", json=health_payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Node should exist in registry (auto-registered)
    node = registry.get_node("node-auto-001")
    assert node is not None

    # System info should be updated in registry
    assert node.get("hostname") == "auto-host"
    assert node.get("ip_address") == "172.16.0.1"
    assert node.get("os") == "Darwin"
    assert node.get("os_version") == "23.4.0"

    # SQLite should also have it
    from cloud.auth.database import db_ctx
    with db_ctx() as conn:
        row = conn.execute(
            "SELECT * FROM edge_nodes WHERE node_id = ?",
            ("node-auto-001",)
        ).fetchone()
    assert row is not None
    assert row["hostname"] == "auto-host"
    assert row["os"] == "Darwin"


def test_health_report_without_system_info_preserves_existing(client, registry):
    """Health report without system info fields should not overwrite
    previously stored system info."""
    # Register with full system info
    registry.register({
        "node_id": "node-preserve-001",
        "node_name": "edge-preserve",
        "hostname": "keep-this",
        "os": "Linux",
        "os_version": "5.15",
        "ip_address": "10.10.10.10",
    })
    # Sync to SQLite
    from cloud.routers.nodes import _sync_node_to_sqlite
    _sync_node_to_sqlite("node-preserve-001", {
        "node_name": "edge-preserve",
        "hostname": "keep-this",
        "os": "Linux",
        "os_version": "5.15",
        "ip_address": "10.10.10.10",
        "status": "online",
    })

    # Send health report WITHOUT system info
    health_payload = {
        "node_id": "node-preserve-001",
        "metrics": {"cpu_percent": 30.0},
    }

    resp = client.post("/api/v1/health/report", json=health_payload)
    assert resp.status_code == 200

    # System info should still be preserved
    from cloud.auth.database import db_ctx
    with db_ctx() as conn:
        row = conn.execute(
            "SELECT * FROM edge_nodes WHERE node_id = ?",
            ("node-preserve-001",)
        ).fetchone()
    assert row is not None
    assert row["hostname"] == "keep-this"
    assert row["os"] == "Linux"
    assert row["os_version"] == "5.15"
    assert row["ip_address"] == "10.10.10.10"


# ── Test: _sync_node_to_sqlite directly ──────────────────────────

def test_sync_node_to_sqlite_creates_table_and_stores_info(tmp_path, monkeypatch):
    """Direct test of _sync_node_to_sqlite with system info fields."""
    db_path = str(tmp_path / "direct_test.db")
    monkeypatch.setenv("CLAWSHELL_DB_PATH", db_path)
    from cloud.auth import database
    database.DB_PATH = db_path
    import threading
    database._local = threading.local()
    database.init_database()

    from cloud.routers.nodes import _sync_node_to_sqlite

    node_info = {
        "node_name": "direct-node",
        "node_type": "gpu",
        "status": "online",
        "ip_address": "10.0.0.1",
        "hostname": "gpu-server",
        "os": "Ubuntu",
        "os_version": "22.04",
        "python_version": "3.10.12",
        "cpu_count": 16,
        "memory_total_mb": 65536,
    }
    _sync_node_to_sqlite("node-direct-001", node_info, user_id="test-user")

    with database.db_ctx() as conn:
        row = conn.execute(
            "SELECT * FROM edge_nodes WHERE node_id = ?",
            ("node-direct-001",)
        ).fetchone()

    assert row is not None
    assert row["hostname"] == "gpu-server"
    assert row["os"] == "Ubuntu"
    assert row["os_version"] == "22.04"
    assert row["python_version"] == "3.10.12"
    assert row["cpu_count"] == 16
    assert row["memory_total_mb"] == 65536
    assert row["ip_address"] == "10.0.0.1"
    assert row["user_id"] == "test-user"


def test_sync_node_to_sqlite_upsert_preserves_existing(tmp_path, monkeypatch):
    """Upsert should preserve existing values when new ones are empty."""
    db_path = str(tmp_path / "upsert_test.db")
    monkeypatch.setenv("CLAWSHELL_DB_PATH", db_path)
    from cloud.auth import database
    database.DB_PATH = db_path
    import threading
    database._local = threading.local()
    database.init_database()

    from cloud.routers.nodes import _sync_node_to_sqlite

    # First insert with full info
    _sync_node_to_sqlite("node-upsert-001", {
        "node_name": "upsert-node",
        "hostname": "original-host",
        "os": "Linux",
        "ip_address": "1.2.3.4",
        "cpu_count": 8,
        "memory_total_mb": 16384,
    })

    # Second insert with partial info (should preserve existing values)
    _sync_node_to_sqlite("node-upsert-001", {
        "node_name": "upsert-node-updated",
        "status": "online",
        # hostname, os, ip_address not provided — should be preserved
    })

    with database.db_ctx() as conn:
        row = conn.execute(
            "SELECT * FROM edge_nodes WHERE node_id = ?",
            ("node-upsert-001",)
        ).fetchone()

    assert row is not None
    assert row["node_name"] == "upsert-node-updated"  # updated
    assert row["hostname"] == "original-host"  # preserved
    assert row["os"] == "Linux"  # preserved
    assert row["ip_address"] == "1.2.3.4"  # preserved
    assert row["cpu_count"] == 8  # preserved
    assert row["memory_total_mb"] == 16384  # preserved
