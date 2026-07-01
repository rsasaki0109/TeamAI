import asyncio
from pathlib import Path

import pytest

from teamai.core.errors import ToolExecutionError
from teamai.tools.base import Tool
from teamai.tools.builtin.filesystem import build_filesystem_tools


def _tool_by_name(root: Path, name: str) -> Tool:
    tools = build_filesystem_tools(root=root, max_read_bytes=1024, max_write_bytes=1024)
    return {tool.spec.name: tool for tool in tools}[name]


def test_filesystem_write_and_read(tmp_path: Path) -> None:
    write_tool = _tool_by_name(tmp_path, "filesystem.write")
    read_tool = _tool_by_name(tmp_path, "filesystem.read")

    asyncio.run(write_tool.execute({"path": "out.txt", "content": "hello"}))
    result = asyncio.run(read_tool.execute({"path": "out.txt"}))

    assert result.output["content"] == "hello"


def test_filesystem_rejects_path_escape(tmp_path: Path) -> None:
    read_tool = _tool_by_name(tmp_path, "filesystem.read")

    with pytest.raises(ToolExecutionError):
        asyncio.run(read_tool.execute({"path": "../outside.txt"}))


def test_filesystem_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}_outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    link = tmp_path / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation is not available: {exc}")

    read_tool = _tool_by_name(tmp_path, "filesystem.read")

    with pytest.raises(ToolExecutionError):
        asyncio.run(read_tool.execute({"path": "link/secret.txt"}))
