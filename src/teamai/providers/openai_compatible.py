from __future__ import annotations

import os
from typing import Any

import httpx

from teamai.config.models import ModelConfig
from teamai.core.domain import ModelRequest, ModelResponse, ModelUsage


class OpenAICompatibleClient:
    def __init__(self, config: ModelConfig, client: httpx.AsyncClient | None = None) -> None:
        if config.base_url is None:
            raise ValueError("openai_compatible provider requires base_url")
        self._config = config
        self._client = client or httpx.AsyncClient(
            base_url=config.base_url.rstrip("/"),
            timeout=60.0,
        )

    async def complete(self, request: ModelRequest) -> ModelResponse:
        headers: dict[str, str] = {}
        if self._config.api_key_env:
            api_key = os.environ.get(self._config.api_key_env)
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
        messages = [message.model_dump(mode="json") for message in request.messages]
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": request.max_output_tokens,
        }
        if self._config.capabilities.json_mode:
            payload["response_format"] = {"type": "json_object"}
        response = await self._client.post("/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        content = str(data["choices"][0]["message"]["content"])
        usage_data = data.get("usage", {})
        prompt_tokens = int(usage_data.get("prompt_tokens", 0))
        completion_tokens = int(usage_data.get("completion_tokens", 0))
        total_tokens = int(usage_data.get("total_tokens", prompt_tokens + completion_tokens))
        usage = ModelUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        return ModelResponse(content=content, usage=usage)

    async def aclose(self) -> None:
        await self._client.aclose()
