"""Cloud Analyst — LLM-powered analysis and reasoning engine.

Design: Event-driven + timer-driven LLM analysis.
Integrates with CloudEventBus for real-time analysis and
provides scheduled deep analysis capabilities.

Capabilities:
- Error root cause analysis (event-driven, instant)
- Periodic insight generation (timer-driven, configurable interval)
- Deep review and architecture planning (on-demand)
- Best practice extraction and optimization
"""
from __future__ import annotations
import json
import time
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from cloud.brain.llm_client import LLMClient


SYSTEM_ANALYST = (
    "You are the ClawShell Cloud Brain, an AI analyst for the ClawShell distributed system. "
    "ClawShell follows Engineering Cybernetics: information feedback, dynamic regulation, system holism. "
    "Analyze events from edge nodes, find root causes and patterns, generate actionable insights. "
    "Be concise, specific, and actionable. Include concrete suggestions."
)

SYSTEM_PLANNER = (
    "You are the ClawShell Cloud Architect. Analyze system state holistically. "
    "Provide architecture improvements, resource optimization, cross-edge coordination. "
    "Think in Engineering Cybernetics terms. Be specific about what and why."
)


class CloudAnalyst:
    """LLM-powered cloud analysis engine."""

    ANALYSIS_INTERVAL = 300
    DEEP_REVIEW_INTERVAL = 21600
    MAX_EVENTS_PER_ANALYSIS = 200

    def __init__(self, eventbus=None, llm_client=None, data_dir="data"):
        self._eventbus = eventbus
        self._llm = llm_client or LLMClient()
        self._data_dir = data_dir
        self._analyses = []
        self._last_periodic = 0.0
        self._last_deep_review = 0.0
        self._running = False
        self._lock = threading.RLock()
        self._thread = None
        if eventbus and hasattr(eventbus, 'subscribe'):
            eventbus.subscribe("error.*", self._on_critical_event)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._analysis_loop, daemon=True, name="cloud-analyst")
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _analysis_loop(self):
        while self._running:
            for _ in range(int(self.ANALYSIS_INTERVAL / 5)):
                if not self._running:
                    return
                time.sleep(5)
            if not self._running:
                return
            try:
                self.analyze_periodic()
            except Exception:
                pass

    def _on_critical_event(self, event):
        priority = event.get("priority", 50)
        if priority < 80:
            return
        t = threading.Thread(target=self._analyze_critical, args=(event,), daemon=True)
        t.start()

    def _analyze_critical(self, event):
        result = self.analyze_error(event)
        if result.get("success"):
            with self._lock:
                self._analyses.append({"type": "critical", "event_id": event.get("event_id", ""), "content": result["content"], "timestamp": time.time()})

    def analyze_error(self, event):
        ctx = json.dumps(event, indent=2, default=str)
        return self._llm.chat(SYSTEM_ANALYST, "Analyze this critical error and suggest a fix:\n\n" + ctx, temperature=0.3)

    def analyze_errors_batch(self, events):
        if not events:
            return {"success": False, "error": "No events to analyze"}
        summary = [{"type": e.get("event_type", ""), "source": e.get("source", ""), "payload": e.get("payload", {}), "time": e.get("timestamp", 0)} for e in events[-self.MAX_EVENTS_PER_ANALYSIS:]]
        ctx = json.dumps(summary, indent=2, default=str)
        return self._llm.chat(SYSTEM_ANALYST, f"Analyze these {len(summary)} events from ClawShell edge nodes. Find patterns, root causes, and suggest improvements:\n\n{ctx}", temperature=0.5)

    def analyze_periodic(self):
        now = time.time()
        events = []
        if self._eventbus:
            try:
                events = self._eventbus.query(since=now - self.ANALYSIS_INTERVAL, limit=self.MAX_EVENTS_PER_ANALYSIS)
            except Exception:
                pass
        self._last_periodic = now
        if not events:
            return {"success": True, "content": "No new events.", "events": 0}
        return self.analyze_errors_batch(events)

    def deep_review(self):
        now = time.time()
        self._last_deep_review = now
        events = []
        if self._eventbus:
            try:
                events = self._eventbus.query(since=now - self.DEEP_REVIEW_INTERVAL, limit=self.MAX_EVENTS_PER_ANALYSIS)
            except Exception:
                pass
        stats = ""
        if self._eventbus and hasattr(self._eventbus, 'get_stats'):
            try:
                stats = json.dumps(self._eventbus.get_stats(), indent=2)
            except Exception:
                pass
        return self._llm.chat(SYSTEM_PLANNER, f"Deep Review - Last 6 Hours\nSystem Stats:\n{stats}\nRecent Events ({len(events)}):\nAnalyze holistically. Provide architecture recommendations.", temperature=0.5, max_tokens=8192)

    def generate_insight(self, query=""):
        events = []
        if self._eventbus:
            try:
                events = self._eventbus.query(limit=100)
            except Exception:
                pass
        ctx = json.dumps([{"type": e.get("event_type", ""), "source": e.get("source", ""), "payload": e.get("payload", {})} for e in events[-50:]], indent=2, default=str)
        return self._llm.chat(SYSTEM_ANALYST, f"Query: {query}\n\nRecent system events:\n{ctx}", temperature=0.5)

    def plan_architecture(self, description=""):
        events = []
        if self._eventbus:
            try:
                events = self._eventbus.query(limit=100)
            except Exception:
                pass
        stats = ""
        if self._eventbus and hasattr(self._eventbus, 'get_stats'):
            try:
                stats = json.dumps(self._eventbus.get_stats(), indent=2)
            except Exception:
                pass
        return self._llm.chat(SYSTEM_PLANNER, f"Architecture Planning\n{description}\n\nCurrent State:\n{stats}\nDecompose, analyze trade-offs, propose plan with short/mid/long-term recommendations.", temperature=0.3, max_tokens=8192)

    def get_recent_analyses(self, limit=20):
        with self._lock:
            return self._analyses[-limit:]

    @property
    def stats(self):
        with self._lock:
            return {"total_analyses": len(self._analyses), "llm_configured": self._llm.is_configured, "last_periodic": self._last_periodic, "last_deep_review": self._last_deep_review, "running": self._running}
