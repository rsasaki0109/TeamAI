from __future__ import annotations

from pathlib import Path
from types import TracebackType

from teamai.conductor import Conductor
from teamai.config.loader import load_team_config
from teamai.config.models import TeamConfig
from teamai.core.domain import RunResult
from teamai.core.protocols import ApprovalProvider, ModelClient
from teamai.human.auto_approve import AutoApproveProvider
from teamai.human.reject import RejectApprovalProvider
from teamai.persistence.sqlite import SQLiteStore
from teamai.providers.registry import build_model_clients
from teamai.tools.base import ToolRegistry
from teamai.tools.builtin.filesystem import build_filesystem_tools


class TeamRuntime:
    def __init__(
        self,
        *,
        config: TeamConfig,
        base_dir: Path,
        approval_provider: ApprovalProvider | None = None,
        auto_approve: bool = False,
    ) -> None:
        if approval_provider is not None and auto_approve:
            raise ValueError("approval_provider and auto_approve cannot both be set")
        self.config = config
        self.base_dir = base_dir
        if approval_provider is not None:
            self._approval_provider = approval_provider
        elif auto_approve:
            self._approval_provider = AutoApproveProvider()
        else:
            self._approval_provider = RejectApprovalProvider()
        self._model_clients: dict[str, ModelClient] = {}
        self._store: SQLiteStore | None = None
        self._tool_registry: ToolRegistry | None = None

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        approval_provider: ApprovalProvider | None = None,
        auto_approve: bool = False,
    ) -> TeamRuntime:
        teamfile_path = Path(path)
        return cls(
            config=load_team_config(teamfile_path),
            base_dir=teamfile_path.resolve().parent,
            approval_provider=approval_provider,
            auto_approve=auto_approve,
        )

    async def __aenter__(self) -> TeamRuntime:
        self._model_clients = build_model_clients(self.config)
        sqlite_path = self.config.persistence.resolve_sqlite_path(self.base_dir)
        self._store = SQLiteStore(sqlite_path)
        workspace = self.config.security.resolve_workspace(self.base_dir)
        self._tool_registry = ToolRegistry(
            build_filesystem_tools(
                root=workspace,
                max_read_bytes=self.config.security.max_read_bytes,
                max_write_bytes=self.config.security.max_write_bytes,
            )
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        for client in self._model_clients.values():
            await client.aclose()
        if self._store is not None:
            await self._store.aclose()

    async def run(self, *, goal: str) -> RunResult:
        if self._store is None or self._tool_registry is None:
            raise RuntimeError("TeamRuntime must be used as an async context manager")
        conductor = Conductor(
            config=self.config,
            model_clients=self._model_clients,
            store=self._store,
            tool_registry=self._tool_registry,
            approval_provider=self._approval_provider,
        )
        return await conductor.run(goal)
