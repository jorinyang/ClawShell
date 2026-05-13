#!/usr/bin/env python3
"""
ClawShell FC Handler — 阿里云函数计算事件处理器
部署于阿里云香港函数计算，处理来自 CloudHub 的事件流。

函数列表:
  1. event_processor.py  — 事件批处理（去重、聚合、存储）
  2. insight_generator.py — 定时洞察生成（调用 Brain API）
  3. health_monitor.py    — 系统健康监控（告警触发）

Runtime: Python 3.11
Memory: 512MB
Timeout: 120s

部署命令:
  fun deploy -t template.yml
"""

import os
import json
import hashlib
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any
import requests

# ── Configuration ──────────────────────────────────────────────
CLOUDHUB_URL = os.environ.get("CLOUDHUB_URL", "http://47.239.71.174")
BRAIN_URL = f"{CLOUDHUB_URL}/api/v1/brain/analyze"
EVENTS_URL = f"{CLOUDHUB_URL}/api/v1/events/batch"
QUERY_URL = f"{CLOUDHUB_URL}/api/v1/events/"
HEALTH_URL = f"{CLOUDHUB_URL}/health"

OSS_BUCKET = os.environ.get("OSS_BUCKET", "clawshell-vault")
OSS_ENDPOINT = os.environ.get("OSS_ENDPOINT", "oss-cn-hongkong.aliyuncs.com")

# ── Event Processor ────────────────────────────────────────────

def event_processor_handler(event, context) -> dict:
    """
    事件批处理器 — 接收事件批次，去重后转发到 CloudHub。
    
    触发: HTTP / 定时 / OSS 事件
    输入: {"events": [...]} 或 OSS object created 事件
    """
    events = []
    
    # Parse event source
    if isinstance(event, dict):
        # HTTP trigger: event body is the payload
        body = event.get("body", event)
        if isinstance(body, str):
            body = json.loads(body)
        events = body.get("events", [])
        
        # OSS trigger: parse from oss events
        if not events and event.get("events"):
            for oss_evt in event.get("events", []):
                oss_obj = oss_evt.get("oss", {}).get("object", {})
                key = oss_obj.get("key", "")
                if key:
                    events.append({
                        "event_type": "oss.object_created",
                        "source": "fc.event_processor",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "payload": {"key": key, "bucket": oss_obj.get("bucket", "")}
                    })
    
    if not events:
        return {"status": "no_events", "count": 0}
    
    # Dedup
    seen = set()
    deduped = []
    for e in events:
        content = json.dumps({
            "type": e.get("event_type", ""),
            "source": e.get("source", ""),
            "payload": e.get("payload", {})
        }, sort_keys=True, default=str)
        h = hashlib.sha256(content.encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            deduped.append(e)
    
    # Forward to CloudHub
    try:
        r = requests.post(
            EVENTS_URL,
            json={"events": deduped},
            timeout=30,
        )
        accepted = r.json().get("data", {}).get("accepted", 0)
    except Exception as e:
        return {"status": "error", "error": str(e), "processed": 0}
    
    return {
        "status": "ok",
        "received": len(events),
        "deduped": len(deduped),
        "accepted": accepted,
        "duplicates": len(events) - len(deduped),
    }


# ── Insight Generator ──────────────────────────────────────────

def insight_generator_handler(event, context) -> dict:
    """
    定时洞察生成器 — 每5分钟调用 Brain API 分析最近事件。
    
    触发: 定时触发器 (rate(5 minutes))
    """
    since = (datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp()
    
    try:
        r = requests.get(QUERY_URL, params={"limit": 50, "since": since}, timeout=15)
        events = r.json().get("data", {}).get("events", [])
    except Exception:
        events = []
    
    if not events:
        return {"status": "idle", "events": 0, "insight": None}
    
    # Aggregate
    type_counts = {}
    sources = set()
    for e in events:
        t = e.get("event_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
        s = e.get("source", "")
        if s:
            sources.add(s)
    
    # Call Brain for analysis
    try:
        r = requests.post(BRAIN_URL, json={
            "query": f"Quick insight: {len(events)} events from {len(sources)} sources. "
                     f"Types: {json.dumps(type_counts)}. "
                     f"Any anomalies? One sentence max.",
            "context": f"5-min window: {len(events)} events, {len(sources)} sources"
        }, timeout=60)
        insight = r.json().get("data", {}).get("content", "Analysis unavailable")
    except Exception:
        insight = "Analysis unavailable (Brain API error)"
    
    return {
        "status": "ok",
        "events": len(events),
        "sources": len(sources),
        "types": type_counts,
        "insight": insight[:500],
    }


# ── Health Monitor ─────────────────────────────────────────────

def health_monitor_handler(event, context) -> dict:
    """
    系统健康监控 — 定期检查 CloudHub 健康状态，异常时触发告警。
    
    触发: 定时触发器 (rate(1 minute))
    告警: SLS / 钉钉 Webhook
    """
    DINGTALK_WEBHOOK = os.environ.get("DINGTALK_WEBHOOK", "")
    
    # Check CloudHub health
    try:
        r = requests.get(HEALTH_URL, timeout=5)
        healthy = r.ok
        health_data = r.json() if r.ok else {}
    except Exception:
        healthy = False
        health_data = {"error": "connection failed"}
    
    if not healthy:
        # Alert
        alert_msg = json.dumps({
            "msgtype": "text",
            "text": {
                "content": f"⚠️ ClawShell CloudHub HEALTH CHECK FAILED\n"
                           f"Time: {datetime.now(timezone.utc).isoformat()}\n"
                           f"Error: {health_data.get('error', 'unknown')}"
            }
        })
        
        if DINGTALK_WEBHOOK:
            try:
                requests.post(DINGTALK_WEBHOOK, json=json.loads(alert_msg), timeout=5)
            except Exception:
                pass
    
    return {
        "status": "healthy" if healthy else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": health_data,
    }


# ── Main Entry (FC invocation) ─────────────────────────────────

TYPES = {
    "event_processor": event_processor_handler,
    "insight_generator": insight_generator_handler,
    "health_monitor": health_monitor_handler,
}

def handler(event, context):
    """FC 统一入口 — 根据上下文分发到对应的处理器."""
    fc_type = os.environ.get("FC_FUNCTION_TYPE", "event_processor")
    handler_fn = TYPES.get(fc_type, event_processor_handler)
    
    start = time.time()
    try:
        result = handler_fn(event, context)
    except Exception as e:
        result = {"status": "error", "error": str(e)}
    
    result["function_type"] = fc_type
    result["duration_ms"] = round((time.time() - start) * 1000, 2)
    
    return result
