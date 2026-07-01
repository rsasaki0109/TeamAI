from __future__ import annotations

from teamai.config.models import ModelConfig, TeamConfig
from teamai.core.protocols import ModelClient
from teamai.providers.fake import FakeModelClient
from teamai.providers.openai_compatible import OpenAICompatibleClient


def build_model_client(config: ModelConfig) -> ModelClient:
    if config.provider == "fake":
        return FakeModelClient()
    if config.provider == "openai_compatible":
        return OpenAICompatibleClient(config)
    raise ValueError(f"unsupported provider: {config.provider}")


def build_model_clients(config: TeamConfig) -> dict[str, ModelClient]:
    return {name: build_model_client(model) for name, model in config.models.items()}
