"""Indexing: embed chunks and store them in a vector database.

Takes the output of `rag/chunking.py`, turns each chunk's text into a vector
via the `Embedder` factory built in Phase 1, and upserts it into a Qdrant
collection — see `rag/store.py` for why the `QdrantClient` is constructed
once and passed in rather than built here.
"""

from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from claude_agent_lab.llm.base import Embedder
from claude_agent_lab.rag.chunking import Chunk
from claude_agent_lab.rag.store import DEFAULT_COLLECTION_NAME

# Fixed, arbitrary namespace for deriving a chunk's point ID deterministically
# from its identity (file + line range) rather than assigning one at random.
# Re-indexing the same chunk (e.g. after a small edit elsewhere in the file
# shifts nothing) upserts the same point instead of creating a duplicate.
_POINT_ID_NAMESPACE = uuid.UUID("6f6f6f0e-2f0e-4f0e-8f0e-0e0e0e0e0e0e")


def chunk_point_id(chunk: Chunk) -> str:
    """Deterministic Qdrant point ID for a chunk, derived from its identity."""
    key = f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}"
    return str(uuid.uuid5(_POINT_ID_NAMESPACE, key))


def chunk_to_payload(chunk: Chunk) -> dict:
    """The metadata stored alongside a chunk's vector — everything a
    retriever needs to reconstruct a `RetrievedChunk` without re-reading the
    source file."""
    return {
        "file_path": chunk.file_path,
        "kind": chunk.kind,
        "symbol": chunk.symbol,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "text": chunk.text,
    }


class Indexer:
    """Embeds chunks and upserts them into a Qdrant collection."""

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

    def _ensure_collection(self, vector_size: int) -> None:
        if self._client.collection_exists(self._collection_name):
            return
        self._client.create_collection(
            collection_name=self._collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    def index_chunks(self, chunks: list[Chunk]) -> int:
        """Embed and upsert chunks. Returns how many were indexed (0 for
        empty input — the embedder is never called with an empty batch)."""
        if not chunks:
            return 0

        vectors = self._embedder.embed([chunk.text for chunk in chunks])
        self._ensure_collection(vector_size=len(vectors[0]))

        points = [
            PointStruct(id=chunk_point_id(chunk), vector=vector, payload=chunk_to_payload(chunk))
            for chunk, vector in zip(chunks, vectors)
        ]
        self._client.upsert(collection_name=self._collection_name, points=points)
        return len(points)
