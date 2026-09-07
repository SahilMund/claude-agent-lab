"""Shared interfaces for LLM chat clients and embedders.

Structural `Protocol`s rather than ABCs: a provider class satisfies these by
having the right methods, with no inheritance and no import-time coupling
back to this module. Callers (the REPL today; the agent orchestrator and
retrievers from later phases) should type against these, never against a
concrete provider class.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypedDict


class ChatMessage(TypedDict):
    role: str
    content: str


class LLMClient(Protocol):
    """A single-turn chat completion client.

    Deliberately narrow for Phase 1: one call in, one string out. Streaming
    and multi-block responses stayed hidden behind this method — Phase 3
    adds `complete_with_tools` alongside it (not instead of it) once tool
    use actually needed those details to surface. See `ToolCallResult`.
    """

    def complete(self, messages: list[ChatMessage], *, system: str | None = None) -> str: ...

    def complete_with_tools(
        self, messages: list[dict], tools: list[dict], *, system: str | None = None
    ) -> ToolCallResult: ...


class Embedder(Protocol):
    """Turns text into vectors. Not called by anything yet — wired into
    indexing/retrieval in Phase 2.
    """

    def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class ToolCall:
    """One tool invocation the model asked for."""

    id: str
    name: str
    input: dict


@dataclass(frozen=True)
class ToolCallResult:
    """The result of one turn of a tool-enabled completion.

    `raw_content` is deliberately provider-native (the Anthropic SDK's own
    content-block objects, not a project-owned type) — it exists purely to
    be handed back unchanged as the next turn's assistant message, which is
    exactly what the Anthropic SDK's own documented manual-loop pattern
    does. Abstracting that too would mean designing a provider-agnostic
    content-block schema for a project with exactly one provider; see
    docs/progress.md's architecture-decision log for why that trade was
    made instead of left unresolved.
    """

    stop_reason: str
    text: str
    tool_calls: list[ToolCall]
    raw_content: Any
