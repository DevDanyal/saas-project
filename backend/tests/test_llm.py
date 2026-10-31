import pytest

from app.services import llm
from app.services.llm import FakeLlm


def test_extract_json_strips_fences():
    assert llm._extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm._extract_json('{"a": 1}') == {"a": 1}
    assert llm._extract_json('sure, here you go: {"a": 1} hope that helps') == {"a": 1}


def test_extract_json_raises_on_no_json():
    with pytest.raises(ValueError):
        llm._extract_json("I could not process that request.")


def test_detect_provider_is_none_without_keys(monkeypatch):
    monkeypatch.setattr(llm.settings, "openai_api_key", "")
    monkeypatch.setattr(llm.settings, "anthropic_api_key", "")
    monkeypatch.setattr(llm.settings, "gemini_api_key", "")
    assert llm.detect_provider() is None


def test_generate_json_raises_without_key(monkeypatch):
    monkeypatch.setattr(llm.settings, "openai_api_key", "")
    monkeypatch.setattr(llm.settings, "anthropic_api_key", "")
    monkeypatch.setattr(llm.settings, "gemini_api_key", "")
    with pytest.raises(RuntimeError):
        llm.generate_json("system", "user")


def test_fake_llm_sequential():
    fake = FakeLlm(responses=[{"a": 1}, {"b": 2}])
    assert fake("s", "u1") == {"a": 1}
    assert fake("s", "u2") == {"b": 2}
    with pytest.raises(AssertionError):
        fake("s", "u3")


def test_fake_llm_by_keyword():
    fake = FakeLlm(by_keyword={"pre-approved": {"category": "lead"}})
    assert fake("s", "we are pre-approved for 450k") == {"category": "lead"}
    with pytest.raises(AssertionError):
        fake("s", "no matching keyword")