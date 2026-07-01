from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from teamai.cli.init import DEFAULT_TEAMFILE
from teamai.config.loader import TeamfileValidationError
from teamai.config.schema import generate_teamfile_schema
from teamai.config.validator import validate_teamfile
from teamai.core.domain import Artifact, RunResult
from teamai.core.events import Event
from teamai.human.auto_approve import AutoApproveProvider
from teamai.human.terminal import TerminalApprovalProvider
from teamai.persistence.sqlite import SQLiteStore
from teamai.runtime import TeamRuntime

DEFAULT_LIST_LIMIT = 20
MAX_INSPECT_SUMMARY_CHARS = 160


def main() -> None:
    parser = argparse.ArgumentParser(prog="teamai")
    subcommands = parser.add_subparsers(dest="command", required=True)

    init_parser = subcommands.add_parser("init")
    init_parser.add_argument("path", nargs="?", default="team.yaml")

    validate_parser = subcommands.add_parser("validate")
    validate_parser.add_argument("teamfile")

    schema_parser = subcommands.add_parser("schema")
    schema_parser.add_argument("--output", type=Path)

    run_parser = subcommands.add_parser("run")
    run_parser.add_argument("teamfile")
    run_parser.add_argument("--input", required=True)
    run_parser.add_argument("--yes", action="store_true", help="auto-approve side effects")
    run_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    list_parser = subcommands.add_parser("list")
    list_parser.add_argument("--db", default=".teamai/runs.sqlite")
    list_parser.add_argument("--limit", type=int, default=DEFAULT_LIST_LIMIT)
    list_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    inspect_parser = subcommands.add_parser("inspect")
    inspect_parser.add_argument("run_id", nargs="?")
    inspect_parser.add_argument("--db", default=".teamai/runs.sqlite")
    inspect_parser.add_argument(
        "--latest",
        action="store_true",
        help="inspect the latest saved run",
    )
    inspect_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    args = parser.parse_args()
    if args.command == "init":
        _init(Path(args.path))
    elif args.command == "validate":
        _validate(Path(args.teamfile))
    elif args.command == "schema":
        _schema(args.output)
    elif args.command == "run":
        asyncio.run(
            _run(
                Path(args.teamfile),
                str(args.input),
                bool(args.yes),
                output_json=bool(args.json),
            )
        )
    elif args.command == "list":
        asyncio.run(_list_runs(Path(args.db), limit=int(args.limit), output_json=bool(args.json)))
    elif args.command == "inspect":
        run_id = UUID(str(args.run_id)) if args.run_id else None
        asyncio.run(
            _inspect(
                run_id,
                Path(args.db),
                latest=bool(args.latest),
                output_json=bool(args.json),
            )
        )


def _init(path: Path) -> None:
    if path.exists():
        raise SystemExit(f"{path} already exists")
    path.write_text(DEFAULT_TEAMFILE, encoding="utf-8")
    workspace = path.parent / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    print(f"created {path}")


def _validate(path: Path) -> None:
    try:
        config = validate_teamfile(path)
    except TeamfileValidationError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"valid Teamfile: {config.team.name}")


def _schema(output: Path | None = None) -> None:
    payload = json.dumps(generate_teamfile_schema(), ensure_ascii=True, indent=2)
    if output is None:
        print(payload)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f"{payload}\n", encoding="utf-8")
    print(f"wrote {output}")


async def _run(path: Path, goal: str, yes: bool, *, output_json: bool = False) -> None:
    approval = AutoApproveProvider() if yes else TerminalApprovalProvider()
    async with TeamRuntime.from_file(path, approval_provider=approval) as runtime:
        result = await runtime.run(goal=goal)
    if output_json:
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=True, indent=2))
        return
    print(f"run_id: {result.run_id}")
    print(f"status: {result.status.value}")
    print(result.final_output)


async def _list_runs(
    db: Path,
    *,
    limit: int = DEFAULT_LIST_LIMIT,
    output_json: bool = False,
) -> None:
    if limit < 1:
        raise SystemExit("--limit must be greater than 0")
    store = SQLiteStore(db)
    try:
        runs = await store.list_runs(limit=limit)
    finally:
        await store.aclose()
    if output_json:
        payload = [run.model_dump(mode="json") for run in runs]
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return
    if not runs:
        print("no runs")
        return
    for run in runs:
        saved_at = run.saved_at or "<unknown>"
        print(f"{saved_at} {run.status.value} {run.run_id} {run.goal}")


async def _inspect(
    run_id: UUID | None,
    db: Path,
    *,
    latest: bool = False,
    output_json: bool = False,
) -> None:
    if run_id is None and not latest:
        raise SystemExit("run_id is required unless --latest is used")
    store = SQLiteStore(db)
    try:
        if latest:
            result = await store.get_latest_run()
        else:
            result = await store.get_run(_require_run_id(run_id))
        if result is None:
            target = "latest run" if latest else str(run_id)
            raise SystemExit(f"run not found: {target}")
        events = await store.list_events(result.run_id)
        artifacts = await store.list_artifacts(result.run_id)
    finally:
        await store.aclose()
    if output_json:
        print(json.dumps(_inspect_payload(result, events, artifacts), ensure_ascii=True, indent=2))
        return
    print(f"run_id: {result.run_id}")
    print(f"status: {result.status.value}")
    print(f"model_calls: {_count_events(events, 'model.completed')}")
    print(f"tool_calls: {_count_events(events, 'tool.completed')}")
    print(f"prompt_tokens: {result.usage.prompt_tokens}")
    print(f"completion_tokens: {result.usage.completion_tokens}")
    print(f"total_tokens: {result.usage.total_tokens}")
    print(f"artifacts: {len(artifacts)}")
    if artifacts:
        print("artifact_summaries:")
        for artifact in artifacts:
            print(f"  {_format_artifact_summary(artifact)}")
    print("events:")
    for event in events:
        task = f" task={event.task_id}" if event.task_id else ""
        print(f"  {event.sequence:03d} {event.type} actor={event.actor}{task}")


def _count_events(events: Sequence[Event], event_type: str) -> int:
    return sum(1 for event in events if event.type == event_type)


def _require_run_id(run_id: UUID | None) -> UUID:
    if run_id is None:
        raise SystemExit("run_id is required unless --latest is used")
    return run_id


def _format_artifact_summary(artifact: Artifact) -> str:
    task_id = artifact.task_id or "<none>"
    summary = _compact_summary(artifact.summary)
    return f"{artifact.id} task={task_id} type={artifact.type} summary={summary}"


def _compact_summary(summary: str, limit: int = MAX_INSPECT_SUMMARY_CHARS) -> str:
    compact = " ".join(summary.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


def _inspect_payload(
    result: RunResult,
    events: Sequence[Event],
    artifacts: Sequence[Artifact],
) -> dict[str, object]:
    run_payload = result.model_dump(mode="json")
    return {
        "run": run_payload,
        "summary": {
            "run_id": run_payload["run_id"],
            "status": run_payload["status"],
            "model_calls": _count_events(events, "model.completed"),
            "tool_calls": _count_events(events, "tool.completed"),
            "artifact_count": len(artifacts),
            "usage": run_payload["usage"],
        },
        "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
        "events": [event.model_dump(mode="json") for event in events],
    }


if __name__ == "__main__":
    main()
