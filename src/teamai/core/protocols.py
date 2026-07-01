from __future__ import annotations

from typing import Protocol
from uuid import UUID

from teamai.core.domain import (
    ApprovalDecision,
    ApprovalRequest,
    Artifact,
    ModelRequest,
    ModelResponse,
    RunResult,
)
from teamai.core.events import Event


class ModelClient(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError

    async def aclose(self) -> None:
        raise NotImplementedError


class EventStore(Protocol):
    async def append_event(self, event: Event) -> None:
        raise NotImplementedError

    async def list_events(self, run_id: UUID) -> list[Event]:
        raise NotImplementedError


class ArtifactStore(Protocol):
    async def save_artifact(self, artifact: Artifact) -> None:
        raise NotImplementedError

    async def list_artifacts(self, run_id: UUID) -> list[Artifact]:
        raise NotImplementedError


class RunStore(EventStore, ArtifactStore, Protocol):
    async def save_run(self, result: RunResult, goal: str) -> None:
        raise NotImplementedError


class ApprovalProvider(Protocol):
    async def request(self, request: ApprovalRequest) -> ApprovalDecision:
        raise NotImplementedError
