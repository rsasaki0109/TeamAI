from __future__ import annotations

import json
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from teamai.config.models import AgentConfig
from teamai.core.domain import ModelMessage, ModelRequest, ModelResponse, ModelUsage
from teamai.core.errors import ModelOutputError
from teamai.core.events import EventEmitter
from teamai.core.protocols import ModelClient

T = TypeVar("T", bound=BaseModel)


class LLMAgent:
    def __init__(
        self,
        name: str,
        config: AgentConfig,
        model_name: str,
        model_client: ModelClient,
        max_output_tokens: int,
        max_parse_retries: int,
        model_call_guard: Callable[[], None] | None = None,
        event_emitter: EventEmitter | None = None,
    ) -> None:
        self.name = name
        self.config = config
        self.model_name = model_name
        self.model_client = model_client
        self.max_output_tokens = max_output_tokens
        self.max_parse_retries = max_parse_retries
        self._model_call_guard = model_call_guard or (lambda: None)
        self._events = event_emitter

    async def _complete(
        self,
        *,
        system: str,
        user: str,
        output_schema: str,
        metadata: dict[str, object],
    ) -> ModelResponse:
        self._model_call_guard()
        request = ModelRequest(
            model=self.model_name,
            messages=[
                ModelMessage(role="system", content=system),
                ModelMessage(role="user", content=user),
            ],
            output_schema=output_schema,
            max_output_tokens=self.max_output_tokens,
            metadata={
                **metadata,
                "agent_name": self.name,
                "agent_kind": self.config.kind.value,
                "output_schema": output_schema,
            },
        )
        return await self.model_client.complete(request)

    async def _complete_structured(
        self,
        *,
        system: str,
        user: str,
        output_schema: str,
        metadata: dict[str, object],
        model_type: type[T],
    ) -> tuple[T, ModelUsage]:
        usage = ModelUsage()
        current_user = user
        last_error: ModelOutputError | None = None
        for attempt in range(self.max_parse_retries + 1):
            response = await self._complete(
                system=system,
                user=current_user,
                output_schema=output_schema,
                metadata={**metadata, "parse_attempt": attempt},
            )
            usage.add(response.usage)
            try:
                return self._parse(response, model_type), usage
            except ModelOutputError as exc:
                last_error = exc
                await self._emit_output_invalid(
                    output_schema=output_schema,
                    metadata=metadata,
                    attempt=attempt,
                    error=exc,
                )
                if attempt >= self.max_parse_retries:
                    break
                current_user = (
                    f"{user}\n\n"
                    "The previous response was invalid for the required JSON schema. "
                    "Return only valid JSON. Do not include markdown fences.\n"
                    f"Validation error:\n{exc}"
                )
        if last_error is None:
            raise ModelOutputError(f"model output did not match {model_type.__name__}")
        raise last_error

    def _parse(self, response: ModelResponse, model_type: type[T]) -> T:
        try:
            content = _extract_json(response.content)
        except ValueError as exc:
            raise ModelOutputError(f"model output was not valid JSON: {exc}") from exc
        try:
            return model_type.model_validate_json(content)
        except ValidationError as exc:
            raise ModelOutputError(
                f"model output did not match {model_type.__name__}: {exc}"
            ) from exc

    async def _emit_output_invalid(
        self,
        *,
        output_schema: str,
        metadata: dict[str, object],
        attempt: int,
        error: Exception,
    ) -> None:
        if self._events is None:
            return
        await self._events.emit(
            "model.output_invalid",
            actor=self.name,
            task_id=_task_id_from_metadata(metadata),
            payload={
                "output_schema": output_schema,
                "attempt": attempt,
                "error": str(error),
            },
        )


def _extract_json(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    json.loads(stripped)
    return stripped


def _task_id_from_metadata(metadata: dict[str, object]) -> str | None:
    task = metadata.get("task")
    if isinstance(task, dict):
        task_id = task.get("id")
        if isinstance(task_id, str):
            return task_id
    return None
