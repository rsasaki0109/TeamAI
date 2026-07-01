from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from teamai.core.domain import SideEffect, ToolResult, ToolSpec
from teamai.core.errors import ToolExecutionError
from teamai.tools.base import Tool


class _FilesystemTool(Tool):
    def __init__(
        self,
        *,
        root: Path,
        spec: ToolSpec,
        max_read_bytes: int,
        max_write_bytes: int,
    ) -> None:
        self._root = root.resolve()
        self._spec = spec
        self._max_read_bytes = max_read_bytes
        self._max_write_bytes = max_write_bytes

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def _resolve(self, raw_path: object) -> Path:
        if not isinstance(raw_path, str) or not raw_path:
            raise ToolExecutionError("path must be a non-empty string")
        target = (self._root / raw_path).resolve()
        root_text = str(self._root)
        target_text = str(target)
        if target != self._root and not target_text.startswith(root_text + os.sep):
            raise ToolExecutionError("path escapes workspace root")
        return target

    async def execute(self, arguments: Mapping[str, object]) -> ToolResult:
        raise NotImplementedError


class FilesystemListTool(_FilesystemTool):
    def __init__(self, root: Path, max_read_bytes: int, max_write_bytes: int) -> None:
        super().__init__(
            root=root,
            max_read_bytes=max_read_bytes,
            max_write_bytes=max_write_bytes,
            spec=ToolSpec(
                name="filesystem.list",
                description="List files under a workspace-relative directory.",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                output_schema={"type": "object"},
                side_effect=SideEffect.READ,
                idempotent=True,
            ),
        )

    async def execute(self, arguments: Mapping[str, object]) -> ToolResult:
        target = self._resolve(arguments.get("path", "."))
        if not target.exists():
            raise ToolExecutionError("path does not exist")
        if not target.is_dir():
            raise ToolExecutionError("path is not a directory")
        entries = [
            {"name": child.name, "type": "directory" if child.is_dir() else "file"}
            for child in sorted(target.iterdir(), key=lambda path: path.name)
        ]
        return ToolResult(output={"entries": entries})


class FilesystemReadTool(_FilesystemTool):
    def __init__(self, root: Path, max_read_bytes: int, max_write_bytes: int) -> None:
        super().__init__(
            root=root,
            max_read_bytes=max_read_bytes,
            max_write_bytes=max_write_bytes,
            spec=ToolSpec(
                name="filesystem.read",
                description="Read a UTF-8 file from the workspace.",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                output_schema={"type": "object"},
                side_effect=SideEffect.READ,
                idempotent=True,
            ),
        )

    async def execute(self, arguments: Mapping[str, object]) -> ToolResult:
        target = self._resolve(arguments.get("path"))
        if not target.is_file():
            raise ToolExecutionError("path is not a file")
        size = target.stat().st_size
        if size > self._max_read_bytes:
            raise ToolExecutionError("file exceeds max_read_bytes")
        return ToolResult(output={"content": target.read_text(encoding="utf-8", errors="replace")})


class FilesystemWriteTool(_FilesystemTool):
    def __init__(self, root: Path, max_read_bytes: int, max_write_bytes: int) -> None:
        super().__init__(
            root=root,
            max_read_bytes=max_read_bytes,
            max_write_bytes=max_write_bytes,
            spec=ToolSpec(
                name="filesystem.write",
                description="Write a UTF-8 file inside the workspace.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                },
                output_schema={"type": "object"},
                side_effect=SideEffect.WRITE,
                idempotent=False,
            ),
        )

    async def execute(self, arguments: Mapping[str, object]) -> ToolResult:
        target = self._resolve(arguments.get("path"))
        raw_content = arguments.get("content")
        if not isinstance(raw_content, str):
            raise ToolExecutionError("content must be a string")
        encoded = raw_content.encode("utf-8")
        if len(encoded) > self._max_write_bytes:
            raise ToolExecutionError("content exceeds max_write_bytes")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(raw_content, encoding="utf-8")
        return ToolResult(
            output={"path": str(target.relative_to(self._root)), "bytes": len(encoded)}
        )


def build_filesystem_tools(
    *,
    root: Path,
    max_read_bytes: int,
    max_write_bytes: int,
) -> list[Tool]:
    root.mkdir(parents=True, exist_ok=True)
    return [
        FilesystemListTool(root, max_read_bytes, max_write_bytes),
        FilesystemReadTool(root, max_read_bytes, max_write_bytes),
        FilesystemWriteTool(root, max_read_bytes, max_write_bytes),
    ]
