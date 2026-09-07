from __future__ import annotations

from pathlib import Path

import pytest

from claude_agent_lab.agent.tools import (
    ToolError,
    default_tools,
    make_list_directory_tool,
    make_read_file_tool,
)


def test_read_file_returns_contents(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello world")
    tool = make_read_file_tool(tmp_path)

    assert tool.handler({"path": "a.txt"}) == "hello world"


def test_read_file_requires_a_path(tmp_path: Path):
    tool = make_read_file_tool(tmp_path)
    with pytest.raises(ToolError):
        tool.handler({})


def test_read_file_rejects_missing_file(tmp_path: Path):
    tool = make_read_file_tool(tmp_path)
    with pytest.raises(ToolError):
        tool.handler({"path": "nope.txt"})


def test_read_file_rejects_a_directory(tmp_path: Path):
    (tmp_path / "subdir").mkdir()
    tool = make_read_file_tool(tmp_path)
    with pytest.raises(ToolError):
        tool.handler({"path": "subdir"})


def test_read_file_truncates_very_large_files(tmp_path: Path):
    (tmp_path / "big.txt").write_text("x" * 300_000)
    tool = make_read_file_tool(tmp_path)

    result = tool.handler({"path": "big.txt"})

    assert len(result) < 300_000
    assert result.endswith("[truncated]")


def test_read_file_cannot_escape_the_root_via_dotdot(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("outside the root")
    tool = make_read_file_tool(root)

    with pytest.raises(ToolError):
        tool.handler({"path": "../secret.txt"})


def test_read_file_cannot_escape_the_root_via_absolute_path(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("outside the root")
    tool = make_read_file_tool(root)

    with pytest.raises(ToolError):
        tool.handler({"path": str(outside)})


def test_read_file_allows_an_absolute_path_inside_the_root(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    inside = root / "a.txt"
    inside.write_text("inside the root")
    tool = make_read_file_tool(root)

    assert tool.handler({"path": str(inside)}) == "inside the root"


def test_list_directory_lists_entries_with_trailing_slash_on_dirs(tmp_path: Path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "sub").mkdir()
    tool = make_list_directory_tool(tmp_path)

    result = tool.handler({})

    assert "a.py" in result
    assert "sub/" in result


def test_list_directory_defaults_to_the_root(tmp_path: Path):
    (tmp_path / "a.py").write_text("")
    tool = make_list_directory_tool(tmp_path)
    assert tool.handler({}) == tool.handler({"path": "."})


def test_list_directory_on_empty_directory(tmp_path: Path):
    tool = make_list_directory_tool(tmp_path)
    assert tool.handler({}) == "(empty directory)"


def test_list_directory_rejects_a_file_path(tmp_path: Path):
    (tmp_path / "a.txt").write_text("")
    tool = make_list_directory_tool(tmp_path)
    with pytest.raises(ToolError):
        tool.handler({"path": "a.txt"})


def test_list_directory_cannot_escape_the_root(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    tool = make_list_directory_tool(root)
    with pytest.raises(ToolError):
        tool.handler({"path": ".."})


def test_default_tools_returns_read_file_and_list_directory(tmp_path: Path):
    tools = default_tools(tmp_path)
    names = {tool.name for tool in tools}
    assert names == {"read_file", "list_directory"}


def test_tool_to_api_schema_shape(tmp_path: Path):
    tool = make_read_file_tool(tmp_path)
    schema = tool.to_api_schema()
    assert schema["name"] == "read_file"
    assert "input_schema" in schema
    assert "handler" not in schema  # never leaks the Python callable into the API payload
