import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from teamai.config.models import SecurityConfig
from teamai.core.budgets import Budget, BudgetLimits
from teamai.core.domain import ApprovalDecision, ApprovalRequest
from teamai.core.errors import ApprovalRejectedError
from teamai.core.events import Event, EventEmitter
from teamai.tools.base import ToolRegistry
from teamai.tools.broker import ToolBroker
from teamai.tools.builtin.filesystem import build_filesystem_tools


class MemoryEventStore:
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def append_event(self, event: Event) -> None:
        self.events.append(event)


class RejectApprovalProvider:
    def __init__(self) -> None:
        self.requests: list[ApprovalRequest] = []

    async def request(self, request: ApprovalRequest) -> ApprovalDecision:
        self.requests.append(request)
        return ApprovalDecision(approved=False, comment="no")


def test_tool_broker_emits_approval_events_and_rejects_write(tmp_path: Path) -> None:
    run_id = uuid4()
    event_store = MemoryEventStore()
    approval_provider = RejectApprovalProvider()
    broker = ToolBroker(
        registry=ToolRegistry(
            build_filesystem_tools(
                root=tmp_path,
                max_read_bytes=1024,
                max_write_bytes=1024,
            )
        ),
        security=SecurityConfig(workspace_root=str(tmp_path)),
        budget=Budget(
            BudgetLimits(
                max_model_calls=10,
                max_tool_calls=10,
                max_tasks=3,
                max_revisions_per_task=1,
                max_runtime_seconds=60,
                max_output_tokens_per_call=1024,
                max_parallel_tasks=1,
            )
        ),
        approval_provider=approval_provider,
        event_emitter=EventEmitter(run_id, event_store),
        run_id=run_id,
    )

    async def run() -> None:
        with pytest.raises(ApprovalRejectedError):
            await broker.execute(
                "filesystem.write",
                {"path": "out.txt", "content": "hello"},
                actor="coder",
                task_id="task_1",
                allowed_tools={"filesystem.write"},
            )

    asyncio.run(run())

    event_types = [event.type for event in event_store.events]
    assert event_types == ["tool.requested", "approval.requested", "approval.completed"]
    assert approval_provider.requests[0].preview is not None
    assert "hello" in approval_provider.requests[0].preview


def test_tool_broker_redacts_write_content_from_events(tmp_path: Path) -> None:
    run_id = uuid4()
    event_store = MemoryEventStore()
    approval_provider = RejectApprovalProvider()
    broker = ToolBroker(
        registry=ToolRegistry(
            build_filesystem_tools(
                root=tmp_path,
                max_read_bytes=1024,
                max_write_bytes=1024,
            )
        ),
        security=SecurityConfig(workspace_root=str(tmp_path)),
        budget=Budget(
            BudgetLimits(
                max_model_calls=10,
                max_tool_calls=10,
                max_tasks=3,
                max_revisions_per_task=1,
                max_runtime_seconds=60,
                max_output_tokens_per_call=1024,
                max_parallel_tasks=1,
            )
        ),
        approval_provider=approval_provider,
        event_emitter=EventEmitter(run_id, event_store),
        run_id=run_id,
    )

    async def run() -> None:
        with pytest.raises(ApprovalRejectedError):
            await broker.execute(
                "filesystem.write",
                {"path": "out.txt", "content": "secret-token-value"},
                actor="coder",
                task_id="task_1",
                allowed_tools={"filesystem.write"},
            )

    asyncio.run(run())

    requested = event_store.events[0].payload
    approval_requested = event_store.events[1].payload
    assert requested["arguments"]["content"] == "<redacted string chars=18>"
    assert approval_requested["redacted_arguments"]["content"] == "<redacted string chars=18>"
    assert str(approval_requested["preview"]).startswith("<redacted string chars=")
    assert "secret-token-value" not in str([event.payload for event in event_store.events])


def test_tool_broker_redacts_read_content_from_completed_event(tmp_path: Path) -> None:
    (tmp_path / "secret.txt").write_text("secret-file-content", encoding="utf-8")
    run_id = uuid4()
    event_store = MemoryEventStore()
    broker = ToolBroker(
        registry=ToolRegistry(
            build_filesystem_tools(
                root=tmp_path,
                max_read_bytes=1024,
                max_write_bytes=1024,
            )
        ),
        security=SecurityConfig(workspace_root=str(tmp_path)),
        budget=Budget(
            BudgetLimits(
                max_model_calls=10,
                max_tool_calls=10,
                max_tasks=3,
                max_revisions_per_task=1,
                max_runtime_seconds=60,
                max_output_tokens_per_call=1024,
                max_parallel_tasks=1,
            )
        ),
        approval_provider=RejectApprovalProvider(),
        event_emitter=EventEmitter(run_id, event_store),
        run_id=run_id,
    )

    async def run() -> None:
        result = await broker.execute(
            "filesystem.read",
            {"path": "secret.txt"},
            actor="coder",
            task_id="task_1",
            allowed_tools={"filesystem.read"},
        )
        assert result.output["content"] == "secret-file-content"

    asyncio.run(run())

    completed = event_store.events[1].payload
    assert completed["output"]["content"] == "<redacted string chars=19>"
    assert "secret-file-content" not in str([event.payload for event in event_store.events])
