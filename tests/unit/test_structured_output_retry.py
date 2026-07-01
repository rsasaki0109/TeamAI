import asyncio
import json
from typing import Any
from uuid import uuid4

import pytest

from teamai.agents.planner import PlannerAgent
from teamai.config.models import AgentConfig
from teamai.core.domain import AgentKind, ModelRequest, ModelResponse, ModelUsage
from teamai.core.errors import ModelOutputError
from teamai.core.events import Event, EventEmitter


class MemoryEventStore:
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def append_event(self, event: Event) -> None:
        self.events.append(event)


class FlakyPlanClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    async def complete(self, request: ModelRequest) -> ModelResponse:
        content = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return ModelResponse(content=content, usage=ModelUsage(total_tokens=1))

    async def aclose(self) -> None:
        return None


def _valid_plan_json() -> str:
    return json.dumps(
        {
            "summary": "Recovered plan",
            "tasks": [
                {
                    "id": "task_1",
                    "objective": "Do the work",
                    "required_capabilities": [],
                    "dependencies": [],
                    "acceptance_criteria": ["Done"],
                    "expected_artifact_type": "text",
                    "risk": "low",
                }
            ],
            "final_acceptance_criteria": ["Done"],
        }
    )


def _planner(
    client: FlakyPlanClient,
    *,
    max_parse_retries: int,
    guard: Any,
    event_store: MemoryEventStore,
) -> PlannerAgent:
    return PlannerAgent(
        "planner",
        AgentConfig(kind=AgentKind.PLANNER, model="default", capabilities={"planning"}),
        "fake",
        client,
        1024,
        max_parse_retries,
        guard,
        EventEmitter(uuid4(), event_store),
    )


def test_structured_output_retry_recovers_after_invalid_json() -> None:
    client = FlakyPlanClient(["not json", _valid_plan_json()])
    event_store = MemoryEventStore()
    guard_calls = 0

    def guard() -> None:
        nonlocal guard_calls
        guard_calls += 1

    async def run() -> None:
        planner = _planner(
            client,
            max_parse_retries=1,
            guard=guard,
            event_store=event_store,
        )
        plan, usage = await planner.create_plan(
            goal="Do the work",
            available_agents=[],
            tool_names=[],
        )

        assert plan.summary == "Recovered plan"
        assert usage.total_tokens == 2

    asyncio.run(run())

    assert client.calls == 2
    assert guard_calls == 2
    assert [event.type for event in event_store.events] == ["model.output_invalid"]


def test_structured_output_retry_exhaustion_raises() -> None:
    client = FlakyPlanClient(["not json"])
    event_store = MemoryEventStore()
    guard_calls = 0

    def guard() -> None:
        nonlocal guard_calls
        guard_calls += 1

    async def run() -> None:
        planner = _planner(
            client,
            max_parse_retries=1,
            guard=guard,
            event_store=event_store,
        )
        with pytest.raises(ModelOutputError):
            await planner.create_plan(
                goal="Do the work",
                available_agents=[],
                tool_names=[],
            )

    asyncio.run(run())

    assert client.calls == 2
    assert guard_calls == 2
    assert [event.type for event in event_store.events] == [
        "model.output_invalid",
        "model.output_invalid",
    ]
