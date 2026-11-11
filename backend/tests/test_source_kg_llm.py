"""API-contract tests for the source compiler's optional LLM client."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from kgtracevis.source_kg_compiler.llm import OpenAICompatibleSourceKGLLM


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch):
    monkeypatch.setattr("kgtracevis.source_kg_compiler.llm.load_source_kg_env", lambda: None)
    for name in ("SOURCE_KG_LLM_API", "SOURCE_KG_REASONING_EFFORT"):
        monkeypatch.delenv(name, raising=False)


def test_responses_uses_reasoning_and_accounts_for_usage(monkeypatch):
    monkeypatch.setenv("SOURCE_KG_LLM_API", "responses")
    monkeypatch.setenv("SOURCE_KG_REASONING_EFFORT", "high")
    llm = OpenAICompatibleSourceKGLLM(api_key="test-only", model="test-model")
    create = Mock(
        return_value=SimpleNamespace(
            status="completed",
            output_text='{"ok":true}',
            usage=SimpleNamespace(input_tokens=11, output_tokens=7),
        )
    )
    llm._client = SimpleNamespace(responses=SimpleNamespace(create=create))
    assert llm.complete_json(system_prompt="Return JSON", user_prompt="test") == '{"ok":true}'
    kwargs = create.call_args.kwargs
    assert kwargs["reasoning"] == {"effort": "high"}
    assert kwargs["text"] == {"format": {"type": "json_object"}}
    assert kwargs["max_output_tokens"] == 8192
    assert kwargs["store"] is False
    assert not {"temperature", "messages", "max_tokens", "response_format"} & kwargs.keys()
    assert (llm.calls, llm.input_tokens, llm.output_tokens, llm.total_tokens) == (1, 11, 7, 18)


@pytest.mark.parametrize("status,text", [("incomplete", "{}"), ("completed", "")])
def test_responses_rejects_incomplete_or_empty_results(status, text):
    llm = OpenAICompatibleSourceKGLLM(api_key="test-only", wire_api="responses")
    llm._client = SimpleNamespace(
        responses=SimpleNamespace(
            create=Mock(return_value=SimpleNamespace(status=status, output_text=text, usage=None))
        )
    )
    with pytest.raises(ValueError):
        llm.complete_json(system_prompt="JSON", user_prompt="test")
    assert llm.calls == 1


def test_chat_default_preserves_deepseek_contract():
    llm = OpenAICompatibleSourceKGLLM(api_key="test-only", model="deepseek-test")
    create = Mock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))],
            usage=SimpleNamespace(prompt_tokens=13, completion_tokens=5),
        )
    )
    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    llm.complete_json(system_prompt="JSON", user_prompt="test")
    kwargs = create.call_args.kwargs
    assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["temperature"] == 0.0
    assert "reasoning" not in kwargs
    assert llm.total_tokens == 18


def test_invalid_wire_api_fails_early():
    with pytest.raises(ValueError, match="SOURCE_KG_LLM_API"):
        OpenAICompatibleSourceKGLLM(api_key="test-only", wire_api="invalid")


@pytest.mark.parametrize("wire_api", ["chat_completions", "responses"])
def test_source_sdk_disables_transport_retries_and_propagates_failure(monkeypatch, wire_api):
    create = Mock(side_effect=TimeoutError("controlled provider timeout"))
    sdk = Mock(
        return_value=SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
            responses=SimpleNamespace(create=create),
        )
    )
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=sdk))
    llm = OpenAICompatibleSourceKGLLM(
        api_key="test-only", base_url="https://fixture.invalid/v1", wire_api=wire_api
    )

    with pytest.raises(TimeoutError, match="controlled provider timeout"):
        llm.complete_json(system_prompt="JSON", user_prompt="public fixture")

    sdk.assert_called_once_with(
        api_key="test-only", base_url="https://fixture.invalid/v1", max_retries=0
    )
    create.assert_called_once()
    assert llm.calls == 0  # No completed provider response was received.
