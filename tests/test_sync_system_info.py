"""Tests for SyncDaemon system info integration in health reports."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def daemon():
    """Create an EdgeSyncDaemon instance with mocked CloudClient."""
    with patch("edge.sync.daemon.CloudClient"):
        from edge.sync.daemon import EdgeSyncDaemon
        d = EdgeSyncDaemon(
            cloud_url="http://localhost:9999",
            edge_token="test-token",
            edge_id="test-edge-001",
            data_dir="/tmp/test-clawshell-edge",
        )
        return d


# ── _system_info property tests ──────────────────────────


class TestSystemInfoProperty:
    """Test the _system_info cached property."""

    def test_returns_dict(self, daemon):
        result = daemon._system_info
        assert isinstance(result, dict)

    def test_contains_expected_fields(self, daemon):
        result = daemon._system_info
        expected_fields = {
            "hostname", "ip_address", "os", "os_version",
            "python_version", "cpu_count", "memory_total_mb",
        }
        assert expected_fields.issubset(set(result.keys())), (
            f"Missing fields: {expected_fields - set(result.keys())}"
        )

    def test_caches_result(self, daemon):
        """System info should be cached — same object returned on repeat calls."""
        first = daemon._system_info
        second = daemon._system_info
        assert first is second

    def test_handles_import_error(self, daemon):
        """If detect_system_info fails, property returns empty dict."""
        with patch.dict("sys.modules", {"edge.detector.system": None}):
            # Clear any cached value
            if hasattr(daemon, "_cached_sys_info"):
                delattr(daemon, "_cached_sys_info")
            result = daemon._system_info
            assert isinstance(result, dict)


# ── _report_health tests ─────────────────────────────────


class TestReportHealthIncludesSystemInfo:
    """Test that _report_health includes system info fields."""

    def test_health_payload_has_system_fields(self, daemon):
        """Health dict should have hostname, ip_address, os, os_version as top-level keys."""
        # Mock psutil so the psutil branch runs
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = 50.0
        mock_mem = MagicMock()
        mock_mem.percent = 60.0
        mock_psutil.virtual_memory.return_value = mock_mem
        mock_disk = MagicMock()
        mock_disk.percent = 70.0
        mock_psutil.disk_usage.return_value = mock_disk

        captured_health = {}

        def mock_report_health(data):
            captured_health.update(data)
            return {"success": True}

        daemon._client.report_health = mock_report_health

        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            with patch("edge.detector.detect_all_frameworks", side_effect=ImportError):
                with patch("edge.ide_bridge.detect_ide_tools", side_effect=ImportError):
                    daemon._report_health()

        # Verify system info fields are present as top-level keys
        assert "hostname" in captured_health, "hostname missing from health payload"
        assert "ip_address" in captured_health, "ip_address missing from health payload"
        assert "os" in captured_health, "os missing from health payload"
        assert "os_version" in captured_health, "os_version missing from health payload"
        assert "python_version" in captured_health, "python_version missing from health payload"
        assert "cpu_count" in captured_health, "cpu_count missing from health payload"
        assert "memory_total_mb" in captured_health, "memory_total_mb missing from health payload"

    def test_health_fields_are_top_level_not_nested(self, daemon):
        """System info fields should be top-level in the health dict, not under metrics."""
        captured_health = {}

        def mock_report_health(data):
            captured_health.update(data)
            return {"success": True}

        daemon._client.report_health = mock_report_health

        with patch.dict("sys.modules", {"psutil": MagicMock()}):
            with patch("edge.detector.detect_all_frameworks", side_effect=ImportError):
                with patch("edge.ide_bridge.detect_ide_tools", side_effect=ImportError):
                    daemon._report_health()

        # Top-level check
        assert "hostname" in captured_health
        assert "ip_address" in captured_health
        assert "os" in captured_health

        # Metrics should NOT contain these
        metrics = captured_health.get("metrics", {})
        assert "hostname" not in metrics, "hostname should not be nested under metrics"
        assert "ip_address" not in metrics, "ip_address should not be nested under metrics"

    def test_health_node_id_preserved(self, daemon):
        """node_id should still be present in the health payload."""
        captured_health = {}

        def mock_report_health(data):
            captured_health.update(data)
            return {"success": True}

        daemon._client.report_health = mock_report_health

        with patch.dict("sys.modules", {"psutil": MagicMock()}):
            with patch("edge.detector.detect_all_frameworks", side_effect=ImportError):
                with patch("edge.ide_bridge.detect_ide_tools", side_effect=ImportError):
                    daemon._report_health()

        assert "node_id" in captured_health, "node_id missing from health payload"

    def test_health_report_counter_increments(self, daemon):
        """health_reports stat should increment after _report_health."""
        daemon._client.report_health = MagicMock(return_value={"success": True})
        initial = daemon._stats["health_reports"]

        with patch.dict("sys.modules", {"psutil": MagicMock()}):
            with patch("edge.detector.detect_all_frameworks", side_effect=ImportError):
                with patch("edge.ide_bridge.detect_ide_tools", side_effect=ImportError):
                    daemon._report_health()

        assert daemon._stats["health_reports"] == initial + 1

    def test_health_system_info_values_are_nonempty(self, daemon):
        """System info values in health should be non-empty (using live detect)."""
        captured_health = {}

        def mock_report_health(data):
            captured_health.update(data)
            return {"success": True}

        daemon._client.report_health = mock_report_health

        with patch.dict("sys.modules", {"psutil": MagicMock()}):
            with patch("edge.detector.detect_all_frameworks", side_effect=ImportError):
                with patch("edge.ide_bridge.detect_ide_tools", side_effect=ImportError):
                    daemon._report_health()

        assert len(captured_health["hostname"]) > 0, "hostname is empty"
        assert len(captured_health["ip_address"]) > 0, "ip_address is empty"
        assert len(captured_health["os"]) > 0, "os is empty"
        assert captured_health["cpu_count"] > 0, "cpu_count should be > 0"


# ── Integration: actual detect_system_info ────────────────


class TestSystemInfoLive:
    """Test with actual detect_system_info (no mocking)."""

    def test_detect_system_info_returns_real_values(self):
        from edge.detector.system import detect_system_info
        info = detect_system_info()
        assert isinstance(info["hostname"], str)
        assert len(info["hostname"]) > 0
        assert isinstance(info["ip_address"], str)
        assert "." in info["ip_address"]  # Looks like an IP
        assert isinstance(info["os"], str)
        assert len(info["os"]) > 0
        assert isinstance(info["os_version"], str)
        assert isinstance(info["python_version"], str)
        assert isinstance(info["cpu_count"], int)
        assert info["cpu_count"] >= 0
        assert isinstance(info["memory_total_mb"], (int, float))
