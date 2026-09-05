from __future__ import annotations

from pathlib import Path

from claude_agent_lab.llm.embedders import FakeEmbedder
from claude_agent_lab.rag.chunking import Chunk
from claude_agent_lab.rag.indexer import Indexer, chunk_point_id
from claude_agent_lab.rag.store import get_qdrant_client

COLLECTION = "test_collection"


def _chunk(symbol: str, start: int = 1, end: int = 2, text: str | None = None) -> Chunk:
    return Chunk(
        file_path="example.py",
        kind="function",
        symbol=symbol,
        start_line=start,
        end_line=end,
        text=text or f"def {symbol}(): pass",
    )


def _indexer(tmp_path: Path) -> Indexer:
    client = get_qdrant_client(tmp_path / "qdrant")
    return Indexer(client=client, embedder=FakeEmbedder(), collection_name=COLLECTION)


def test_indexing_empty_list_returns_zero_and_creates_nothing(tmp_path: Path):
    indexer = _indexer(tmp_path)
    assert indexer.index_chunks([]) == 0
    assert not indexer._client.collection_exists(COLLECTION)


def test_indexing_chunks_creates_collection_and_upserts_points(tmp_path: Path):
    indexer = _indexer(tmp_path)
    count = indexer.index_chunks([_chunk("foo", start=1, end=2), _chunk("bar", start=5, end=6)])

    assert count == 2
    assert indexer._client.count(COLLECTION).count == 2


def test_reindexing_the_same_chunk_upserts_rather_than_duplicates(tmp_path: Path):
    indexer = _indexer(tmp_path)
    chunk = _chunk("foo")

    indexer.index_chunks([chunk])
    indexer.index_chunks([chunk])  # same file/line-range identity, indexed twice

    assert indexer._client.count(COLLECTION).count == 1


def test_chunk_point_id_is_deterministic():
    chunk = _chunk("foo", start=10, end=20)
    assert chunk_point_id(chunk) == chunk_point_id(chunk)


def test_chunk_point_id_differs_for_different_identity():
    a = _chunk("foo", start=1, end=2)
    b = _chunk("foo", start=3, end=4)  # same symbol, different location
    assert chunk_point_id(a) != chunk_point_id(b)


def test_chunk_point_id_is_stable_even_if_chunk_text_changes():
    # Identity is (file_path, start_line, end_line) — a chunk whose text
    # changed slightly (e.g. a docstring edit) but whose location didn't
    # should still map to the same point, so re-indexing updates it in
    # place instead of leaving a stale duplicate behind.
    a = _chunk("foo", start=1, end=2, text="def foo(): pass")
    b = _chunk("foo", start=1, end=2, text="def foo(): return None")
    assert chunk_point_id(a) == chunk_point_id(b)
