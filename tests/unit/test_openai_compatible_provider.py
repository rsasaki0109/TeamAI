import asyncio
import json

import httpx
import pytest

from teamai.config.models import ModelConfig, ProviderCapabilities
from teamai.core.domain import ModelMessage, ModelRequest
from teamai.providers.openai_compatible import OpenAICompatibleClient


def test_openai_compatible_client_sends_chat_completion_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 4,
                    "total_tokens": 7,
                },
            },
        )

    monkeypatch.setenv("TEAMAI_TEST_API_KEY", "test-key")
    config = ModelConfig(
        provider="openai_compatible",
        model="local-model",
        base_url="http://provider.test/v1",
        api_key_env="TEAMAI_TEST_API_KEY",
    )
    http_client = httpx.AsyncClient(
        base_url=config.base_url or "",
        transport=httpx.MockTransport(handler),
    )
    client = OpenAICompatibleClient(config, client=http_client)

    async def run() -> None:
        response = await client.complete(
            ModelRequest(
                model="ignored-request-model",
                messages=[ModelMessage(role="user", content="hello")],
                output_schema="Example",
                max_output_tokens=128,
            )
        )
        await client.aclose()

        assert response.content == '{"ok": true}'
        assert response.usage.prompt_tokens == 3
        assert response.usage.completion_tokens == 4
        assert response.usage.total_tokens == 7

    asyncio.run(run())

    assert captured["url"] == "http://provider.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "local-model"
    assert body["messages"] == [{"role": "user", "content": "hello"}]
    assert body["temperature"] == 0
    assert body["max_tokens"] == 128
    assert body["response_format"] == {"type": "json_object"}


def test_openai_compatible_client_omits_json_mode_and_falls_back_total_usage() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 8,
                },
            },
        )

    config = ModelConfig(
        provider="openai_compatible",
        model="local-model",
        base_url="http://provider.test/v1",
        capabilities=ProviderCapabilities(json_mode=False),
    )
    http_client = httpx.AsyncClient(
        base_url=config.base_url or "",
        transport=httpx.MockTransport(handler),
    )
    client = OpenAICompatibleClient(config, client=http_client)

    async def run() -> None:
        response = await client.complete(
            ModelRequest(
                model="ignored-request-model",
                messages=[ModelMessage(role="user", content="hello")],
                max_output_tokens=128,
            )
        )
        await client.aclose()

        assert response.usage.total_tokens == 13

    asyncio.run(run())

    body = captured["body"]
    assert isinstance(body, dict)
    assert "response_format" not in body
