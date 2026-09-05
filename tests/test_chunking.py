from __future__ import annotations

from pathlib import Path

from claude_agent_lab.rag.chunking import (
    FallbackChunker,
    PythonChunker,
    chunk_file,
    get_chunker_for_path,
)

PY_SOURCE = '''\
import os

TOP_LEVEL_CONSTANT = 1


def foo(x):
    return x + 1


@staticmethod
@another.decorator
def decorated(y):
    return y


class Bar:
    def method(self):
        pass


result = foo(1)
'''


def test_python_chunker_splits_on_definitions():
    chunks = PythonChunker().chunk("example.py", PY_SOURCE)
    kinds = [(c.kind, c.symbol) for c in chunks]

    assert kinds == [
        ("module", None),  # import + constant
        ("function", "foo"),
        ("function", "decorated"),  # decorators included, symbol resolved through the wrapper
        ("class", "Bar"),
        ("module", None),  # trailing `result = foo(1)`
    ]


def test_python_chunker_preserves_exact_source_text():
    chunks = PythonChunker().chunk("example.py", PY_SOURCE)
    foo_chunk = next(c for c in chunks if c.symbol == "foo")

    assert foo_chunk.text == "def foo(x):\n    return x + 1"
    assert foo_chunk.start_line == 6
    assert foo_chunk.end_line == 7


def test_python_chunker_handles_decorators_as_part_of_the_chunk():
    chunks = PythonChunker().chunk("example.py", PY_SOURCE)
    decorated_chunk = next(c for c in chunks if c.symbol == "decorated")

    assert decorated_chunk.text.startswith("@staticmethod")
    assert "def decorated(y):" in decorated_chunk.text


def test_python_chunker_on_empty_file_returns_no_chunks():
    assert PythonChunker().chunk("empty.py", "") == []


def test_python_chunker_degrades_gracefully_on_syntax_errors():
    # Missing closing paren — tree-sitter won't raise, it produces an ERROR
    # node; chunking should still return something rather than crash.
    broken = "def foo(x:\n    return x\n"
    chunks = PythonChunker().chunk("broken.py", broken)
    assert chunks  # doesn't crash, produces at least a module-level chunk


def test_fallback_chunker_splits_into_overlapping_windows():
    lines = [f"line {i}" for i in range(1, 21)]  # 20 lines
    source = "\n".join(lines)
    chunker = FallbackChunker(window_lines=10, overlap_lines=2)

    chunks = chunker.chunk("notes.txt", source)

    assert [c.start_line for c in chunks] == [1, 9, 17]
    assert [c.end_line for c in chunks] == [10, 18, 20]
    assert chunks[0].kind == "lines"
    assert chunks[0].symbol is None


def test_fallback_chunker_rejects_overlap_not_smaller_than_window():
    try:
        FallbackChunker(window_lines=10, overlap_lines=10)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for overlap_lines >= window_lines")


def test_fallback_chunker_on_empty_source_returns_no_chunks():
    assert FallbackChunker(window_lines=10, overlap_lines=2).chunk("empty.txt", "") == []


def test_get_chunker_for_path_dispatches_on_extension():
    assert isinstance(
        get_chunker_for_path("a.py", fallback_window_lines=10, fallback_overlap_lines=2),
        PythonChunker,
    )
    assert isinstance(
        get_chunker_for_path("a.md", fallback_window_lines=10, fallback_overlap_lines=2),
        FallbackChunker,
    )


def test_chunk_file_reads_and_chunks_a_real_file(tmp_path: Path):
    file_path = tmp_path / "sample.py"
    file_path.write_text(PY_SOURCE, encoding="utf-8")

    chunks = chunk_file(file_path)

    assert [c.symbol for c in chunks if c.symbol] == ["foo", "decorated", "Bar"]
    assert all(c.file_path == str(file_path) for c in chunks)
