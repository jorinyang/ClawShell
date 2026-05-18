"""LLM Client — OpenAI-compatible LLM API client (stdlib only).

Design: Zero external dependencies, urllib-based, OpenAI-compatible API.
Supports: DeepSeek, OpenAI, and any OpenAI-compatible endpoint.

Configuration via environment variables:
  DEEPSEEK_API_KEY / OPENAI_API_KEY / LLM_API_KEY
  LLM_BASE_URL (default: https://api.deepseek.com/v1)
  LLM_MODEL    (default: deepseek-v4-pro)
"""
from __future__ import annotations
import os
import json
import time
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List


class LLMClient:
    """Minimal OpenAI-compatible LLM client — stdlib only.

    Usage:
        llm = LLMClient()
        reply = llm.chat("You are an analyst.", "Analyze this: ...")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 120,
    ):
        """Initialize LLM client.

        Args:
            api_key: API key (auto-detected from env)
            base_url: API base URL (default: DeepSeek)
            model: Model name (default: deepseek-chat)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY", "")
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL") or "https://api.deepseek.com/v1").rstrip("/")
        self.model = model or os.environ.get("LLM_MODEL", "deepseek-v4-pro")
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        """Check if client has valid credentials."""
        return bool(self.api_key)

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send a chat completion request.

        Args:
            system_prompt: System message (role/context)
            user_message: User message (the actual query)
            temperature: Creativity level (0.0-2.0)
            max_tokens: Max response tokens
            response_format: Optional {"type": "json_object"} for JSON mode

        Returns:
            {"success": True, "content": "...", "usage": {...}}
            or {"success": False, "error": "..."}
        """
        if not self.is_configured:
            return {"success": False, "error": "LLM client not configured (no API key)"}

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        body: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            body["response_format"] = response_format

        try:
            data = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=data,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp = urllib.request.urlopen(req, timeout=self.timeout)
            result = json.loads(resp.read().decode("utf-8"))

            choice = result.get("choices", [{}])[0]
            return {
                "success": True,
                "content": choice.get("message", {}).get("content", ""),
                "usage": result.get("usage", {}),
                "model": result.get("model", self.model),
            }
        except urllib.error.HTTPError as e:
            return {"success": False, "error": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def chat_simple(self, system_prompt: str, user_message: str) -> str:
        """Convenience: chat and return content string directly."""
        result = self.chat(system_prompt, user_message)
        return result.get("content", "") if result.get("success") else f"[LLM Error: {result.get('error')}]"
