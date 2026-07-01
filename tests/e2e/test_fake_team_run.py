import asyncio
import sqlite3
from pathlib import Path

import pytest

from teamai import TeamRuntime
from teamai.core.errors import ApprovalRejectedError, BudgetExceededError
from teamai.core.states import RunStatus
from teamai.persistence.sqlite import SQLiteStore


def test_fake_team_run_succeeds(tmp_path: Path) -> None:
    teamfile = tmp_path / "team.yaml"
    source = Path("examples/minimal/team.yaml").read_text(encoding="utf-8")
    teamfile.write_text(source, encoding="utf-8")

    async def run() -> None:
        async with TeamRuntime.from_file(teamfile) as runtime:
            result = await runtime.run(goal="Create a short implementation note")

        assert result.status == RunStatus.SUCCEEDED
        assert result.artifacts
        assert "Run completed successfully" in result.final_output
        assert result.usage.prompt_tokens > 0
        assert result.usage.completion_tokens > 0
        assert result.usage.total_tokens == (
            result.usage.prompt_tokens + result.usage.completion_tokens
        )

    asyncio.run(run())


def test_fake_team_run_records_model_events(tmp_path: Path) -> None:
    teamfile = tmp_path / "team.yaml"
    source = Path("examples/minimal/team.yaml").read_text(encoding="utf-8")
    teamfile.write_text(source, encoding="utf-8")

    async def run() -> None:
        async with TeamRuntime.from_file(teamfile) as runtime:
            result = await runtime.run(goal="Create a short implementation note")

        store = SQLiteStore(tmp_path / ".teamai" / "runs.sqlite")
        try:
            events = await store.list_events(result.run_id)
        finally:
            await store.aclose()

        event_types = [event.type for event in events]
        assert event_types.count("model.requested") == 4
        assert event_types.count("model.completed") == 4

    asyncio.run(run())


def test_fake_team_run_executes_structured_tool_request(tmp_path: Path) -> None:
    teamfile = tmp_path / "team.yaml"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "input.txt").write_text("hello", encoding="utf-8")
    source = Path("examples/minimal/team.yaml").read_text(encoding="utf-8")
    teamfile.write_text(source, encoding="utf-8")

    async def run() -> None:
        async with TeamRuntime.from_file(teamfile) as runtime:
            result = await runtime.run(goal="List workspace files using tools")

        assert result.status == RunStatus.SUCCEEDED
        assert result.artifacts[0].metadata["tool_results"][0]["name"] == "filesystem.list"

        store = SQLiteStore(tmp_path / ".teamai" / "runs.sqlite")
        try:
            events = await store.list_events(result.run_id)
        finally:
            await store.aclose()

        event_types = [event.type for event in events]
        assert "tool.requested" in event_types
        assert "tool.completed" in event_types

    asyncio.run(run())


def test_pipeline_team_run_succeeds_without_planner(tmp_path: Path) -> None:
    teamfile = tmp_path / "team.yaml"
    source = Path("examples/pipeline/team.yaml").read_text(encoding="utf-8")
    teamfile.write_text(source, encoding="utf-8")

    async def run() -> None:
        async with TeamRuntime.from_file(teamfile) as runtime:
            result = await runtime.run(goal="Create a short implementation note")

        assert result.status == RunStatus.SUCCEEDED

        store = SQLiteStore(tmp_path / ".teamai" / "runs.sqlite")
        try:
            events = await store.list_events(result.run_id)
        finally:
            await store.aclose()

        event_types = [event.type for event in events]
        assert "pipeline.started" in event_types
        assert "plan.requested" not in event_types
        assert event_types.count("model.completed") == 3

    asyncio.run(run())


def test_run_model_call_budget_exhaustion_is_persisted(tmp_path: Path) -> None:
    teamfile = tmp_path / "team.yaml"
    source = Path("examples/minimal/team.yaml").read_text(encoding="utf-8")
    teamfile.write_text(
        source.replace("max_model_calls: 30", "max_model_calls: 1"),
        encoding="utf-8",
    )

    async def run() -> None:
        async with TeamRuntime.from_file(teamfile) as runtime:
            with pytest.raises(BudgetExceededError, match="max_model_calls"):
                await runtime.run(goal="Create a short implementation note")

    asyncio.run(run())

    connection = sqlite3.connect(tmp_path / ".teamai" / "runs.sqlite")
    try:
        run_row = connection.execute("select status, final_output from runs").fetchone()
        event_rows = connection.execute("select type from events order by sequence").fetchall()
    finally:
        connection.close()

    assert run_row == ("failed", "run exceeded max_model_calls")
    assert ("run.failed",) in event_rows


def test_runtime_rejects_write_tool_by_default(tmp_path: Path) -> None:
    teamfile = tmp_path / "team.yaml"
    source = Path("examples/minimal/team.yaml").read_text(encoding="utf-8")
    teamfile.write_text(source, encoding="utf-8")

    async def run() -> None:
        async with TeamRuntime.from_file(teamfile) as runtime:
            with pytest.raises(ApprovalRejectedError, match="approval provider"):
                await runtime.run(goal="Write workspace file using tools")

    asyncio.run(run())

    assert not (tmp_path / "workspace" / "teamai-output.txt").exists()


def test_runtime_auto_approve_allows_write_tool(tmp_path: Path) -> None:
    teamfile = tmp_path / "team.yaml"
    source = Path("examples/minimal/team.yaml").read_text(encoding="utf-8")
    teamfile.write_text(source, encoding="utf-8")

    async def run() -> None:
        async with TeamRuntime.from_file(teamfile, auto_approve=True) as runtime:
            result = await runtime.run(goal="Write workspace file using tools")
        assert result.status == RunStatus.SUCCEEDED

    asyncio.run(run())

    assert (
        tmp_path / "workspace" / "teamai-output.txt"
    ).read_text(encoding="utf-8") == "Created by FakeModelClient"


def test_high_risk_task_requires_approval_by_default(tmp_path: Path) -> None:
    teamfile = tmp_path / "team.yaml"
    source = Path("examples/minimal/team.yaml").read_text(encoding="utf-8")
    teamfile.write_text(source, encoding="utf-8")

    async def run() -> None:
        async with TeamRuntime.from_file(teamfile) as runtime:
            with pytest.raises(ApprovalRejectedError, match="approval provider"):
                await runtime.run(goal="High risk implementation note")

    asyncio.run(run())

    connection = sqlite3.connect(tmp_path / ".teamai" / "runs.sqlite")
    try:
        event_types = [
            row[0] for row in connection.execute("select type from events order by sequence")
        ]
    finally:
        connection.close()

    assert "approval.requested" in event_types
    assert "approval.completed" in event_types
    assert "task.ready" not in event_types


def test_high_risk_task_runs_with_explicit_auto_approve(tmp_path: Path) -> None:
    teamfile = tmp_path / "team.yaml"
    source = Path("examples/minimal/team.yaml").read_text(encoding="utf-8")
    teamfile.write_text(source, encoding="utf-8")

    async def run() -> None:
        async with TeamRuntime.from_file(teamfile, auto_approve=True) as runtime:
            result = await runtime.run(goal="High risk implementation note")
        assert result.status == RunStatus.SUCCEEDED

    asyncio.run(run())


def test_plan_approval_required_rejects_before_task_ready(tmp_path: Path) -> None:
    teamfile = tmp_path / "team.yaml"
    source = Path("examples/minimal/team.yaml").read_text(encoding="utf-8")
    teamfile.write_text(
        source.replace("require_plan_approval: false", "require_plan_approval: true"),
        encoding="utf-8",
    )

    async def run() -> None:
        async with TeamRuntime.from_file(teamfile) as runtime:
            with pytest.raises(ApprovalRejectedError, match="approval provider"):
                await runtime.run(goal="Create a plan-gated note")

    asyncio.run(run())

    connection = sqlite3.connect(tmp_path / ".teamai" / "runs.sqlite")
    try:
        event_rows = connection.execute(
            "select type, task_id from events order by sequence"
        ).fetchall()
    finally:
        connection.close()

    assert ("approval.requested", None) in event_rows
    assert ("approval.completed", None) in event_rows
    assert ("task.ready", "task_1") not in event_rows


def test_plan_approval_required_runs_with_explicit_auto_approve(tmp_path: Path) -> None:
    teamfile = tmp_path / "team.yaml"
    source = Path("examples/minimal/team.yaml").read_text(encoding="utf-8")
    teamfile.write_text(
        source.replace("require_plan_approval: false", "require_plan_approval: true"),
        encoding="utf-8",
    )

    async def run() -> None:
        async with TeamRuntime.from_file(teamfile, auto_approve=True) as runtime:
            result = await runtime.run(goal="Create a plan-gated note")
        assert result.status == RunStatus.SUCCEEDED

    asyncio.run(run())
