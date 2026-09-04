"""Shared interfaces for LLM chat clients and embedders.

Structural `Protocol`s rather than ABCs: a provider class satisfies these by
having the right methods, with no inheritance and no import-time coupling
back to this module. Callers (the REPL today; the agent orchestrator and
retrievers from Phase 2 on) should type against these, never against a
concrete provider class.
"""

from __future__ import annotations

from typing import Protocol, TypedDict


class ChatMessage(TypedDict):
    role: str
    content: str


class LLMClient(Protocol):
    """A single-turn chat completion client.

    Deliberately narrow for Phase 1: one call in, one string out. Streaming,
    tool use, and multi-block responses are provider-implementation details
    hidden behind this method — they surface here only once a later phase
    (agent orchestration, task planning) actually needs them.
    """

    def complete(self, messages: list[ChatMessage], *, system: str | None = None) -> str: ...


class Embedder(Protocol):
    """Turns text into vectors. Not called by anything yet — wired into
    indexing/retrieval in Phase 2.
    """

    def embed(self, texts: list[str]) -> list[list[float]]: ...
