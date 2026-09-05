from __future__ import annotations

from pathlib import Path

from claude_agent_lab.rag.chunking import Chunk
from claude_agent_lab.rag.indexer import Indexer
from claude_agent_lab.rag.retriever import HybridRetriever, SemanticRetriever, _tokenize
from claude_agent_lab.rag.store import get_qdrant_client

COLLECTION = "test_collection"


class StubEmbedder:
    """Deterministic test double: maps exact known text to a fixed vector,
    with a default vector for anything unrecognized (typically the query)."""

    def __init__(self, vectors: dict[str, list[float]], default: list[float]) -> None:
        self._vectors = vectors
        self._default = default

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors.get(text, self._default) for text in texts]


def _chunk(symbol: str, text: str, start: int) -> Chunk:
    # start is required (no default) precisely so a test can't accidentally
    # give two chunks the same identity — chunk_point_id is derived from
    # (file_path, start_line, end_line), and the indexer treats a repeated
    # identity as an update to the same point, not a second point.
    return Chunk(
        file_path="example.py",
        kind="function",
        symbol=symbol,
        start_line=start,
        end_line=start + 1,
        text=text,
    )


def test_semantic_retriever_on_missing_collection_returns_empty(tmp_path: Path):
    client = get_qdrant_client(tmp_path / "qdrant")
    retriever = SemanticRetriever(
        client=client, embedder=StubEmbedder({}, default=[0.0]), collection_name=COLLECTION
    )
    assert retriever.retrieve("anything") == []


def test_semantic_retriever_ranks_by_vector_similarity(tmp_path: Path):
    chunk_a = _chunk("alpha", "def alpha(): return 1", start=1)
    chunk_b = _chunk("beta", "def beta(): return 2", start=10)
    embedder = StubEmbedder(
        vectors={chunk_a.text: [1.0, 0.0], chunk_b.text: [0.0, 1.0]},
        default=[1.0, 0.0],  # the query embeds close to chunk_a
    )
    client = get_qdrant_client(tmp_path / "qdrant")
    Indexer(client=client, embedder=embedder, collection_name=COLLECTION).index_chunks(
        [chunk_a, chunk_b]
    )

    retriever = SemanticRetriever(client=client, embedder=embedder, collection_name=COLLECTION)
    results = retriever.retrieve("find alpha", top_k=1)

    assert results[0].symbol == "alpha"


def test_hybrid_retriever_improves_an_exact_identifier_matchs_rank_over_semantic_alone(
    tmp_path: Path,
):
    # Three chunks, ranked distinctly (no ties) on semantic similarity:
    # "filler" is the best semantic match, "decoy" second, "needle_token"
    # dead last — but only needle_token's text contains the literal
    # identifier the query names, so it alone gets a BM25 match.
    #
    # RRF only uses rank, not raw score, so it can't be fooled by *how much*
    # better filler's cosine similarity is — but a single rank-1 semantic
    # match is still a strong signal, and this project's default rrf_k=60
    # (tuned for large result sets, see rag/fusion.py) barely discounts
    # rank 3 vs rank 1 at this tiny scale. So the fair, general claim is
    # "needle_token's rank improves under hybrid" — not "hybrid always wins
    # outright regardless of how strong the competing semantic match is."
    # See docs/progress.md for the worked-out numbers behind this.
    filler = _chunk("filler", "def filler(): return 1", start=1)
    decoy = _chunk("decoy", "def decoy(): return 2", start=10)
    needle = _chunk("needle_token", "def needle_token(): return 3", start=20)
    embedder = StubEmbedder(
        vectors={
            filler.text: [1.0, 0.0, 0.0],
            decoy.text: [0.8, 0.6, 0.0],
            needle.text: [0.0, 0.0, 1.0],
        },
        default=[1.0, 0.0, 0.0],  # query embeds exactly like "filler"
    )
    client = get_qdrant_client(tmp_path / "qdrant")
    Indexer(client=client, embedder=embedder, collection_name=COLLECTION).index_chunks(
        [filler, decoy, needle]
    )

    query = "needle_token"
    semantic_order = [
        r.symbol
        for r in SemanticRetriever(
            client=client, embedder=embedder, collection_name=COLLECTION
        ).retrieve(query, top_k=3)
    ]
    hybrid_order = [
        r.symbol
        for r in HybridRetriever(
            client=client, embedder=embedder, collection_name=COLLECTION
        ).retrieve(query, top_k=3)
    ]

    assert semantic_order == ["filler", "decoy", "needle_token"]  # semantic alone: dead last
    assert hybrid_order.index("needle_token") < semantic_order.index("needle_token")


def test_hybrid_retriever_on_missing_collection_returns_empty(tmp_path: Path):
    client = get_qdrant_client(tmp_path / "qdrant")
    retriever = HybridRetriever(
        client=client, embedder=StubEmbedder({}, default=[0.0]), collection_name=COLLECTION
    )
    assert retriever.retrieve("anything") == []


def test_tokenizer_splits_identifiers_glued_to_punctuation():
    # Regression test for the whitespace-tokenization bug: naive
    # text.split() would keep "needle_token(x," as one token that never
    # matches a query token "needle_token". This bypasses the whole
    # retrieve() pipeline on purpose — it's testing the tokenizer in
    # isolation, not RRF's ranking behavior (that's tests/test_fusion.py
    # and the scenario above).
    tokens = _tokenize("def needle_token(x, y):\n    return x + y")
    assert "needle_token" in tokens
    assert "needle_token(x," not in tokens


def test_tokenizer_lowercases():
    assert _tokenize("DEF Needle_Token") == ["def", "needle_token"]
