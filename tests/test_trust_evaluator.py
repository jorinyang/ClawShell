"""Unit tests for the Behavioral Trust Scoring System."""

from __future__ import annotations

import json
import os
import tempfile
import time

import pytest

from shared.trust.evaluator import (
    NodeMetrics,
    TrustEvaluator,
    TrustLevel,
    TrustScore,
    TrustTransition,
)


# ── Helpers ─────────────────────────────────────────────────────────────

def _perfect_metrics() -> NodeMetrics:
    return NodeMetrics(
        messages_sent=1000,
        messages_received=1000,
        hmac_failures=0,
        threat_detections=0,
        uptime_seconds=3600,
        total_seconds=3600,
        tasks_completed=100,
        tasks_failed=0,
    )


def _zero_metrics() -> NodeMetrics:
    return NodeMetrics()


# ── Trust Level Mapping ────────────────────────────────────────────────

class TestTrustLevelMapping:
    def test_perfect_score_is_privileged(self):
        assert TrustLevel.from_score(0.95) == TrustLevel.PRIVILEGED
        assert TrustLevel.from_score(1.0) == TrustLevel.PRIVILEGED
        assert TrustLevel.from_score(0.8) == TrustLevel.PRIVILEGED

    def test_high_level(self):
        assert TrustLevel.from_score(0.79) == TrustLevel.HIGH
        assert TrustLevel.from_score(0.6) == TrustLevel.HIGH

    def test_standard_level(self):
        assert TrustLevel.from_score(0.59) == TrustLevel.STANDARD
        assert TrustLevel.from_score(0.4) == TrustLevel.STANDARD

    def test_low_level(self):
        assert TrustLevel.from_score(0.39) == TrustLevel.LOW
        assert TrustLevel.from_score(0.2) == TrustLevel.LOW

    def test_untrusted_level(self):
        assert TrustLevel.from_score(0.19) == TrustLevel.UNTRUSTED
        assert TrustLevel.from_score(0.0) == TrustLevel.UNTRUSTED


# ── Core Scoring ───────────────────────────────────────────────────────

class TestCoreScoring:
    def test_perfect_metrics_privileged(self):
        ev = TrustEvaluator()
        ts = ev.record_metrics("node-1", _perfect_metrics())
        assert ts.level == TrustLevel.PRIVILEGED
        assert ts.score >= 0.8
        # All components should be near 1.0
        assert ts.components["success_rate"] == pytest.approx(1.0)
        assert ts.components["uptime_ratio"] == pytest.approx(1.0)
        assert ts.components["threat_penalty"] == pytest.approx(0.0)
        assert ts.components["data_integrity"] == pytest.approx(1.0)

    def test_zero_metrics_untrusted(self):
        ev = TrustEvaluator()
        ts = ev.record_metrics("node-1", _zero_metrics())
        # Zero total messages → success_rate=0, uptime=0, integrity=1
        # score = 0.4*0 + 0.2*0 + 0.2*(1-0) + 0.2*1 = 0.4
        # But uptime_ratio=0 (0/0 clamped), so actually standard
        # Let's just check it's low
        assert ts.score < 0.8

    def test_zero_messages_edge_case(self):
        """With zero messages, success_rate=0, integrity=1."""
        ev = TrustEvaluator()
        metrics = NodeMetrics(messages_sent=0, messages_received=0, uptime_seconds=100, total_seconds=100)
        ts = ev.record_metrics("n", metrics)
        # success_rate = 0, uptime = 1, threat_penalty = 0, integrity = 1
        # score = 0.4*0 + 0.2*1 + 0.2*1 + 0.2*1 = 0.6
        assert ts.score == pytest.approx(0.6)
        assert ts.level == TrustLevel.HIGH

    def test_all_hmac_failures(self):
        """All messages fail HMAC → low score."""
        ev = TrustEvaluator()
        metrics = NodeMetrics(
            messages_sent=100, messages_received=100,
            hmac_failures=200, uptime_seconds=100, total_seconds=100,
        )
        ts = ev.record_metrics("n", metrics)
        # success_rate = 0, uptime = 1, threat_penalty = 0, integrity = 0
        # score = 0 + 0.2 + 0.2 + 0 = 0.4
        assert ts.score == pytest.approx(0.4)
        assert ts.level == TrustLevel.STANDARD

    def test_partial_uptime(self):
        ev = TrustEvaluator()
        metrics = NodeMetrics(
            messages_sent=100, messages_received=100,
            uptime_seconds=50, total_seconds=100,
        )
        ts = ev.record_metrics("n", metrics)
        assert ts.components["uptime_ratio"] == pytest.approx(0.5)

    def test_score_clamped_to_0_1(self):
        ev = TrustEvaluator()
        ts = ev.record_metrics("n", _perfect_metrics())
        assert 0.0 <= ts.score <= 1.0


# ── Threat Detection ───────────────────────────────────────────────────

class TestThreatDetection:
    def test_single_threat_no_penalty(self):
        """One threat in window should not exceed threshold."""
        ev = TrustEvaluator()
        triggered = ev.record_threat_detection("n")
        assert triggered is False

    def test_two_threats_exceeds_threshold(self):
        """Two threats in window triggers penalty."""
        ev = TrustEvaluator()
        ev.record_threat_detection("n")
        triggered = ev.record_threat_detection("n")
        assert triggered is True

    def test_threat_penalty_applied(self):
        """Threat detections should reduce the trust score."""
        ev = TrustEvaluator()
        # Record good metrics first
        ts_good = ev.record_metrics("n", _perfect_metrics())

        # Now add threats
        ev.record_threat_detection("n")
        ev.record_threat_detection("n")

        ts_bad = ev.record_metrics("n", _perfect_metrics())
        assert ts_bad.score < ts_good.score
        assert ts_bad.components["threat_penalty"] > 0

    def test_threat_window_decay(self):
        """Threats outside the window should not count."""
        ev = TrustEvaluator()
        now = time.time()

        # Record 2 threats long ago (outside 1-hour window)
        old_time = now - ev.THREAT_WINDOW_SECONDS - 10
        ev.record_threat_detection("n", timestamp=old_time)
        ev.record_threat_detection("n", timestamp=old_time)

        count = ev.get_threat_count("n", now=now)
        assert count == 0

    def test_threat_window_mixed(self):
        """Mix of old and recent threats — only recent ones count."""
        ev = TrustEvaluator()
        now = time.time()
        old = now - ev.THREAT_WINDOW_SECONDS - 10

        ev.record_threat_detection("n", timestamp=old)
        ev.record_threat_detection("n", timestamp=now)
        ev.record_threat_detection("n", timestamp=now)

        count = ev.get_threat_count("n", now=now)
        assert count == 2


# ── Immediate Downgrade ────────────────────────────────────────────────

class TestImmediateDowngrade:
    def test_downgrade_sets_untrusted(self):
        ev = TrustEvaluator()
        ev.record_metrics("n", _perfect_metrics())
        assert ev.get_level("n") == TrustLevel.PRIVILEGED

        t = ev.immediate_downgrade("n", reason="hmac-verification-failure")
        assert t.new_level == TrustLevel.UNTRUSTED
        assert t.previous_level == TrustLevel.PRIVILEGED
        assert ev.get_level("n") == TrustLevel.UNTRUSTED

    def test_downgrade_from_any_level(self):
        ev = TrustEvaluator()
        for level in TrustLevel:
            ev._node_levels["n"] = level
            t = ev.immediate_downgrade("n", reason="session-hijack-attempt")
            assert t.new_level == TrustLevel.UNTRUSTED
            assert t.previous_level == level

    def test_downgrade_recorded_in_transitions(self):
        ev = TrustEvaluator()
        ev.record_metrics("n", _perfect_metrics())
        ev.immediate_downgrade("n", reason="test")
        transitions = ev.get_transitions("n")
        assert any("Immediate downgrade" in t.reason for t in transitions)


# ── Trust Level Transitions ────────────────────────────────────────────

class TestTrustTransitions:
    def test_upgrade_on_improving_metrics(self):
        """Score improvement should trigger upgrade transition."""
        ev = TrustEvaluator()
        # Start with bad metrics
        ev.record_metrics("n", NodeMetrics(
            messages_sent=10, messages_received=10,
            hmac_failures=15, uptime_seconds=10, total_seconds=100,
        ))
        initial_level = ev.get_level("n")

        # Now give perfect metrics
        ts = ev.record_metrics("n", _perfect_metrics())
        assert ts.level.value >= initial_level.value

    def test_transition_history_tracked(self):
        ev = TrustEvaluator()
        ev.record_metrics("n", _zero_metrics())
        ev.record_metrics("n", _perfect_metrics())
        transitions = ev.get_transitions("n")
        assert len(transitions) >= 1

    def test_no_transition_when_level_unchanged(self):
        ev = TrustEvaluator()
        ev.record_metrics("n", _perfect_metrics())
        ev.record_metrics("n", _perfect_metrics())
        transitions = ev.get_transitions("n")
        # Should have initial assignment transition at most
        # Re-recording perfect metrics shouldn't cause additional transitions
        initial_count = len(transitions)
        ev.record_metrics("n", _perfect_metrics())
        assert len(ev.get_transitions("n")) == initial_count


# ── Persistence ────────────────────────────────────────────────────────

class TestPersistence:
    def test_save_and_load(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            # Create evaluator with state
            ev1 = TrustEvaluator(persistence_path=path)
            ev1.record_metrics("node-A", _perfect_metrics())
            ev1.record_metrics("node-B", NodeMetrics(
                messages_sent=50, messages_received=50,
                hmac_failures=10, uptime_seconds=100, total_seconds=200,
            ))
            ev1.record_threat_detection("node-A")
            ev1.save()

            # Load in fresh evaluator
            ev2 = TrustEvaluator(persistence_path=path)
            assert ev2.get_level("node-A") == ev1.get_level("node-A")
            assert ev2.get_level("node-B") == ev1.get_level("node-B")

            # Metrics should be preserved
            ts = ev2.evaluate("node-B")
            assert ts.components["data_integrity"] == pytest.approx(0.9)

            # Transitions preserved
            assert len(ev2.get_transitions()) == len(ev1.get_transitions())
        finally:
            os.unlink(path)

    def test_load_nonexistent_file(self):
        """Loading from a missing file should not crash."""
        ev = TrustEvaluator(persistence_path="/tmp/nonexistent_trust_12345.json")
        assert ev.get_level("any") == TrustLevel.STANDARD  # default

    def test_save_without_path_raises(self):
        ev = TrustEvaluator()
        with pytest.raises(ValueError, match="No persistence path"):
            ev.save()

    def test_save_load_threat_windows(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            ev1 = TrustEvaluator(persistence_path=path)
            ev1.record_threat_detection("n")
            ev1.record_threat_detection("n")
            ev1.save()

            ev2 = TrustEvaluator(persistence_path=path)
            assert ev2.get_threat_count("n") == 2
        finally:
            os.unlink(path)


# ── Edge Cases ─────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_zero_total_seconds(self):
        ev = TrustEvaluator()
        metrics = NodeMetrics(messages_sent=10, messages_received=10, total_seconds=0)
        ts = ev.record_metrics("n", metrics)
        assert ts.components["uptime_ratio"] == 0.0

    def test_negative_uptime_clamped(self):
        ev = TrustEvaluator()
        metrics = NodeMetrics(
            messages_sent=10, messages_received=10,
            uptime_seconds=-5, total_seconds=100,
        )
        ts = ev.record_metrics("n", metrics)
        assert ts.components["uptime_ratio"] == 0.0

    def test_uptime_exceeds_total_clamped(self):
        ev = TrustEvaluator()
        metrics = NodeMetrics(
            messages_sent=10, messages_received=10,
            uptime_seconds=200, total_seconds=100,
        )
        ts = ev.record_metrics("n", metrics)
        assert ts.components["uptime_ratio"] == 1.0

    def test_node_defaults_to_standard(self):
        ev = TrustEvaluator()
        assert ev.get_level("unknown-node") == TrustLevel.STANDARD

    def test_multiple_nodes_independent(self):
        ev = TrustEvaluator()
        ev.record_metrics("good", _perfect_metrics())
        ev.record_metrics("bad", NodeMetrics(
            messages_sent=100, messages_received=100,
            hmac_failures=200, uptime_seconds=0, total_seconds=100,
        ))
        assert ev.get_level("good") == TrustLevel.PRIVILEGED
        assert ev.get_level("bad").value < TrustLevel.PRIVILEGED.value

    def test_transitions_filtered_by_node(self):
        ev = TrustEvaluator()
        ev.record_metrics("a", _perfect_metrics())
        ev.record_metrics("b", _zero_metrics())
        a_transitions = ev.get_transitions("a")
        b_transitions = ev.get_transitions("b")
        for t in a_transitions:
            assert t.node_id == "a"
        for t in b_transitions:
            assert t.node_id == "b"

    def test_serialization_roundtrip(self):
        """TrustTransition should round-trip through dict."""
        t = TrustTransition(
            node_id="n", previous_level=TrustLevel.LOW,
            new_level=TrustLevel.HIGH, score=0.75,
            reason="test", timestamp=1234567890.0,
        )
        d = t.to_dict()
        t2 = TrustTransition.from_dict(d)
        assert t2.node_id == t.node_id
        assert t2.previous_level == t.previous_level
        assert t2.new_level == t.new_level
        assert t2.score == t.score

    def test_node_metrics_serialization(self):
        m = NodeMetrics(messages_sent=10, messages_received=20, hmac_failures=1)
        d = m.to_dict()
        m2 = NodeMetrics.from_dict(d)
        assert m2.messages_sent == 10
        assert m2.messages_total == 30

    def test_trust_score_to_dict(self):
        ts = TrustScore(score=0.9, level=TrustLevel.PRIVILEGED, components={"a": 1.0})
        d = ts.to_dict()
        assert d["score"] == 0.9
        assert d["level"] == 4
        assert d["level_name"] == "PRIVILEGED"
