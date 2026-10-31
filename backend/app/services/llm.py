"""Thin LLM client wrapper.

Routes structured-JSON chat calls to whichever provider has an API key set.
Uses plain HTTP (requests) so the vendor SDKs stay optional. Designed for
small, cheap calls (the per-email cost target ~$0.001-0.003).

Tests can inject a fixed responder by passing a callable in place of
generate_json (see app/agents and the pipeline).
"""

import json
from typing import Callable, Mapping

import requests

from app.core.config import settings

PROVIDERS: dict[str, dict] = {
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
    if settings.openai_api_key:
        return "openai"
    if settings.anthropic_api_key:
        return "anthropic"
    if settings.gemini_api_key:
        return "gemini"
    return None


def _api_key(provider: str) -> str:
    return {
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


def _call_openai(system: str, user: str, temperature: float, max_tokens: int) -> dict:
    spec = PROVIDERS["openai"]
    resp = requests.post(
        spec["url"],
        headers={
            "Authorization": f"Bearer {_api_key('openai')}",
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
        timeout=120,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return _extract_json(content)


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
        timeout=120,
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
            },
        },
        timeout=120,
    )
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    return _extract_json(text)


def generate_json(
    system: str,
    user: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> dict:
    """One structured-JSON chat call through the configured provider."""
    provider = detect_provider()
    if provider is None:
        raise RuntimeError(
            "No LLM API key configured. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GEMINI_API_KEY."
        )
    callers: Mapping[str, Callable[..., dict]] = {
        "openai": _call_openai,
        "anthropic": _call_anthropic,
        "gemini": _call_gemini,
    }
    return callers[provider](system, user, temperature, max_tokens)


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