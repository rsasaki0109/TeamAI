from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Event(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    sequence: int
    type: str
    actor: str
    task_id: str | None = None
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)


class EventEmitter:
    def __init__(self, run_id: UUID, store: EventStoreProtocol) -> None:
        self._run_id = run_id
        self._store = store
        self._sequence = 0

    async def emit(
        self,
        event_type: str,
        *,
        actor: str,
        task_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Event:
        self._sequence += 1
        event = Event(
            run_id=self._run_id,
            sequence=self._sequence,
            type=event_type,
            actor=actor,
            task_id=task_id,
            payload=payload or {},
        )
        await self._store.append_event(event)
        return event


class EventStoreProtocol(Protocol):
    async def append_event(self, event: Event) -> None:
        raise NotImplementedError
