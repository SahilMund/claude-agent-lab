from __future__ import annotations

from pathlib import Path

from claude_agent_lab.config import ChunkingConfig
from claude_agent_lab.llm.embedders import FakeEmbedder
from claude_agent_lab.rag.indexer import Indexer
from claude_agent_lab.rag.pipeline import build_ask_prompt, format_context, index_repo
from claude_agent_lab.rag.retriever import RetrievedChunk
from claude_agent_lab.rag.store import get_qdrant_client

CHUNKING = ChunkingConfig()


def _indexer(tmp_path: Path) -> Indexer:
    client = get_qdrant_client(tmp_path / "qdrant")
    return Indexer(client=client, embedder=FakeEmbedder(), collection_name="test")


def test_index_repo_chunks_and_indexes_python_files(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def foo():\n    return 1\n")
    (repo / "b.py").write_text("def bar():\n    return 2\n")

    indexer = _indexer(tmp_path)
    result = index_repo(repo, indexer=indexer, chunking=CHUNKING)

    assert result.files_indexed == 2
    assert result.files_skipped == 0
    assert result.chunks_indexed == 2


def test_index_repo_skips_ignored_directories(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "config").write_text("not real git config")
    (repo / "__pycache__").mkdir()
    (repo / "__pycache__" / "a.pyc").write_text("junk")
    (repo / "real.py").write_text("def real(): pass\n")

    indexer = _indexer(tmp_path)
    result = index_repo(repo, indexer=indexer, chunking=CHUNKING)

    assert result.files_indexed == 1
    assert result.files_skipped == 0


def test_index_repo_skips_unreadable_files_without_failing_the_whole_run(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "good.py").write_text("def good(): pass\n")
    (repo / "binary.dat").write_bytes(b"\xff\xfe\x00\x01binary junk")

    indexer = _indexer(tmp_path)
    result = index_repo(repo, indexer=indexer, chunking=CHUNKING)

    assert result.files_indexed == 1
    assert result.files_skipped == 1


def test_index_repo_indexes_non_python_text_files_via_fallback_chunker(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Title\n\nSome docs.\n")

    indexer = _indexer(tmp_path)
    result = index_repo(repo, indexer=indexer, chunking=CHUNKING)

    assert result.files_indexed == 1
    assert result.chunks_indexed >= 1


def test_index_repo_on_empty_directory_indexes_nothing(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    indexer = _indexer(tmp_path)
    result = index_repo(repo, indexer=indexer, chunking=CHUNKING)

    assert result == type(result)(files_indexed=0, files_skipped=0, chunks_indexed=0)


def _chunk(symbol: str | None, text: str, kind: str = "function") -> RetrievedChunk:
    return RetrievedChunk(
        file_path="example.py",
        kind=kind,
        symbol=symbol,
        start_line=1,
        end_line=2,
        text=text,
        score=0.5,
    )


def test_format_context_includes_file_location_and_symbol():
    chunk = _chunk("foo", "def foo(): pass")
    rendered = format_context([chunk])
    assert "example.py:1-2" in rendered
    assert "function foo" in rendered
    assert "def foo(): pass" in rendered


def test_format_context_handles_chunks_without_a_symbol():
    chunk = _chunk(None, "x = 1", kind="module")
    header_line = format_context([chunk]).split("\n")[0]
    assert "example.py:1-2" in header_line
    assert "(" not in header_line  # no "(module None)"-style suffix for symbol-less chunks


def test_format_context_on_empty_list_returns_empty_string():
    assert format_context([]) == ""


def test_build_ask_prompt_includes_context_and_question():
    chunk = _chunk("foo", "def foo(): pass")
    prompt = build_ask_prompt("what does foo do?", [chunk])
    assert "what does foo do?" in prompt
    assert "def foo(): pass" in prompt


def test_build_ask_prompt_tells_the_model_when_nothing_was_retrieved():
    prompt = build_ask_prompt("what does foo do?", [])
    assert "No relevant code context was found" in prompt
    assert "what does foo do?" in prompt
