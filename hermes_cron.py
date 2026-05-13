#!/usr/bin/env python3
"""
ClawShell Hermes Cron Runner — 轻量级定时分析引擎
部署于 ECS，通过 Linux cron 定时触发，调用 CloudHub Brain API 执行分析任务。

三档任务：
  1. 快速洞察 (every 5min) — 拉取最近事件，调用 brain/analyze 做微分析
  2. 深度复盘 (every 6h)  — 全量事件分析 + 趋势报告
  3. 每日优化 (daily 2am)  — 存储优化 + 日报生成

Usage:
  python3 hermes_cron.py insight    # 快速洞察
  python3 hermes_cron.py review     # 深度复盘
  python3 hermes_cron.py optimize   # 每日优化
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Config ──────────────────────────────────────────────────
CLOUDHUB_URL = os.environ.get("CLOUDHUB_URL", "http://127.0.0.1:8000")
LOG_DIR = Path(os.environ.get("HERMES_CRON_LOG_DIR", "/opt/clawshell/logs/cron"))
DATA_DIR = Path(os.environ.get("HERMES_CRON_DATA_DIR", "/opt/clawshell/data/hermes_cron"))

API_TIMEOUT = 120  # LLM analyze may take a while

# ── Logging ─────────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "hermes_cron.log"),
        logging.StreamHandler(sys.stderr),
    ],
)
log = logging.getLogger("hermes_cron")

# ── HTTP Session ────────────────────────────────────────────
def _make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=2, status_forcelist=[502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s

session = _make_session()


# ── API Helpers ──────────────────────────────────────────────
def _check_health() -> dict:
    """Verify CloudHub is alive."""
    try:
        r = session.get(f"{CLOUDHUB_URL}/health", timeout=10)
        return r.json() if r.ok else {"error": r.status_code}
    except Exception as e:
        return {"error": str(e)}


def _brain_analyze(query: str, context: str = "") -> dict:
    """Call brain/analyze endpoint."""
    payload = {"query": query}
    if context:
        payload["context"] = context
    try:
        r = session.post(
            f"{CLOUDHUB_URL}/api/v1/brain/analyze",
            json=payload,
            timeout=API_TIMEOUT,
        )
        return r.json() if r.ok else {"error": r.text, "status": r.status_code}
    except Exception as e:
        return {"error": str(e)}


def _fetch_events(limit: int = 100, since: float = None) -> list:
    """Fetch recent events from CloudHub."""
    params = {"limit": limit}
    if since:
        params["since"] = since
    try:
        r = session.get(
            f"{CLOUDHUB_URL}/api/v1/events/",
            params=params,
            timeout=30,
        )
        if r.ok:
            data = r.json()
            if isinstance(data, dict):
                inner = data.get("data", {})
                return inner.get("events", inner if isinstance(inner, list) else [])
            return data if isinstance(data, list) else []
        return []
    except Exception as e:
        log.error(f"Failed to fetch events: {e}")
        return []


def _brain_status() -> dict:
    """Get brain status."""
    try:
        r = session.get(f"{CLOUDHUB_URL}/api/v1/brain/status", timeout=10)
        return r.json() if r.ok else {"error": r.text}
    except Exception as e:
        return {"error": str(e)}


# ── Task: Quick Insight (every 5 min) ────────────────────────
def run_insight():
    """快速洞察：拉取最近5分钟事件，做轻量分析。"""
    log.info("=== INSIGHT START ===")

    health = _check_health()
    if "error" in health:
        log.warning(f"CloudHub unhealthy, skipping insight: {health}")
        return

    brain = _brain_status()
    if not brain.get("data", {}).get("running"):
        log.warning(f"Brain not running, skipping insight: {brain}")
        return

    # 获取最近5分钟事件
    since = (datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp()
    events = _fetch_events(limit=50, since=since)

    event_count = len(events)
    if event_count == 0:
        log.info("No events in last 5 minutes — idle period")
        return

    # 构建分析上下文
    event_types = {}
    for e in events:
        t = e.get("event_type", e.get("type", "unknown"))
        event_types[t] = event_types.get(t, 0) + 1

    summary = f"Last 5 minutes: {event_count} events. Types: {json.dumps(event_types)}"

    # 调用brain做微分析
    query = f"""You are ClawShell's real-time insight engine. Analyze these recent events:

Time window: last 5 minutes
Total events: {event_count}
Event type breakdown: {json.dumps(event_types)}

Task:
1. Identify any anomalies or patterns
2. Flag critical events that need attention
3. Suggest one actionable insight (1 sentence max)
4. If nothing notable, say "Steady state — no anomalies detected"

Keep the response under 100 words. Be concise."""

    result = _brain_analyze(query, context=summary)
    log.info(f"Insight result: {json.dumps(result, ensure_ascii=False)[:500]}")

    # 保存洞察到文件
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    insight_file = DATA_DIR / "insights" / f"{ts}.json"
    insight_file.parent.mkdir(parents=True, exist_ok=True)
    insight_file.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_count": event_count,
        "event_types": event_types,
        "analysis": result,
    }, ensure_ascii=False, indent=2))

    log.info(f"Insight saved to {insight_file}")
    log.info("=== INSIGHT DONE ===")


# ── Task: Deep Review (every 6 hours) ────────────────────────
def run_review():
    """深度复盘：全量分析最近6小时事件，生成趋势报告。"""
    log.info("=== DEEP REVIEW START ===")

    health = _check_health()
    if "error" in health:
        log.warning(f"CloudHub unhealthy, skipping review: {health}")
        return

    # 获取最近6小时事件
    since = (datetime.now(timezone.utc) - timedelta(hours=6)).timestamp()
    events = _fetch_events(limit=500, since=since)
    event_count = len(events)
    log.info(f"Fetched {event_count} events for review window")

    if event_count == 0:
        log.info("No events in review window")
        return

    # 聚合统计
    event_types = {}
    source_ids = set()
    timestamps = []
    for e in events:
        t = e.get("event_type", e.get("type", "unknown"))
        event_types[t] = event_types.get(t, 0) + 1
        sid = e.get("source", e.get("source_id", ""))
        if sid:
            source_ids.add(sid)
        ts = e.get("timestamp", "")
        if ts:
            timestamps.append(ts)

    context_block = f"""Review window: last 6 hours
Total events: {event_count}
Unique sources (devices): {len(source_ids)}
Event type distribution: {json.dumps(event_types)}"""

    query = f"""You are ClawShell's deep analytics engine. Perform a comprehensive 6-hour review:

DATA:
{context_block}

ANALYSIS TASKS:
1. **Trend analysis**: What patterns emerge from the event distribution?
2. **Anomaly detection**: Any unusual spikes, drops, or outliers?
3. **Device health**: Based on source diversity, are all nodes reporting normally?
4. **Risk assessment**: Any concerning patterns that could escalate?
5. **Recommendations**: Top 3 actionable recommendations for the system operator.
6. **Score**: Rate system health 1-10 with brief justification.

Format the output as a structured report with clear sections."""

    result = _brain_analyze(query, context=context_block)

    # 保存报告
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    report_file = DATA_DIR / "reviews" / f"review_{ts}.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "window_hours": 6,
        "event_count": event_count,
        "unique_sources": len(source_ids),
        "event_types": event_types,
        "analysis": result,
    }, ensure_ascii=False, indent=2))

    log.info(f"Review report saved to {report_file}")
    log.info("=== DEEP REVIEW DONE ===")


# ── Task: Daily Optimize (every day at 2am) ──────────────────
def run_optimize():
    """每日优化：生成日报 + 清理旧数据 + 存储优化建议。"""
    log.info("=== DAILY OPTIMIZE START ===")

    health = _check_health()
    if "error" in health:
        log.warning(f"CloudHub unhealthy, skipping optimize: {health}")
        return

    # 获取过去24小时事件
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).timestamp()
    events = _fetch_events(limit=1000, since=since)
    event_count = len(events)
    log.info(f"Fetched {event_count} events for daily window")

    # 聚合
    event_types = {}
    hourly_counts = {}
    source_ids = set()
    for e in events:
        t = e.get("event_type", e.get("type", "unknown"))
        event_types[t] = event_types.get(t, 0) + 1
        sid = e.get("source", e.get("source_id", ""))
        if sid:
            source_ids.add(sid)
        ts = e.get("timestamp", None)
        if ts:
            try:
                hour = datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%dT%H")
                hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
            except Exception:
                pass

    context_block = f"""Daily window: last 24 hours
Total events: {event_count}
Unique sources: {len(source_ids)}
Event type distribution: {json.dumps(event_types)}
Hourly event counts: {json.dumps(hourly_counts)}"""

    query = f"""You are ClawShell's daily system optimizer. Generate a comprehensive daily report:

DATA:
{context_block}

OUTPUT SECTIONS:
1. **Executive Summary**: One paragraph overview of the day
2. **Key Metrics**: Events/hour avg, peak hour, active devices
3. **Top Events**: Most frequent event types and their significance
4. **System Health**: Score 1-10 with reasoning
5. **Optimization Recommendations**: 
   - Storage: any events that can be archived/aggregated?
   - Performance: any bottlenecks visible in event rates?
   - Reliability: any devices with irregular reporting?
6. **Tomorrow's Focus**: What to watch for next 24h

Format as a clean markdown report."""

    result = _brain_analyze(query, context=context_block)

    # 保存日报
    date_str = datetime.now().strftime("%Y%m%d")
    daily_file = DATA_DIR / "daily" / f"report_{date_str}.json"
    daily_file.parent.mkdir(parents=True, exist_ok=True)
    daily_file.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "date": date_str,
        "event_count": event_count,
        "unique_sources": len(source_ids),
        "event_types": event_types,
        "hourly_counts": hourly_counts,
        "analysis": result,
    }, ensure_ascii=False, indent=2))

    log.info(f"Daily report saved to {daily_file}")

    # 清理旧洞察数据 (保留最近7天)
    insights_dir = DATA_DIR / "insights"
    if insights_dir.exists():
        cutoff = datetime.now() - timedelta(days=7)
        cleaned = 0
        for f in insights_dir.glob("*.json"):
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
                cleaned += 1
        log.info(f"Cleaned {cleaned} old insight files")

    log.info("=== DAILY OPTIMIZE DONE ===")


# ── CLI Entry ────────────────────────────────────────────────
COMMANDS = {
    "insight": run_insight,
    "review": run_review,
    "optimize": run_optimize,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} {{{ '|'.join(COMMANDS) }}}")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}. Choose from: {', '.join(COMMANDS)}")
        sys.exit(1)

    start = time.time()
    try:
        COMMANDS[cmd]()
    except Exception as e:
        log.exception(f"Fatal error in {cmd}: {e}")
    elapsed = time.time() - start
    log.info(f"[{cmd}] completed in {elapsed:.1f}s")
