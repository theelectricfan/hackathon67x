"""Tests for LLM client layer — no real API calls made."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
import pytest


# ── Settings ──────────────────────────────────────────────────────────────────

def test_settings_have_defaults():
    from config.settings import settings
    assert settings.ANTHROPIC_MODEL == "claude-sonnet-4-20250514"
    assert settings.ANTHROPIC_MAX_TOKENS == 4096
    assert settings.LLM_RETRY_ATTEMPTS == 3
    assert settings.LLM_RETRY_DELAY == 2
    assert settings.RCA_CONFIDENCE_THRESHOLD == 60
    assert settings.DEFAULT_EXTRACTION_MODEL == "gemini-1.5-flash"
    assert settings.DEFAULT_PARALLEL_PROCESSOR == "base-fast"


def test_settings_log_llm_calls_default_true():
    from config.settings import settings
    assert settings.LOG_LLM_CALLS is True


# ── LLM Client importable ────────────────────────────────────────────────────

def test_llm_client_importable():
    from llm.client import llm, LLMClient
    assert isinstance(llm, LLMClient)


def test_llm_singleton():
    from llm.client import llm as a
    from llm import llm as b
    assert a is b


# ── extract_json ──────────────────────────────────────────────────────────────

from llm.utils import extract_json


def test_extract_json_clean():
    result = extract_json('{"bucket": "MCAT_MISMATCH", "confidence": 85}')
    assert result["bucket"] == "MCAT_MISMATCH"
    assert result["confidence"] == 85


def test_extract_json_markdown_block():
    text = '```json\n{"bucket": "THIN_CONTENT", "confidence": 70}\n```'
    result = extract_json(text)
    assert result["bucket"] == "THIN_CONTENT"


def test_extract_json_extra_text_around():
    text = 'Here is the result:\n{"bucket": "LOW_BUYER_INTENT", "confidence": 90}\nEnd.'
    result = extract_json(text)
    assert result["bucket"] == "LOW_BUYER_INTENT"


def test_extract_json_empty_string():
    result = extract_json("")
    assert result == {}


def test_extract_json_none_like():
    result = extract_json(None)
    assert result == {}


def test_extract_json_plain_markdown_no_lang():
    text = '```\n{"bucket": "SPEC_CONTRADICTION", "confidence": 60}\n```'
    result = extract_json(text)
    assert result["bucket"] == "SPEC_CONTRADICTION"


def test_extract_json_returns_error_on_garbage():
    result = extract_json("this is not json at all !@#$")
    assert "error" in result or result == {}


# ── with_retry ────────────────────────────────────────────────────────────────

def test_with_retry_succeeds_first_try():
    from llm.utils import with_retry
    called = []

    def ok():
        called.append(1)
        return "ok"

    result = with_retry(ok)
    assert result == "ok"
    assert len(called) == 1


def test_with_retry_retries_then_succeeds():
    from llm.utils import with_retry
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 2:
            raise ValueError("transient error")
        return "recovered"

    with patch("llm.utils.settings") as mock_settings:
        mock_settings.LLM_RETRY_ATTEMPTS = 3
        mock_settings.LLM_RETRY_DELAY = 0
        with patch("llm.utils.time.sleep"):
            result = with_retry(flaky)

    assert result == "recovered"
    assert len(attempts) == 2


def test_with_retry_raises_after_all_attempts():
    from llm.utils import with_retry

    def always_fails():
        raise ConnectionError("gateway down")

    with patch("llm.utils.settings") as mock_settings:
        mock_settings.LLM_RETRY_ATTEMPTS = 2
        mock_settings.LLM_RETRY_DELAY = 0
        with patch("llm.utils.time.sleep"):
            with pytest.raises(ConnectionError):
                with_retry(always_fails)


# ── LLMClient methods (mocked) ────────────────────────────────────────────────

def test_llm_chat_calls_gateway():
    from llm.client import LLMClient
    client = LLMClient()
    with patch("llm.client.call_llm", return_value="raw response") as mock_call:
        result = client.chat(system="sys", user="usr")
    assert result == "raw response"
    mock_call.assert_called_once_with(
        system="sys", user="usr", model=None, temperature=0.0, max_tokens=4096
    )


def test_llm_chat_json_parses_result():
    from llm.client import LLMClient
    client = LLMClient()
    with patch("llm.client.call_llm", return_value='{"bucket":"MCAT_MISMATCH","confidence":80}'):
        result = client.chat_json(system="sys", user="usr")
    assert result["bucket"] == "MCAT_MISMATCH"
    assert result["confidence"] == 80


def test_llm_chat_with_tools_calls_anthropic():
    from llm.client import LLMClient
    client = LLMClient()
    mock_response = MagicMock()

    with patch("llm.client.get_anthropic_client") as mock_get:
        mock_get.return_value.messages.create.return_value = mock_response
        with patch("llm.client.settings") as mock_settings:
            mock_settings.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
            mock_settings.ANTHROPIC_MAX_TOKENS = 4096
            mock_settings.LOG_LLM_CALLS = False
            result = client.chat_with_tools(
                messages=[{"role": "user", "content": "hello"}],
                tools=[{"name": "run_skill_intent"}],
                system="You are orchestrator",
            )

    assert result is mock_response


def test_llm_parse_json_delegates_to_extract_json():
    from llm.client import LLMClient
    client = LLMClient()
    result = client.parse_json('{"key": "value"}')
    assert result == {"key": "value"}
