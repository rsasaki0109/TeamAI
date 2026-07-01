from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from teamai.core.domain import Artifact, RunResult, RunSummary
from teamai.core.events import Event


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self._connection.executescript(
            """
            create table if not exists runs (
                run_id text primary key,
                status text not null,
                goal text not null,
                final_output text not null,
                payload text not null,
                saved_at text not null default ''
            );

            create table if not exists events (
                run_id text not null,
                sequence integer not null,
                event_id text not null unique,
                type text not null,
                actor text not null,
                task_id text,
                payload text not null,
                occurred_at text not null,
                primary key (run_id, sequence)
            );

            create table if not exists artifacts (
                artifact_id text primary key,
                run_id text not null,
                task_id text,
                type text not null,
                summary text not null,
                content text not null,
                payload text not null,
                created_at text not null
            );
            """
        )
        self._ensure_column("runs", "saved_at", "text not null default ''")
        self._connection.commit()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        rows = self._connection.execute(f"pragma table_info({table})").fetchall()
        if column in {str(row["name"]) for row in rows}:
            return
        self._connection.execute(f"alter table {table} add column {column} {definition}")

    async def append_event(self, event: Event) -> None:
        self._connection.execute(
            """
            insert into events (
                run_id, sequence, event_id, type, actor, task_id, payload, occurred_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(event.run_id),
                event.sequence,
                str(event.id),
                event.type,
                event.actor,
                event.task_id,
                json.dumps(event.payload, ensure_ascii=True),
                event.occurred_at.isoformat(),
            ),
        )
        self._connection.commit()

    async def list_events(self, run_id: UUID) -> list[Event]:
        rows = self._connection.execute(
            "select * from events where run_id = ? order by sequence",
            (str(run_id),),
        ).fetchall()
        return [
            Event(
                id=UUID(row["event_id"]),
                run_id=UUID(row["run_id"]),
                sequence=int(row["sequence"]),
                type=str(row["type"]),
                actor=str(row["actor"]),
                task_id=row["task_id"],
                occurred_at=row["occurred_at"],
                payload=json.loads(str(row["payload"])),
            )
            for row in rows
        ]

    async def save_artifact(self, artifact: Artifact) -> None:
        self._connection.execute(
            """
            insert or replace into artifacts (
                artifact_id, run_id, task_id, type, summary, content, payload, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(artifact.id),
                str(artifact.run_id),
                artifact.task_id,
                artifact.type,
                artifact.summary,
                artifact.content,
                artifact.model_dump_json(),
                artifact.created_at.isoformat(),
            ),
        )
        self._connection.commit()

    async def list_artifacts(self, run_id: UUID) -> list[Artifact]:
        rows = self._connection.execute(
            "select payload from artifacts where run_id = ? order by created_at",
            (str(run_id),),
        ).fetchall()
        return [Artifact.model_validate_json(str(row["payload"])) for row in rows]

    async def save_run(self, result: RunResult, goal: str) -> None:
        self._connection.execute(
            """
            insert or replace into runs (run_id, status, goal, final_output, payload, saved_at)
            values (?, ?, ?, ?, ?, ?)
            """,
            (
                str(result.run_id),
                result.status.value,
                goal,
                result.final_output,
                result.model_dump_json(),
                datetime.now(UTC).isoformat(),
            ),
        )
        self._connection.commit()

    async def get_run(self, run_id: UUID) -> RunResult | None:
        row = self._connection.execute(
            "select payload from runs where run_id = ?",
            (str(run_id),),
        ).fetchone()
        if row is None:
            return None
        return RunResult.model_validate_json(str(row["payload"]))

    async def get_latest_run(self) -> RunResult | None:
        row = self._connection.execute(
            "select payload from runs order by saved_at desc, rowid desc limit 1"
        ).fetchone()
        if row is None:
            return None
        return RunResult.model_validate_json(str(row["payload"]))

    async def list_runs(self, *, limit: int = 20) -> list[RunSummary]:
        rows = self._connection.execute(
            """
            select run_id, status, goal, saved_at
            from runs
            order by saved_at desc, rowid desc
            limit ?
            """,
            (limit,),
        ).fetchall()
        return [
            RunSummary(
                run_id=UUID(row["run_id"]),
                status=row["status"],
                goal=str(row["goal"]),
                saved_at=str(row["saved_at"]),
            )
            for row in rows
        ]

    async def aclose(self) -> None:
        self._connection.close()
