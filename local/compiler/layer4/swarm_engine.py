"""SwarmEngine — unified L4 swarm (SwarmManager+TrustEvaluator+NicheMatcher) v2.3."""
from __future__ import annotations
import json, time, threading, os
from typing import Dict, List

class SwarmEngine:
    """Unified L4 swarm: node discovery + trust scoring + niche matching."""

    TRUST_LEVELS = ["untrusted", "low", "neutral", "high", "trusted"]

    def __init__(self, data_dir: str = "~/.clawshell-edge"):
        self._data_dir = os.path.expanduser(data_dir)
        os.makedirs(self._data_dir, exist_ok=True)
        self._nodes: Dict[str, dict] = {}
        self._scores: Dict[str, dict] = {}
        self._lock = threading.RLock()
        self._load()

    # ── Node Management ──
    def register_node(self, node_id: str, capabilities: List[str] = None) -> dict:
        with self._lock:
            self._nodes[node_id] = {"node_id": node_id, "capabilities": capabilities or [],
                                     "status": "online", "joined": time.time(), "tasks_completed": 0}
            self._save()
        return self._nodes[node_id]

    def heartbeat(self, node_id: str, metrics: dict = None) -> bool:
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id]["last_heartbeat"] = time.time()
                if metrics: self._nodes[node_id]["metrics"] = metrics
                return True
        return False

    def get_online(self) -> List[dict]:
        cutoff = time.time() - 60
        return [n for n in self._nodes.values() if n.get("last_heartbeat", 0) > cutoff]

    # ── Trust Scoring ──
    def evaluate_trust(self, node_id: str, metrics: dict = None) -> dict:
        weights = {"uptime": 0.25, "success_rate": 0.35, "response_time": 0.20, "error_rate": 0.20}
        score = 0.5
        if metrics:
            sr = metrics.get("success_rate", 0.5)
            rt = metrics.get("response_time", 5) / 10
            score = score + sr * weights["success_rate"] + max(0, 1 - rt) * weights["response_time"]
        score = round(min(1.0, max(0.0, score)), 3)
        level = self._score_to_level(score)
        with self._lock:
            self._scores[node_id] = {"score": score, "level": level, "updated": time.time()}
            self._save()
        return {"node_id": node_id, "score": score, "level": level}

    def demote_trust(self, node_id: str, reason: str = "") -> dict:
        with self._lock:
            current = self._scores.get(node_id, {"score": 0.5})
            current["score"] = max(0.0, current["score"] - 0.3)
            current["level"] = self._score_to_level(current["score"])
            current["demoted_at"] = time.time()
            current["reason"] = reason
            self._scores[node_id] = current
            self._save()
        return current

    # ── Niche Matching ──
    def match_capabilities(self, required: List[str]) -> List[dict]:
        online = self.get_online()
        matches = []
        for node in online:
            caps = set(node.get("capabilities", []))
            overlap = len(caps.intersection(set(required)))
            if overlap > 0:
                trust = self._scores.get(node["node_id"], {}).get("score", 0.5)
                matches.append({"node_id": node["node_id"], "match_score": min(overlap / len(required), 1.0),
                                "trust_score": trust, "combined": round((overlap / len(required) + trust) / 2, 3)})
        return sorted(matches, key=lambda x: x["combined"], reverse=True)

    def stats(self) -> dict:
        with self._lock:
            trust_stats = {}
            for s in self._scores.values(): 
                l = s.get("level"); trust_stats[l] = trust_stats.get(l, 0) + 1
            return {"total_nodes": len(self._nodes), "online": len(self.get_online()),
                    "trust_distribution": trust_stats}

    def _score_to_level(self, score: float) -> str:
        if score >= 0.9: return "trusted"
        if score >= 0.7: return "high"
        if score >= 0.5: return "neutral"
        if score >= 0.3: return "low"
        return "untrusted"

    def _load(self):
        try:
            with open(os.path.join(self._data_dir, "swarm.json")) as f:
                d = json.load(f); self._nodes = d.get("nodes", {}); self._scores = d.get("scores", {})
        except: pass
    def _save(self):
        try:
            with open(os.path.join(self._data_dir, "swarm.json"), "w") as f:
                json.dump({"nodes": self._nodes, "scores": self._scores}, f, indent=2)
        except: pass
