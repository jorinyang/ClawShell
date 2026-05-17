"""Integration tests for MemoryServer + UnifiedMemoryManager.

Tests the 4th-layer HNSW integration without requiring external services
(MemPalace, MemOS Local, MemOS Cloud are all mocked/absent).
"""

import json
import os
import sys
import shutil
import tempfile
import uuid

import pytest

# Ensure the clawshell root is on sys.path
CLAWSHELL_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, CLAWSHELL_ROOT)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """Give each test its own unified-memory data directory."""
    data_dir = str(tmp_path / "unified_memory")
    monkeypatch.setenv("CLAWSHELL_UNIFIED_MEMORY_PATH", data_dir)
    # Reset the lazy singleton so each test gets a fresh manager
    import edge.mcp.memory_server as ms
    ms._unified_mgr = None
    # Also update the module-level path (computed at import time)
    monkeypatch.setattr(ms, "UNIFIED_MEMORY_PATH", data_dir)
    yield
    ms._unified_mgr = None


@pytest.fixture
def server_module():
    """Import and return the memory_server module."""
    import edge.mcp.memory_server as ms
    return ms


# ── Helper: simulate a JSON-RPC call ─────────────────────────


def _call_tool(server_module, tool_name: str, arguments: dict) -> dict:
    """Simulate a tools/call JSON-RPC request and return the parsed result."""
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    resp = server_module.handle_request(msg)
    assert resp is not None, "handle_request returned None"
    assert "result" in resp, f"No result in response: {resp}"
    text = resp["result"]["content"][0]["text"]
    return json.loads(text)


# ── Tests ─────────────────────────────────────────────────────


class TestUnifiedStoreAndSearch:
    """Store a memory and search it back via the unified layer."""

    def test_store_to_unified_layer(self, server_module):
        """Storing should succeed and include 'unified' in stored_to."""
        result = _call_tool(server_module, "clawshell_memory_store", {
            "content": "ClawShell v2 introduces HNSW vector search for memory",
            "category": "knowledge",
        })
        assert "unified" in result["stored_to"], (
            f"'unified' not in stored_to: {result}"
        )
        assert "content_preview" in result

    def test_search_returns_unified_results(self, server_module):
        """After storing, searching should return results from the unified layer."""
        # Store content that closely matches the query (same key tokens)
        content = "quick brown fox jumps lazy dog"
        _call_tool(server_module, "clawshell_memory_store", {
            "content": content,
            "category": "fact",
        })

        # Directly test search_unified (bypasses dedup with other layers)
        unified_results = server_module.search_unified("quick brown fox jumps lazy dog", limit=10)
        assert len(unified_results) >= 1, (
            f"Expected at least 1 unified result, got {len(unified_results)}"
        )
        assert unified_results[0]["source"] == "unified"
        assert "quick brown fox" in unified_results[0]["content"]

        # Also verify via full search (may be deduped against mempalace)
        result = _call_tool(server_module, "clawshell_memory_search", {
            "query": "quick brown fox jumps lazy dog",
        })
        # The content should appear at least once (from any source)
        all_contents = [r["content"] for r in result["results"]]
        assert any("quick brown fox" in c for c in all_contents), (
            f"Content not found in any source: {all_contents}"
        )

    def test_search_empty_query_returns_error(self, server_module):
        """Empty query should return an error, not crash."""
        result = _call_tool(server_module, "clawshell_memory_search", {
            "query": "",
        })
        assert "error" in result

    def test_store_empty_content_returns_error(self, server_module):
        """Empty content should return an error."""
        result = _call_tool(server_module, "clawshell_memory_store", {
            "content": "",
        })
        assert "error" in result


class TestCategoryClassification:
    """Category strings should map to correct MemoryType values."""

    def test_knowledge_maps_to_semantic(self, server_module):
        result = _call_tool(server_module, "clawshell_memory_store", {
            "content": "Python is a programming language",
            "category": "knowledge",
        })
        assert "unified" in result["stored_to"]

        # Verify via direct search
        mgr = server_module._get_unified_manager()
        hits = mgr.search("Python programming language", k=5)
        assert len(hits) >= 1
        assert hits[0].memory.memory_type.value == "semantic"

    def test_skill_maps_to_procedural(self, server_module):
        result = _call_tool(server_module, "clawshell_memory_store", {
            "content": "How to deploy a Kubernetes cluster",
            "category": "skill",
        })
        assert "unified" in result["stored_to"]

        mgr = server_module._get_unified_manager()
        hits = mgr.search("deploy Kubernetes cluster", k=5)
        assert len(hits) >= 1
        assert hits[0].memory.memory_type.value == "procedural"

    def test_unknown_category_defaults_to_semantic(self, server_module):
        result = _call_tool(server_module, "clawshell_memory_store", {
            "content": "Some random content with no clear category",
            "category": "general",
        })
        assert "unified" in result["stored_to"]

        mgr = server_module._get_unified_manager()
        hits = mgr.search("random content category", k=5)
        assert len(hits) >= 1
        assert hits[0].memory.memory_type.value == "semantic"


class TestConsolidate:
    """Test the consolidate tool."""

    def test_consolidate_returns_summary(self, server_module):
        """Consolidate should return a summary dict with expired/merged/evicted."""
        # Store a few memories first
        for i in range(3):
            _call_tool(server_module, "clawshell_memory_store", {
                "content": f"Memory entry number {i} for consolidation test",
                "category": "fact",
            })

        result = _call_tool(server_module, "clawshell_memory_consolidate", {})
        assert result.get("status") == "ok", f"Consolidate failed: {result}"
        assert "consolidation" in result
        summary = result["consolidation"]
        assert "expired" in summary
        assert "merged" in summary
        assert "evicted" in summary
        assert isinstance(summary["expired"], int)
        assert isinstance(summary["merged"], int)
        assert isinstance(summary["evicted"], int)

    def test_consolidate_detects_duplicates(self, server_module):
        """Duplicate content should be merged during consolidation."""
        content = "This is a duplicate memory that should be merged"
        _call_tool(server_module, "clawshell_memory_store", {
            "content": content,
            "category": "fact",
        })
        _call_tool(server_module, "clawshell_memory_store", {
            "content": content,  # exact duplicate
            "category": "fact",
        })

        mgr = server_module._get_unified_manager()
        size_before = mgr.size
        assert size_before >= 2, "Expected at least 2 entries before consolidation"

        result = _call_tool(server_module, "clawshell_memory_consolidate", {})
        assert result["status"] == "ok"
        # After consolidation, duplicates should be merged
        assert result["entries_after"] < size_before, (
            f"Expected fewer entries after dedup: {size_before} -> {result['entries_after']}"
        )
        assert result["consolidation"]["merged"] >= 1

    def test_consolidate_when_unavailable(self, server_module):
        """If UnifiedMemoryManager is None, consolidate should return an error."""
        # Force the manager to None
        server_module._unified_mgr = None
        # Monkey-patch _get_unified_manager to return None
        orig = server_module._get_unified_manager
        server_module._get_unified_manager = lambda: None
        try:
            result = _call_tool(server_module, "clawshell_memory_consolidate", {})
            assert "error" in result
        finally:
            server_module._get_unified_manager = orig


class TestHNWSSearchQuality:
    """Verify that HNSW-powered search returns relevant results."""

    def test_semantic_relevance(self, server_module):
        """Search for related content should surface it."""
        memories = [
            "Machine learning is a subset of artificial intelligence",
            "Deep learning uses neural networks with many layers",
            "Reinforcement learning trains agents via reward signals",
            "The weather today is sunny and warm",
        ]
        for content in memories:
            _call_tool(server_module, "clawshell_memory_store", {
                "content": content,
                "category": "knowledge",
            })

        # Search for ML-related content
        result = _call_tool(server_module, "clawshell_memory_search", {
            "query": "artificial intelligence neural networks",
        })
        unified = [r for r in result["results"] if r["source"] == "unified"]
        assert len(unified) >= 1
        # The ML-related entries should appear
        contents = [r["content"] for r in unified]
        ml_found = any(
            "machine learning" in c.lower() or "deep learning" in c.lower()
            or "neural network" in c.lower()
            for c in contents
        )
        assert ml_found, f"Expected ML-related content in results: {contents}"

    def test_search_score_present(self, server_module):
        """Unified results should include a score field."""
        _call_tool(server_module, "clawshell_memory_store", {
            "content": "Test content for score verification",
            "category": "fact",
        })
        result = _call_tool(server_module, "clawshell_memory_search", {
            "query": "test content score verification",
        })
        unified = [r for r in result["results"] if r["source"] == "unified"]
        assert len(unified) >= 1
        for r in unified:
            assert "score" in r, f"Missing 'score' field in result: {r}"
            assert isinstance(r["score"], (int, float))
            assert 0 <= r["score"] <= 1


class TestDeduplication:
    """Test cross-source deduplication logic."""

    def test_deduplicate_identical_content(self, server_module):
        """Two results with identical content from different sources should dedup."""
        results = [
            {"source": "mempalace", "content": "Hello world test", "key": "1"},
            {"source": "unified", "content": "Hello world test", "key": "2", "score": 0.9},
        ]
        deduped = server_module._deduplicate_results(results)
        assert len(deduped) == 1

    def test_deduplicate_different_content(self, server_module):
        """Different content should not be deduplicated."""
        results = [
            {"source": "mempalace", "content": "Completely different content A", "key": "1"},
            {"source": "unified", "content": "Another totally distinct entry B", "key": "2", "score": 0.5},
        ]
        deduped = server_module._deduplicate_results(results)
        assert len(deduped) == 2

    def test_deduplicate_empty_list(self, server_module):
        """Empty input should return empty output."""
        assert server_module._deduplicate_results([]) == []


class TestToolsList:
    """Verify the MCP tools/list endpoint includes all 4 tools."""

    def test_tools_list_includes_consolidate(self, server_module):
        msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }
        resp = server_module.handle_request(msg)
        tool_names = [t["name"] for t in resp["result"]["tools"]]
        assert "clawshell_memory_search" in tool_names
        assert "clawshell_memory_store" in tool_names
        assert "clawshell_memory_stats" in tool_names
        assert "clawshell_memory_consolidate" in tool_names
        assert len(tool_names) == 4


class TestMemoryStats:
    """Verify stats endpoint works (other layers may be unreachable)."""

    def test_stats_returns_dict(self, server_module):
        result = _call_tool(server_module, "clawshell_memory_stats", {})
        assert isinstance(result, dict)
        assert "mempalace" in result
        assert "memos_cloud" in result
        assert "memos_local" in result
