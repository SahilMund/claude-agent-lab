"""Filesystem tools the agent can call.

Read-only, and sandboxed to a single root directory — no tool here can read
a path outside the project root it was built with, regardless of what the
model asks for. Shell/terminal execution (the other tool category the PRD's
Phase 3 row calls for) is deliberately not in this slice — see
docs/progress.md's architecture-decision log for why that's staged
separately rather than shipped alongside filesystem tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

MAX_READ_CHARS = 200_000  # cap so one huge file can't blow the context window


class ToolError(Exception):
    """Raised by a tool's handler; the orchestrator turns this into an
    `is_error` tool_result instead of letting it crash the agent loop."""


@dataclass(frozen=True)
class Tool:
    """A tool the model can call: its API-facing schema, plus the Python
    function that actually runs it."""

    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], str]

    def to_api_schema(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema}


def _resolve_within_root(root: Path, path_str: str) -> Path:
    """Resolve `path_str` (relative or absolute) against `root`, and reject
    it outright if it resolves to anywhere outside `root` — including via
    `..` segments or a symlink. This is the actual security boundary; every
    tool in this module must route its path argument through here before
    touching the filesystem.
    """
    root = root.resolve()
    candidate = Path(path_str)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ToolError(f"path {path_str!r} is outside the project root") from exc
    return resolved


def make_read_file_tool(root: Path) -> Tool:
    def handler(tool_input: dict) -> str:
        path_str = tool_input.get("path")
        if not path_str:
            raise ToolError("'path' is required")
        path = _resolve_within_root(root, path_str)
        if not path.exists():
            raise ToolError(f"no such file: {path_str}")
        if not path.is_file():
            raise ToolError(f"not a file: {path_str}")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError(f"{path_str} is not valid UTF-8 text") from exc
        if len(text) > MAX_READ_CHARS:
            text = text[:MAX_READ_CHARS] + "\n... [truncated]"
        return text

    return Tool(
        name="read_file",
        description="Read a text file's contents. `path` is relative to the project root.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to the project root."}
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=handler,
    )


def make_list_directory_tool(root: Path) -> Tool:
    def handler(tool_input: dict) -> str:
        path_str = tool_input.get("path", ".")
        path = _resolve_within_root(root, path_str)
        if not path.exists():
            raise ToolError(f"no such directory: {path_str}")
        if not path.is_dir():
            raise ToolError(f"not a directory: {path_str}")
        entries = sorted(entry.name + ("/" if entry.is_dir() else "") for entry in path.iterdir())
        return "\n".join(entries) if entries else "(empty directory)"

    return Tool(
        name="list_directory",
        description=(
            "List the files and subdirectories directly inside a directory "
            "(non-recursive). `path` is relative to the project root; "
            "defaults to the project root itself."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path relative to the project root. Defaults to the root.",
                }
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
    )


def default_tools(root: Path) -> list[Tool]:
    """The tool set the agent factory wires up by default."""
    return [make_read_file_tool(root), make_list_directory_tool(root)]
