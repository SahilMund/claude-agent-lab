"""Retrieval: turn a query into ranked chunks.

Two strategies, both reading from the same Qdrant collection an `Indexer`
wrote to:

- `SemanticRetriever` — embed the query, rank by vector similarity. Good at
  matching *meaning* ("how do we split a class into chunks") even when the
  wording doesn't match the code at all.
- `HybridRetriever` — semantic search plus BM25 keyword search over the same
  chunks, combined by Reciprocal Rank Fusion (RRF). Good at also catching the
  case semantic search alone is weak at: an exact identifier or literal
  string match (`FakeEmbedder`, `AGENT_LAB_LOG_LEVEL`) that a paraphrase-y
  embedding model can underweight.

See docs/progress.md's architecture-decision log for why RRF specifically,
and for the current scale tradeoff (`HybridRetriever` re-scans the whole
collection for BM25 on every call — fine for this project's own codebase,
not for a large one).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from qdrant_client import QdrantClient
from rank_bm25 import BM25Plus

from claude_agent_lab.llm.base import Embedder
from claude_agent_lab.rag.fusion import rank_with_ties, reciprocal_rank_fusion
from claude_agent_lab.rag.store import DEFAULT_COLLECTION_NAME

_SCROLL_PAGE_SIZE = 256

# Identifier-shaped tokens only, lowercased. Plain str.split() would glue
# punctuation onto identifiers — "get_settings(config_path:".split() keeps
# that as one token, which never matches a query token "get_settings". This
# regex is deliberately simple (no sub-token splitting of "get_settings"
# into "get"/"settings", no handling of camelCase) — good enough to make
# exact-identifier matches work, which is the whole reason BM25 exists here
# alongside semantic search.
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass(frozen=True)
class RetrievedChunk:
    """A chunk plus how well it matched a query."""

    file_path: str
    kind: str
    symbol: str | None
    start_line: int
    end_line: int
    text: str
    score: float


def _payload_to_retrieved_chunk(payload: dict, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        file_path=payload["file_path"],
        kind=payload["kind"],
        symbol=payload["symbol"],
        start_line=payload["start_line"],
        end_line=payload["end_line"],
        text=payload["text"],
        score=score,
    )


def _scroll_all_points(client: QdrantClient, collection_name: str) -> list[tuple[str, dict]]:
    """Every (point id, payload) in a collection, paginated via scroll()."""
    points: list[tuple[str, dict]] = []
    offset = None
    while True:
        batch, offset = client.scroll(
            collection_name=collection_name,
            limit=_SCROLL_PAGE_SIZE,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        points.extend((point.id, point.payload) for point in batch)
        if offset is None:
            break
    return points


class SemanticRetriever:
    """Vector-similarity search only."""

    def __init__(
        self,
        *,
        client: QdrantClient,
        embedder: Embedder,
        collection_name: str = DEFAULT_COLLECTION_NAME,
    ) -> None:
        self._client = client
        self._embedder = embedder
        self._collection_name = collection_name

    def retrieve(self, query: str, *, top_k: int = 5) -> list[RetrievedChunk]:
        if not self._client.collection_exists(self._collection_name):
            return []

        [query_vector] = self._embedder.embed([query])
        result = self._client.query_points(
            collection_name=self._collection_name,
            query=query_vector,
            limit=top_k,
        )
        return [_payload_to_retrieved_chunk(point.payload, point.score) for point in result.points]


class HybridRetriever:
    """Semantic search + BM25 keyword search, merged by Reciprocal Rank Fusion.

    RRF combines two ranked lists using each item's *rank* rather than its
    raw score — sidestepping the fact that cosine similarity and a BM25
    score live on totally different, incomparable scales. An item's fused
    score is `sum(1 / (rrf_k + rank))` over every list it appears in; missing
    from a list contributes nothing from that list.
    """

    def __init__(
        self,
        *,
        client: QdrantClient,
        embedder: Embedder,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        rrf_k: int = 60,
    ) -> None:
        self._client = client
        self._embedder = embedder
        self._collection_name = collection_name
        self._rrf_k = rrf_k
        self._semantic = SemanticRetriever(
            client=client, embedder=embedder, collection_name=collection_name
        )

    def retrieve(self, query: str, *, top_k: int = 5) -> list[RetrievedChunk]:
        if not self._client.collection_exists(self._collection_name):
            return []

        all_points = _scroll_all_points(self._client, self._collection_name)
        if not all_points:
            return []

        semantic_results = self._semantic.retrieve(query, top_k=len(all_points))
        semantic_rank = rank_with_ties(
            [(self._point_key(result), result.score) for result in semantic_results]
        )
        bm25_rank = rank_with_ties(self._bm25_scores(query, all_points))

        fused = reciprocal_rank_fusion([semantic_rank, bm25_rank], k=self._rrf_k)
        payload_by_key = {self._payload_key(payload): payload for _point_id, payload in all_points}

        ranked_keys = sorted(fused, key=lambda key: fused[key], reverse=True)[:top_k]
        return [_payload_to_retrieved_chunk(payload_by_key[key], fused[key]) for key in ranked_keys]

    def _bm25_scores(
        self, query: str, all_points: list[tuple[str, dict]]
    ) -> list[tuple[str, float]]:
        # BM25Plus, not the classic BM25Okapi: Okapi's plain IDF term can
        # come out to exactly zero (or negative, floored to a small epsilon)
        # for a term that appears in about half the corpus — trivially
        # reproducible with only a couple of chunks indexed, which is exactly
        # this project's own corpus size for a while. BM25Plus adds a small
        # constant to the term-frequency component so a document containing
        # the query term always scores strictly higher than one that
        # doesn't, regardless of corpus size.
        corpus = [payload["text"] for _point_id, payload in all_points]
        bm25 = BM25Plus([_tokenize(text) for text in corpus])
        scores = bm25.get_scores(_tokenize(query))
        return [
            (self._payload_key(payload), score)
            for (_point_id, payload), score in zip(all_points, scores)
        ]

    @staticmethod
    def _payload_key(payload: dict) -> str:
        return f"{payload['file_path']}:{payload['start_line']}-{payload['end_line']}"

    @staticmethod
    def _point_key(result: RetrievedChunk) -> str:
        return f"{result.file_path}:{result.start_line}-{result.end_line}"
