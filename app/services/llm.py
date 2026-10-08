"""Optional LLM calls through the local CPA gateway (OpenAI-compatible chat completions).

Only candidate patterns, variants and statistics are sent; see
docs/design/2026-10-08-02-optional-embedding.md for the data boundary.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.fsutil import atomic_text_writer

DEFAULT_LLM_MODEL = "grok-4.5"
LLM_CACHE_DIRNAME = "llm-cache"

# Reasoning models count reasoning tokens against this limit.
_MAX_TOKENS = 16000
_MAX_ATTEMPTS = 3
_TIMEOUT_SECONDS = 600
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})

# (system prompt, user prompt) -> raw assistant text
type ChatFn = Callable[[str, str], str]


class LlmError(RuntimeError):
    """LLM configuration, request or response failure."""


@dataclass(frozen=True, slots=True)
class LlmConfig:
    base_url: str
    api_key: str
    model: str = DEFAULT_LLM_MODEL

    @classmethod
    def from_env(cls, model: str = DEFAULT_LLM_MODEL) -> LlmConfig:
        base_url = os.environ.get("CLIPROXYAPI_BASE_URL", "").rstrip("/")
        api_key = os.environ.get("CLIPROXYAPI_API_KEY", "")
        if not base_url or not api_key:
            raise LlmError("CLIPROXYAPI_BASE_URL and CLIPROXYAPI_API_KEY must be set for synthesize")
        return cls(base_url=base_url, api_key=api_key, model=model)


def cpa_chat(config: LlmConfig) -> ChatFn:
    """Build a chat function that requests a JSON object reply from CPA, with retries."""

    def chat(system: str, user: str) -> str:
        body = json.dumps(
            {
                "model": config.model,
                "max_tokens": _MAX_TOKENS,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"},
            }
        ).encode()
        request = urllib.request.Request(
            f"{config.base_url}/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
        )
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
                    payload = json.load(response)
                return str(payload["choices"][0]["message"]["content"])
            except urllib.error.HTTPError as error:
                if error.code not in _RETRY_STATUS or attempt == _MAX_ATTEMPTS:
                    detail = error.read()[:300].decode(errors="replace")
                    raise LlmError(f"chat request failed: HTTP {error.code} {detail}") from error
            except (urllib.error.URLError, TimeoutError) as error:
                if attempt == _MAX_ATTEMPTS:
                    raise LlmError(f"chat request failed: {error}") from error
            time.sleep(2**attempt)
        raise LlmError("chat request failed: retries exhausted")

    return chat


def cached_chat(chat: ChatFn, cache_dir: Path, model: str) -> ChatFn:
    """Wrap a chat function with an on-disk cache keyed by model and prompts."""

    def wrapped(system: str, user: str) -> str:
        key = hashlib.sha256(f"{model}\x00{system}\x00{user}".encode()).hexdigest()
        path = cache_dir / f"{key}.txt"
        if path.is_file():
            return path.read_text(encoding="utf-8")
        reply = chat(system, user)
        with atomic_text_writer(path) as handle:
            handle.write(reply)
        return reply

    return wrapped


def parse_json_reply(reply: str) -> dict[str, Any]:
    """Parse a JSON object reply, tolerating a surrounding Markdown code fence."""
    text = reply.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise LlmError(f"reply is not valid JSON: {reply[:200]}") from error
    if not isinstance(payload, dict):
        raise LlmError("reply JSON is not an object")
    return payload
