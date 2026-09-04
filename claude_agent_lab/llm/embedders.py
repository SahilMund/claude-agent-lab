"""Embedder implementations.

Not yet wired into any retrieval path — that lands in Phase 2 (RAG core).
Phase 1 only needs the factory to hand back a working client so the
Embedder interface is settled before anything depends on it.
"""

from __future__ import annotations

import hashlib


class FakeEmbedder:
    """Deterministic, dependency-free embedder for local dev and tests.

    Hashes each text into a fixed-size vector of floats in [-1, 1]. This is
    NOT semantically meaningful — never use it for anything that needs real
    similarity. It exists so the rest of the system can be exercised (config
    → factory → embedder call) without network access or an API key.
    """

    def __init__(self, dimensions: int = 32) -> None:
        self._dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_vector(text) for text in texts]

    def _hash_vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        repeats = self._dimensions // len(digest) + 1
        raw = (digest * repeats)[: self._dimensions]
        return [(byte / 127.5) - 1.0 for byte in raw]


class VoyageEmbedder:
    """Embedder backed by Voyage AI — Anthropic's recommended embeddings
    partner (Anthropic does not serve first-party embeddings).

    Implemented against the documented `voyageai` client shape but not yet
    exercised end-to-end against a live account — that verification happens
    in Phase 2, once retrieval actually calls it.
    """

    def __init__(self, *, model: str, api_key: str | None = None) -> None:
        import voyageai  # lazy import so the "fake" default stays dependency-free

        self._model = model
        self._client = voyageai.Client(api_key=api_key) if api_key else voyageai.Client()

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = self._client.embed(texts, model=self._model, input_type="document")
        return result.embeddings
