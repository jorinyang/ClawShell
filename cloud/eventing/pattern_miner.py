"""Pattern Miner — detect recurring patterns in event streams.

Analyzes event sequences to identify common patterns, anomalies,
and actionable insights. Feeds into EvolutionEngine for skill generation.

Design: stdlib-only, statistical approach (no ML dependencies).
"""

from __future__ import annotations

import json
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Pattern:
    """A detected pattern in the event stream."""
    pattern_id: str = ""
    name: str = ""
    description: str = ""
    topic_sequence: List[str] = field(default_factory=list)
    frequency: int = 0
    confidence: float = 0.0        # 0.0 - 1.0
    avg_duration_ms: float = 0.0
    first_seen: float = 0.0
    last_seen: float = 0.0
    is_anomaly: bool = False
    suggested_action: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "description": self.description,
            "topic_sequence": self.topic_sequence,
            "frequency": self.frequency,
            "confidence": self.confidence,
            "avg_duration_ms": self.avg_duration_ms,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "is_anomaly": self.is_anomaly,
            "suggested_action": self.suggested_action,
            "metadata": self.metadata,
        }


@dataclass
class MiningResult:
    """Result of a pattern mining operation."""
    patterns: List[Pattern] = field(default_factory=list)
    total_events_analyzed: int = 0
    unique_topics: int = 0
    mining_duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patterns": [p.to_dict() for p in self.patterns],
            "total_events_analyzed": self.total_events_analyzed,
            "unique_topics": self.unique_topics,
            "mining_duration_ms": self.mining_duration_ms,
            "timestamp": self.timestamp,
        }


class PatternMiner:
    """Statistical pattern miner for event streams.

    Detects:
    1. Sequential patterns (topic A → topic B → topic C)
    2. Frequency anomalies (sudden spikes or drops)
    3. Co-occurrence patterns (topics that appear together)

    Thread-safe via RLock.
    """

    def __init__(self, min_support: int = 3, min_confidence: float = 0.3,
                 max_sequence_length: int = 5):
        self._min_support = min_support
        self._min_confidence = min_confidence
        self._max_seq_length = max_sequence_length
        self._lock = threading.RLock()
        self._event_history: List[Tuple[str, float]] = []  # (topic, timestamp)
        self._max_history = 10000
        self._patterns: List[Pattern] = []
        self._pattern_counter = 0

    def ingest(self, topic: str, timestamp: Optional[float] = None) -> None:
        """Feed an event topic for pattern analysis."""
        with self._lock:
            ts = timestamp or time.time()
            self._event_history.append((topic, ts))
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history:]

    def mine(self) -> MiningResult:
        """Run pattern mining on current event history."""
        start = time.time()
        with self._lock:
            patterns: List[Pattern] = []

            if len(self._event_history) < self._min_support * 2:
                return MiningResult(
                    total_events_analyzed=len(self._event_history),
                    unique_topics=len(set(t for t, _ in self._event_history)),
                    mining_duration_ms=(time.time() - start) * 1000,
                )

            topics_only = [t for t, _ in self._event_history]
            unique_topics = len(set(topics_only))

            # 1. Frequency-based patterns (most common topics)
            topic_freq = Counter(topics_only)
            total = len(topics_only)
            for topic, count in topic_freq.most_common(10):
                confidence = count / total
                if confidence >= self._min_confidence:
                    self._pattern_counter += 1
                    patterns.append(Pattern(
                        pattern_id=f"freq_{self._pattern_counter}",
                        name=f"High-frequency: {topic}",
                        description=f"Topic '{topic}' appears {count} times ({confidence:.1%} of events)",
                        topic_sequence=[topic],
                        frequency=count,
                        confidence=confidence,
                        suggested_action=f"Consider optimizing handlers for '{topic}' events",
                    ))

            # 2. Sequential patterns (topic transitions)
            transitions = defaultdict(Counter)  # topic → {next_topic: count}
            for i in range(len(topics_only) - 1):
                transitions[topics_only[i]][topics_only[i + 1]] += 1

            for from_topic, next_counts in transitions.items():
                from_total = topic_freq[from_topic]
                for to_topic, count in next_counts.most_common(3):
                    conf = count / from_total
                    if conf >= self._min_confidence and count >= self._min_support:
                        self._pattern_counter += 1
                        patterns.append(Pattern(
                            pattern_id=f"seq_{self._pattern_counter}",
                            name=f"Transition: {from_topic} → {to_topic}",
                            description=f"After '{from_topic}', '{to_topic}' follows {conf:.1%} of the time ({count} occurrences)",
                            topic_sequence=[from_topic, to_topic],
                            frequency=count,
                            confidence=conf,
                            suggested_action=f"Consider linking handlers for {from_topic} → {to_topic}",
                        ))

            # 3. Co-occurrence patterns (windowed pairs)
            window_ms = 5000  # 5-second window
            co_occur = Counter()
            for i in range(len(self._event_history)):
                ti, tsi = self._event_history[i]
                for j in range(i + 1, min(i + 10, len(self._event_history))):
                    tj, tsj = self._event_history[j]
                    if tsj - tsi > window_ms / 1000:
                        break
                    if ti != tj:
                        pair = tuple(sorted([ti, tj]))
                        co_occur[pair] += 1

            for (t1, t2), count in co_occur.most_common(5):
                if count >= self._min_support:
                    self._pattern_counter += 1
                    patterns.append(Pattern(
                        pattern_id=f"cooc_{self._pattern_counter}",
                        name=f"Co-occurrence: {t1} + {t2}",
                        description=f"'{t1}' and '{t2}' appear together within 5s ({count} times)",
                        topic_sequence=[t1, t2],
                        frequency=count,
                        confidence=count / max(topic_freq[t1], topic_freq[t2], 1),
                        suggested_action=f"These topics may be causally related",
                    ))

            # Store discovered patterns
            self._patterns = patterns

            return MiningResult(
                patterns=patterns,
                total_events_analyzed=len(self._event_history),
                unique_topics=unique_topics,
                mining_duration_ms=(time.time() - start) * 1000,
            )

    def get_patterns(self, limit: int = 50) -> List[Pattern]:
        """Get previously mined patterns."""
        with self._lock:
            return sorted(self._patterns, key=lambda p: p.confidence, reverse=True)[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get miner statistics."""
        with self._lock:
            return {
                "total_events": len(self._event_history),
                "discovered_patterns": len(self._patterns),
                "min_support": self._min_support,
                "min_confidence": self._min_confidence,
            }
