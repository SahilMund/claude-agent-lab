"""Code-aware chunking: turn a source file into semantically meaningful chunks.

A "chunk" is the unit indexing and retrieval work with — the piece of text
that gets embedded and, later, comes back as a search result. Splitting on
syntax (function/class boundaries) instead of a fixed line window keeps each
chunk's meaning self-contained: a search for "how do we chunk a class" should
return one whole function, not the back half of one function glued to the
front half of the next.

Only Python is split syntax-aware for now. Everything else — and any Python
file that can't be read as text — falls back to fixed-size, overlapping line
windows. Adding another language means writing one more `Chunker` and adding
its extension to `get_chunker_for_path`; nothing else in this module changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

_PY_LANGUAGE = Language(tspython.language())

# Top-level node types that become their own chunk. A decorated function/class
# ("@decorator\ndef foo(): ...") parses as a wrapper node around the real
# function_definition/class_definition — see _definition_kind_and_symbol.
_PY_DEFINITION_TYPES = {"function_definition", "class_definition", "decorated_definition"}


@dataclass(frozen=True)
class Chunk:
    """One retrievable unit of source code."""

    file_path: str
    kind: str  # "function" | "class" | "module" | "lines" (fallback chunker)
    symbol: str | None  # function/class name; None for non-definition chunks
    start_line: int  # 1-indexed, inclusive
    end_line: int  # 1-indexed, inclusive
    text: str


class Chunker(Protocol):
    def chunk(self, file_path: str, source: str) -> list[Chunk]: ...


def _definition_kind_and_symbol(node: Node) -> tuple[str, str | None]:
    """Resolve a function_definition/class_definition/decorated_definition
    node to (chunk kind, symbol name)."""
    target = node
    if node.type == "decorated_definition":
        for child in node.children:
            if child.type in ("function_definition", "class_definition"):
                target = child
                break
    kind = "function" if target.type == "function_definition" else "class"
    name_node = target.child_by_field_name("name")
    symbol = name_node.text.decode("utf-8") if name_node else None
    return kind, symbol


class PythonChunker:
    """Splits a Python file at its top-level function/class boundaries.

    Everything at module level that isn't a function or class definition
    (imports, constants, bare statements, blank lines, comments) is grouped
    into "module"-kind chunks that fill the gaps between definitions.

    Tree-sitter is error-tolerant — a syntax error produces an ERROR node
    rather than raising — and this chunker never reads text out of the parsed
    tree anyway (only line numbers), so a malformed file degrades to coarser
    chunks instead of failing outright.
    """

    def __init__(self) -> None:
        self._parser = Parser(_PY_LANGUAGE)

    def chunk(self, file_path: str, source: str) -> list[Chunk]:
        tree = self._parser.parse(source.encode("utf-8"))
        source_lines = source.splitlines()
        chunks: list[Chunk] = []
        pending_start: int | None = None  # 0-indexed row of the first pending line

        def flush(end_row: int) -> None:
            nonlocal pending_start
            if pending_start is None:
                return
            start_line = pending_start + 1
            text = "\n".join(source_lines[start_line - 1 : end_row])
            if text.strip():
                chunks.append(
                    Chunk(
                        file_path=file_path,
                        kind="module",
                        symbol=None,
                        start_line=start_line,
                        end_line=end_row,
                        text=text,
                    )
                )
            pending_start = None

        for node in tree.root_node.children:
            if node.type in _PY_DEFINITION_TYPES:
                flush(node.start_point[0])
                kind, symbol = _definition_kind_and_symbol(node)
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                chunks.append(
                    Chunk(
                        file_path=file_path,
                        kind=kind,
                        symbol=symbol,
                        start_line=start_line,
                        end_line=end_line,
                        text="\n".join(source_lines[start_line - 1 : end_line]),
                    )
                )
            elif pending_start is None:
                pending_start = node.start_point[0]

        flush(len(source_lines))
        return chunks


class FallbackChunker:
    """Fixed-size, overlapping line-window chunker.

    Used for anything without a syntax-aware chunker — every non-Python file
    today. The overlap exists so a definition or explanation that happens to
    straddle a window boundary still appears whole in at least one chunk.
    """

    def __init__(self, *, window_lines: int, overlap_lines: int) -> None:
        if overlap_lines >= window_lines:
            raise ValueError("overlap_lines must be smaller than window_lines")
        self._window = window_lines
        self._overlap = overlap_lines

    def chunk(self, file_path: str, source: str) -> list[Chunk]:
        lines = source.splitlines()
        if not lines:
            return []

        chunks: list[Chunk] = []
        step = self._window - self._overlap
        start = 0
        while start < len(lines):
            end = min(start + self._window, len(lines))
            text = "\n".join(lines[start:end])
            if text.strip():
                chunks.append(
                    Chunk(
                        file_path=file_path,
                        kind="lines",
                        symbol=None,
                        start_line=start + 1,
                        end_line=end,
                        text=text,
                    )
                )
            if end == len(lines):
                break
            start += step

        return chunks


def get_chunker_for_path(
    path: str | Path, *, fallback_window_lines: int, fallback_overlap_lines: int
) -> Chunker:
    """Pick the right chunker for a file, based on its extension."""
    if Path(path).suffix == ".py":
        return PythonChunker()
    return FallbackChunker(window_lines=fallback_window_lines, overlap_lines=fallback_overlap_lines)


def chunk_file(
    path: str | Path, *, fallback_window_lines: int = 60, fallback_overlap_lines: int = 10
) -> list[Chunk]:
    """Read a file and split it into chunks with the appropriate chunker."""
    path = Path(path)
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path} is not valid UTF-8 text — can't chunk it") from exc

    chunker = get_chunker_for_path(
        path,
        fallback_window_lines=fallback_window_lines,
        fallback_overlap_lines=fallback_overlap_lines,
    )
    return chunker.chunk(str(path), source)
