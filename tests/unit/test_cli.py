import asyncio
import json
from pathlib import Path

import pytest

from teamai import TeamRuntime
from teamai.cli.app import _inspect, _list_runs, _run, _schema, _validate


def test_cli_validate_accepts_valid_teamfile(capsys: pytest.CaptureFixture[str]) -> None:
    _validate(Path("examples/minimal/team.yaml"))

    assert "valid Teamfile: minimal_team" in capsys.readouterr().out


def test_cli_validate_exits_for_invalid_teamfile(tmp_path: Path) -> None:
    source = Path("examples/minimal/team.yaml").read_text(encoding="utf-8")
    teamfile = tmp_path / "team.yaml"
    teamfile.write_text(
        source.replace("filesystem.write", "filesystem.delete"),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="unknown tool"):
        _validate(teamfile)


def test_cli_schema_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    _schema()

    payload = json.loads(capsys.readouterr().out)
    assert payload["title"] == "Teamfile"
    assert "models" in payload["properties"]
    assert "agents" in payload["properties"]


def test_cli_schema_writes_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "schema" / "teamfile.schema.json"

    _schema(output)

    assert f"wrote {output}" in capsys.readouterr().out
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["title"] == "Teamfile"


def test_cli_run_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    teamfile = tmp_path / "team.yaml"
    teamfile.write_text(
        Path("examples/pipeline/team.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    asyncio.run(_run(teamfile, "Create a run JSON note", yes=False, output_json=True))

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "succeeded"
    assert payload["final_output"].startswith("Run completed successfully")
    assert payload["usage"]["total_tokens"] > 0
    assert payload["artifacts"][0]["summary"] == "Completed: Create a run JSON note"


def test_cli_inspect_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    teamfile = tmp_path / "team.yaml"
    teamfile.write_text(
        Path("examples/minimal/team.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    async def run() -> None:
        async with TeamRuntime.from_file(teamfile) as runtime:
            result = await runtime.run(goal="Create an inspect JSON note")
        await _inspect(
            result.run_id,
            tmp_path / ".teamai" / "runs.sqlite",
            output_json=True,
        )

    asyncio.run(run())

    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["status"] == "succeeded"
    assert payload["summary"]["model_calls"] == 4
    assert payload["summary"]["artifact_count"] == 1
    assert payload["run"]["usage"]["total_tokens"] > 0
    assert payload["events"][0]["type"] == "run.created"


def test_cli_inspect_text_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    teamfile = tmp_path / "team.yaml"
    teamfile.write_text(
        Path("examples/pipeline/team.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    async def run() -> None:
        async with TeamRuntime.from_file(teamfile) as runtime:
            result = await runtime.run(goal="Create an inspect text note")
        await _inspect(result.run_id, tmp_path / ".teamai" / "runs.sqlite")

    asyncio.run(run())

    output = capsys.readouterr().out
    assert "status: succeeded" in output
    assert "model_calls: 3" in output
    assert "artifact_summaries:" in output
    assert "task=task_1 type=text summary=Completed: Create an inspect text note" in output
    assert "events:" in output


def test_cli_inspect_latest_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    teamfile = tmp_path / "team.yaml"
    teamfile.write_text(
        Path("examples/minimal/team.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    async def run() -> None:
        async with TeamRuntime.from_file(teamfile) as runtime:
            first = await runtime.run(goal="Create first latest note")
            second = await runtime.run(goal="Create second latest note")
        assert first.run_id != second.run_id
        await _inspect(
            None,
            tmp_path / ".teamai" / "runs.sqlite",
            latest=True,
            output_json=True,
        )

    asyncio.run(run())

    payload = json.loads(capsys.readouterr().out)
    assert "Create second latest note" in payload["run"]["final_output"]


def test_cli_inspect_requires_run_id_without_latest(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="run_id is required"):
        asyncio.run(_inspect(None, tmp_path / ".teamai" / "runs.sqlite"))


def test_cli_list_runs_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    teamfile = tmp_path / "team.yaml"
    teamfile.write_text(
        Path("examples/minimal/team.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    async def run() -> None:
        async with TeamRuntime.from_file(teamfile) as runtime:
            await runtime.run(goal="Create first list note")
            await runtime.run(goal="Create second list note")
        await _list_runs(
            tmp_path / ".teamai" / "runs.sqlite",
            limit=1,
            output_json=True,
        )

    asyncio.run(run())

    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 1
    assert payload[0]["goal"] == "Create second list note"
    assert payload[0]["status"] == "succeeded"


def test_cli_list_runs_text_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    teamfile = tmp_path / "team.yaml"
    teamfile.write_text(
        Path("examples/pipeline/team.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    async def run() -> None:
        async with TeamRuntime.from_file(teamfile) as runtime:
            await runtime.run(goal="Create list text note")
        await _list_runs(tmp_path / ".teamai" / "runs.sqlite")

    asyncio.run(run())

    output = capsys.readouterr().out
    assert "succeeded" in output
    assert "Create list text note" in output


def test_cli_list_runs_empty_db(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    asyncio.run(_list_runs(tmp_path / "empty.sqlite"))

    assert capsys.readouterr().out.strip() == "no runs"


def test_cli_list_runs_rejects_invalid_limit(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="limit"):
        asyncio.run(_list_runs(tmp_path / "runs.sqlite", limit=0))
