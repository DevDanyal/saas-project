"""Thin LLM client wrapper.

Routes structured-JSON chat calls to whichever provider has an API key set.
Uses plain HTTP (requests) so the vendor SDKs stay optional. Designed for
small, cheap calls (the per-email cost target ~$0.001-0.003).

Tests can inject a fixed responder by passing a callable in place of
generate_json (see app/agents and the pipeline).
"""

import json
import time
from typing import Callable, Mapping

import requests

from app.core.config import settings

REQUEST_TIMEOUT = 30
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

PROVIDERS: dict[str, dict] = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "openai/gpt-oss-20b",
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
    },
    "anthropic": {
        "url": "https://api.anthropic.com/v1/messages",
        "model": "claude-3-5-haiku-latest",
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "model": "gemini-2.5-flash",
    },
}


def detect_provider() -> str | None:
    if settings.groq_api_key:
        return "groq"
    if settings.openai_api_key:
        return "openai"
    if settings.anthropic_api_key:
        return "anthropic"
    if settings.gemini_api_key:
        return "gemini"
    return None


def _api_key(provider: str) -> str:
    return {
        "groq": settings.groq_api_key,
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "gemini": settings.gemini_api_key,
    }[provider]


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3].rstrip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"LLM did not return JSON: {text[:400]!r}")
    return json.loads(text[start : end + 1])


def _call_openai_compatible(
    provider: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
) -> dict:
    spec = PROVIDERS[provider]
    resp = requests.post(
        spec["url"],
        headers={
            "Authorization": f"Bearer {_api_key(provider)}",
            "Content-Type": "application/json",
        },
        json={
            "model": spec["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return _extract_json(content)


def _call_openai(system: str, user: str, temperature: float, max_tokens: int) -> dict:
    return _call_openai_compatible("openai", system, user, temperature, max_tokens)


def _call_groq(system: str, user: str, temperature: float, max_tokens: int) -> dict:
    return _call_openai_compatible("groq", system, user, temperature, max_tokens)


def _call_anthropic(system: str, user: str, temperature: float, max_tokens: int) -> dict:
    spec = PROVIDERS["anthropic"]
    resp = requests.post(
        spec["url"],
        headers={
            "x-api-key": _api_key("anthropic"),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": spec["model"],
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    text = resp.json()["content"][0]["text"]
    return _extract_json(text)


def _call_gemini(system: str, user: str, temperature: float, max_tokens: int) -> dict:
    spec = PROVIDERS["gemini"]
    url = spec["url"].format(model=spec["model"])
    resp = requests.post(
        url,
        params={"key": _api_key("gemini")},
        headers={"Content-Type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
                # Gemini 2.5 Flash spends output tokens on internal "thinking"
                # by default, which can exhaust the budget before emitting any
                # text. Disable it so small JSON calls stay cheap and reliable.
                "thinkingConfig": {"thinkingBudget": 0},
            },
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    candidates = resp.json().get("candidates") or []
    if not candidates:
        raise ValueError(f"Gemini returned no candidates: {resp.text[:300]!r}")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    if not parts:
        reason = candidates[0].get("finishReason")
        raise ValueError(f"Gemini returned no text (finishReason={reason})")
    return _extract_json(parts[0].get("text", ""))


def available_providers() -> list[str]:
    # Prefer providers that are typically free/cheap and reliable; OpenAI is
    # last because its free tier is heavily rate-limited.
    providers: list[str] = []
    if settings.groq_api_key:
        providers.append("groq")
    if settings.gemini_api_key:
        providers.append("gemini")
    if settings.anthropic_api_key:
        providers.append("anthropic")
    if settings.openai_api_key:
        providers.append("openai")
    return providers


def _describe_error(exc: Exception) -> str:
    """Short, key-free description of a provider failure."""
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        body = " ".join((exc.response.text or "").split())
        return f"HTTP {exc.response.status_code}: {body[:180]}"
    return f"{type(exc).__name__}: {str(exc)[:180]}"


def _is_retryable(exc: Exception) -> bool:
    return (
        isinstance(exc, requests.HTTPError)
        and exc.response is not None
        and exc.response.status_code in RETRYABLE_STATUS
    )


def generate_json(
    system: str,
    user: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> dict:
    """One structured-JSON chat call through the configured provider.

    Falls back to other configured providers when one is rate-limited or
    unavailable, so a single bad key does not break inbox processing.
    """
    providers = available_providers()
    if not providers:
        raise RuntimeError(
            "No LLM API key configured. Set GROQ_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, or GEMINI_API_KEY."
        )
    callers: Mapping[str, Callable[..., dict]] = {
        "groq": _call_groq,
        "openai": _call_openai,
        "anthropic": _call_anthropic,
        "gemini": _call_gemini,
    }
    failures: list[str] = []
    for provider in providers:
        callback = callers[provider]
        try:
            return callback(system, user, temperature, max_tokens)
        except Exception as exc:  # noqa: BLE001 - try next provider
            if _is_retryable(exc):
                time.sleep(1)
                try:
                    return callback(system, user, temperature, max_tokens)
                except Exception as retry_exc:  # noqa: BLE001
                    exc = retry_exc
            failures.append(f"{provider}: {_describe_error(exc)}")
    raise RuntimeError("All AI providers failed — " + "; ".join(failures))


class FakeLlm:
    """Deterministic stand-in for generate_json used in tests.

    Callers may pass functions (by subject/topic) or fixed responses.
    """

    def __init__(self, responses: list[dict] | None = None, by_keyword: dict[str, dict] | None = None):
        self._responses = list(responses or [])
        self._by_keyword = by_keyword or {}
        self.calls: list[str] = []

    def __call__(self, system: str, user: str, temperature: float = 0.2, max_tokens: int = 2048) -> dict:
        self.calls.append(user)
        for keyword, resp in self._by_keyword.items():
            if keyword in user:
                return dict(resp)
        if self._responses:
            return dict(self._responses.pop(0))
        raise AssertionError(f"FakeLlm exhausted; unexpected prompt: {user[:200]!r}")