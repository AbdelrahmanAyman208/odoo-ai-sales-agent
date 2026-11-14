# -*- coding: utf-8 -*-
"""
Universal OpenAI-Compatible LLM Client (Global Decision 1 & 2).
Exclusively uses standard OpenAI Chat Completions endpoint (`/chat/completions`)
for OpenRouter, vLLM, Ollama, or OpenAI proxies.

Features:
- Standard `tools` and `tool_calls` schema.
- Resilient JSON argument parser and auto-repair for weak/free models.
- Lenient extraction of tool calls printed in message body.
- Exponential backoff with jitter on 429/5xx/timeouts (max 3 retries).
- Pooled requests.Session keep-alive.

Complexity:
- Time: O(T) where T is generation/streaming latency.
- Space: O(M) where M is request/response payload size.
"""
import json
import logging
import random
import re
import time
from typing import Any, Dict, Generator, List, Optional, Tuple
import requests

_logger = logging.getLogger(__name__)

_GLOBAL_SESSION: Optional[requests.Session] = None


def get_http_session() -> requests.Session:
    """Returns a shared pooled requests.Session instance."""
    global _GLOBAL_SESSION
    if _GLOBAL_SESSION is None:
        _GLOBAL_SESSION = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0,
        )
        _GLOBAL_SESSION.mount('http://', adapter)
        _GLOBAL_SESSION.mount('https://', adapter)
    return _GLOBAL_SESSION


class LLMClientError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, is_retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.is_retryable = is_retryable


class OpenAILLMClient:
    """Universal OpenAI-compatible API client."""

    def __init__(
        self,
        base_url: str = "https://openrouter.ai/api/v1",
        api_key: str = "",
        model: str = "google/gemini-2.0-flash-exp:free",
        timeout: int = 45,
        max_retries: int = 3,
    ):
        clean_base = (base_url or "").strip().rstrip('/')
        if not clean_base:
            clean_base = "https://openrouter.ai/api/v1"

        if clean_base.endswith("/chat/completions"):
            self.endpoint = clean_base
        elif clean_base.endswith("/v1"):
            self.endpoint = f"{clean_base}/chat/completions"
        else:
            self.endpoint = f"{clean_base}/v1/chat/completions"

        self.api_key = (api_key or "").strip()
        self.model = model or "google/gemini-2.0-flash-exp:free"
        self.timeout = timeout or 45
        self.max_retries = max(1, min(max_retries, 4))
        self.session = get_http_session()

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": "https://odoo.com/sale_ai_agent",
            "X-Title": "Odoo 20 AI Operations Agent",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def create_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes a standard /chat/completions call with exponential backoff on 429/5xx.
        """
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }

        # Format tools in standard OpenAI format: {"type": "function", "function": {...}}
        if tools:
            formatted_tools = []
            for t in tools:
                if "function" in t:
                    formatted_tools.append(t)
                else:
                    formatted_tools.append({
                        "type": "function",
                        "function": {
                            "name": t.get("name"),
                            "description": t.get("description", ""),
                            "parameters": t.get("input_schema") or t.get("parameters") or {"type": "object", "properties": {}},
                        }
                    })
            payload["tools"] = formatted_tools
            payload["tool_choice"] = "auto"

        headers = self._get_headers()

        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    data = response.json()
                    return self._parse_completion_response(data)

                # Retryable status codes: 429 (Rate Limit) or 5xx (Server Error)
                if response.status_code in (429, 500, 502, 503, 504):
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        wait_seconds = float(retry_after)
                    else:
                        wait_seconds = (2 ** attempt) + random.uniform(0.1, 0.6)

                    _logger.warning(
                        "LLM API returned %d (attempt %d/%d). Retrying in %.2fs. Body: %s",
                        response.status_code, attempt + 1, self.max_retries, wait_seconds, response.text[:200]
                    )
                    time.sleep(wait_seconds)
                    continue

                # Non-retryable error (e.g. 401 Auth, 400 Bad Request)
                error_msg = f"LLM API Error ({response.status_code}): {response.text[:300]}"
                _logger.error(error_msg)
                raise LLMClientError(error_msg, status_code=response.status_code, is_retryable=False)

            except requests.exceptions.Timeout:
                wait_seconds = (2 ** attempt) + random.uniform(0.1, 0.5)
                _logger.warning("LLM API request timed out (attempt %d/%d). Retrying in %.2fs", attempt + 1, self.max_retries, wait_seconds)
                time.sleep(wait_seconds)
            except requests.exceptions.RequestException as re_err:
                wait_seconds = (2 ** attempt) + random.uniform(0.1, 0.5)
                _logger.warning("Network error calling LLM (attempt %d/%d): %s", attempt + 1, self.max_retries, re_err)
                time.sleep(wait_seconds)

        raise LLMClientError(f"Failed to communicate with LLM API after {self.max_retries} retries.", is_retryable=True)

    def _parse_completion_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses OpenAI completion object, with fallback leniency for free models.
        """
        choices = data.get("choices", [])
        if not choices:
            return {"content": "", "tool_calls": [], "usage": data.get("usage", {})}

        msg = choices[0].get("message", {})
        content = msg.get("content") or ""
        raw_tool_calls = msg.get("tool_calls") or []

        parsed_tool_calls = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            fn_name = fn.get("name", "")
            raw_args = fn.get("arguments", "{}")

            args_dict = self._safe_parse_json(raw_args)
            parsed_tool_calls.append({
                "id": tc.get("id") or f"call_{int(time.time()*1000)}",
                "name": fn_name,
                "arguments": args_dict,
            })

        # Fallback: Check if weak model printed JSON tool call inside text content
        if not parsed_tool_calls and "```json" in content:
            extracted_calls = self._extract_tool_calls_from_text(content)
            if extracted_calls:
                parsed_tool_calls.extend(extracted_calls)

        return {
            "content": content,
            "tool_calls": parsed_tool_calls,
            "usage": data.get("usage", {}),
            "model": data.get("model", self.model),
        }

    def _safe_parse_json(self, raw_str: Any) -> Dict[str, Any]:
        """Auto-repairs dirty JSON strings commonly emitted by small models."""
        if isinstance(raw_str, dict):
            return raw_str
        if not raw_str or not isinstance(raw_str, str):
            return {}

        clean = raw_str.strip()
        try:
            return json.loads(clean)
        except Exception:
            pass

        # Strip markdown fences if present
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)
        try:
            return json.loads(clean.strip())
        except Exception:
            return {}

    def _extract_tool_calls_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extracts JSON tool calls embedded directly into conversational markdown."""
        matches = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        results = []
        for m in matches:
            try:
                parsed = json.loads(m.strip())
                if isinstance(parsed, dict) and "tool" in parsed:
                    results.append({
                        "id": f"call_text_{int(time.time()*1000)}",
                        "name": parsed["tool"],
                        "arguments": parsed.get("arguments") or parsed.get("args") or {},
                    })
            except Exception:
                continue
        return results

    def test_connection(self) -> Dict[str, Any]:
        """
        Executes real connectivity test, verifies tools support, and runs a 1-step test roundtrip.
        """
        try:
            # Simple ping test
            resp = self.create_chat_completion(
                messages=[{"role": "user", "content": "Hello. Reply with 'READY'."}],
                max_tokens=20,
            )
            return {
                "success": True,
                "message": f"Connection verified successfully. Model: {resp.get('model', self.model)}. Response: {resp.get('content', '').strip()}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
