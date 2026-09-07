"""Long-term memory: durable facts/preferences that persist across sessions.

Unlike short_term.py (per-session message history, keyed by thread_id — wiped
clean whenever a new session starts) this store is not scoped to any one
conversation: a fact saved in one session is retrievable in every future one.

There is no equivalent of this in source/capstone_project/educosys_claude/
memory/ — it only has session.py and short_term.py. This is new design, not
a port, per CLAUDE.md's rule that work absent from source entirely is where
independent design belongs (same category as the now-removed Phase 8 dashboard).

Storage: a Qdrant collection separate from the code index collection
(config's qdrant.collection_name), using the same embedder as the rest of
the app (llm/factory.py's get_embedder()) so facts are retrievable by
semantic similarity — "what does the user prefer for error handling?" should
match a stored fact like "user prefers early returns over nested if/else"
without needing an exact string match.
"""
import os
import uuid
from datetime import datetime, timezone

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from claude_agent_lab.config import config
from claude_agent_lab.llm.factory import get_embedder
from claude_agent_lab.observability.logger import get_logger


logger = get_logger(__name__)


def _collection_name() -> str:
    return config.get("long_term_memory", {}).get("collection_name", "claude_agent_lab_memory")


def _connection() -> tuple[str | None, str | None]:
    # `or None`, not a bare os.getenv() — same QdrantClient HTTPS-inference
    # bug as the code index (see context/{indexers,retrievers}/*_qdrant.py):
    # api_key="" (a blank .env line) makes the client assume HTTPS against a
    # local, unauthenticated Qdrant instance and fail with a TLS error.
    return os.getenv("QDRANT_URL") or None, os.getenv("QDRANT_API_KEY") or None


def _store() -> QdrantVectorStore:
    """Return a QdrantVectorStore over the long-term-memory collection,
    creating the collection on first use if it doesn't exist yet."""
    url, api_key = _connection()
    client = QdrantClient(url=url, api_key=api_key)

    name = _collection_name()
    existing = [c.name for c in client.get_collections().collections]
    if name not in existing:
        dims = config["embeddings"]["dims"]
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dims, distance=Distance.COSINE),
        )
        logger.info(f"Created long-term memory collection: {name} (dims={dims})")

    return QdrantVectorStore(client=client, collection_name=name, embedding=get_embedder())


def remember(fact: str, category: str = "general") -> str:
    """Persist a fact/preference so it's retrievable in every future session."""
    store = _store()
    doc = Document(
        page_content=fact,
        metadata={
            "category": category,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    store.add_documents([doc], ids=[str(uuid.uuid4())])
    logger.info(f"Remembered fact (category={category}): {fact}")
    return "Saved."


def recall(query: str, k: int = 3) -> list[dict]:
    """Semantic search over stored long-term facts. Returns [] if nothing's been saved yet."""
    store = _store()
    results = store.similarity_search_with_score(query, k=k)

    facts = []
    for doc, score in results:
        facts.append({
            "fact": doc.page_content,
            "category": doc.metadata.get("category", "general"),
            "created_at": doc.metadata.get("created_at"),
            "score": score,
        })
        logger.debug(f"  Recalled fact (score={score:.4f}): {doc.page_content}")

    logger.info(f"Recalled {len(facts)} long-term facts for query: {query}")
    return facts
