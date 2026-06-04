"""LLM Concurrent — parallel LLM calls with cache integration (v2.3.1).

Wraps LLMClient with ThreadPoolExecutor for parallel analysis.
Integrates LLMCache for repeated-query deduplication.
"""
from __future__ import annotations
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Callable

from cloud.brain.llm_client import LLMClient
from cloud.brain.llm_cache import LLMCache


class LLMConcurrent:
    """Concurrent LLM client with caching.

    Usage:
        client = LLMConcurrent()
        results = client.chat_batch([
            ("You are X.", "Query 1", {}),
            ("You are Y.", "Query 2", {}),
        ])
    """

    def __init__(self, max_workers: int = 4, cache: Optional[LLMCache] = None,
                 persist_cache: bool = True):
        self._client = LLMClient()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="llm-call"
        )
        self._cache = cache or LLMCache(
            max_size=200,
            ttl_seconds=3600,
            persist_path="/opt/clawshell/data/llm_cache.json" if persist_cache else None,
        )
        self._stats = {"calls": 0, "cached": 0, "errors": 0}
        self._lock = threading.RLock()

    def chat(self, system_prompt: str, user_message: str,
             temperature: float = 0.7, max_tokens: int = 4096,
             response_format: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Single chat with cache lookup."""
        model = self._client.model
        cached = self._cache.get(system_prompt, user_message, model, temperature)
        if cached is not None:
            with self._lock:
                self._stats["cached"] += 1
            return cached
        result = self._client.chat(
            system_prompt, user_message,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        self._cache.set(system_prompt, user_message, model, temperature, result)
        with self._lock:
            self._stats["calls"] += 1
            if not result.get("success"):
                self._stats["errors"] += 1
        return result

    def chat_batch(self, queries: List[Dict[str, Any]],
                   timeout: float = 60.0) -> List[Dict[str, Any]]:
        """Execute multiple chat requests concurrently.

        Each query: {"system": str, "user": str, "temperature": float (optional), ...}
        """
        futures = {}
        for i, q in enumerate(queries):
            sys_p = q.get("system", "")
            usr_p = q.get("user", "")
            temp = q.get("temperature", 0.7)
            max_tok = q.get("max_tokens", 4096)
            fmt = q.get("response_format")

            # Check cache first
            model = self._client.model
            cached = self._cache.get(sys_p, usr_p, model, temp)
            if cached is not None:
                with self._lock:
                    self._stats["cached"] += 1
                # Use a resolved future
                from concurrent.futures import Future
                f = Future()
                f.set_result(cached)
                futures[f] = i
                continue

            f = self._executor.submit(
                self._client.chat, sys_p, usr_p, temp, max_tok, fmt
            )
            futures[f] = i

        results = [None] * len(queries)
        for future in as_completed(futures, timeout=timeout):
            idx = futures[future]
            try:
                r = future.result()
                results[idx] = r
                # Cache successful results
                if r.get("success"):
                    q = queries[idx]
                    self._cache.set(
                        q.get("system", ""), q.get("user", ""),
                        self._client.model, q.get("temperature", 0.7), r,
                    )
                with self._lock:
                    self._stats["calls"] += 1
                    if not r.get("success"):
                        self._stats["errors"] += 1
            except Exception as e:
                results[idx] = {"success": False, "error": str(e)}
                with self._lock:
                    self._stats["errors"] += 1
        return results

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                **self._stats,
                "cache": self._cache.stats(),
            }

    def shutdown(self):
        self._executor.shutdown(wait=False)
