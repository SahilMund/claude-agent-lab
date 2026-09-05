"""Shared vector store client construction.

Qdrant's local (embedded, file-based) mode locks its storage directory to a
single open client per process — a second `QdrantClient` pointed at the same
path raises `RuntimeError: Storage folder ... is already accessed by another
instance`. That's not a hypothetical: it reproduces immediately if the
indexer and a retriever each open their own client on the same path in the
same process. So there is exactly one place a `QdrantClient` gets
constructed (`get_qdrant_client`), and `Indexer`/`SemanticRetriever`/
`HybridRetriever` all take a client instance rather than a path — see
docs/progress.md's architecture-decision log for the reasoning.
"""

from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient

DEFAULT_COLLECTION_NAME = "claude_agent_lab"
DEFAULT_STORE_PATH = ".agent_lab/qdrant"


def get_qdrant_client(path: str | Path = DEFAULT_STORE_PATH) -> QdrantClient:
    """Open a local, file-based Qdrant client.

    Swapping to a real Qdrant server later (Docker, cloud) only means
    constructing this differently — `QdrantClient(url=...)` instead of
    `QdrantClient(path=...)` — everything downstream that takes a client
    doesn't change.
    """
    return QdrantClient(path=str(path))
