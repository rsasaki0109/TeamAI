from __future__ import annotations

from typing import Any

from teamai.core.domain import ModelRequest, ModelResponse
from teamai.core.events import EventEmitter
from teamai.core.protocols import ModelClient


class AuditedModelClient:
    def __init__(
        self,
        *,
        name: str,
        wrapped: ModelClient,
        events: EventEmitter,
    ) -> None:
        self._name = name
        self._wrapped = wrapped
        self._events = events

    async def complete(self, request: ModelRequest) -> ModelResponse:
        actor = str(request.metadata.get("agent_name") or self._name)
        task_id = _task_id_from_metadata(request.metadata)
        await self._events.emit(
            "model.requested",
            actor=actor,
            task_id=task_id,
            payload={
                "model": request.model,
                "model_config": self._name,
                "output_schema": request.output_schema,
                "max_output_tokens": request.max_output_tokens,
            },
        )
        try:
            response = await self._wrapped.complete(request)
        except Exception as exc:
            await self._events.emit(
                "model.failed",
                actor=actor,
                task_id=task_id,
                payload={"error_type": type(exc).__name__, "error": str(exc)},
            )
            raise
        await self._events.emit(
            "model.completed",
            actor=actor,
            task_id=task_id,
            payload={"usage": response.usage.model_dump(mode="json")},
        )
        return response

    async def aclose(self) -> None:
        await self._wrapped.aclose()


def _task_id_from_metadata(metadata: dict[str, Any]) -> str | None:
    task = metadata.get("task")
    if isinstance(task, dict):
        task_id = task.get("id")
        if isinstance(task_id, str):
            return task_id
    return None
