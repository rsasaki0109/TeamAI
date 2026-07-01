from pathlib import Path
from uuid import uuid4

import pytest

from teamai.core.domain import RunResult
from teamai.core.states import RunStatus
from teamai.persistence.sqlite import SQLiteStore


@pytest.mark.asyncio
async def test_sqlite_store_get_latest_run(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "runs.sqlite")
    try:
        first = RunResult(
            run_id=uuid4(),
            status=RunStatus.SUCCEEDED,
            final_output="first",
            artifacts=[],
        )
        second = RunResult(
            run_id=uuid4(),
            status=RunStatus.SUCCEEDED,
            final_output="second",
            artifacts=[],
        )
        await store.save_run(first, "first goal")
        await store.save_run(second, "second goal")

        latest = await store.get_latest_run()
    finally:
        await store.aclose()

    assert latest is not None
    assert latest.run_id == second.run_id


@pytest.mark.asyncio
async def test_sqlite_store_list_runs_latest_first(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "runs.sqlite")
    try:
        first = RunResult(
            run_id=uuid4(),
            status=RunStatus.SUCCEEDED,
            final_output="first",
            artifacts=[],
        )
        second = RunResult(
            run_id=uuid4(),
            status=RunStatus.FAILED,
            final_output="second",
            artifacts=[],
        )
        await store.save_run(first, "first goal")
        await store.save_run(second, "second goal")

        summaries = await store.list_runs(limit=1)
    finally:
        await store.aclose()

    assert len(summaries) == 1
    assert summaries[0].run_id == second.run_id
    assert summaries[0].status == RunStatus.FAILED
    assert summaries[0].goal == "second goal"
