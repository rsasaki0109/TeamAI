from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from teamai.core.domain import ToolResult, ToolSpec


class Tool(Protocol):
    @property
    def spec(self) -> ToolSpec:
        raise NotImplementedError

    async def execute(self, arguments: Mapping[str, object]) -> ToolResult:
        raise NotImplementedError


class ToolRegistry:
    def __init__(self, tools: Sequence[Tool] = ()) -> None:
        self._tools = {tool.spec.name: tool for tool in tools}

    def register(self, tool: Tool) -> None:
        self._tools[tool.spec.name] = tool

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools)
