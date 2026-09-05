"""Factory functions for LLM chat clients and embedders.

Centralizing construction here means callers (the REPL today; the agent
orchestrator and retrievers from later phases) depend on Settings + this
module, never on a specific provider SDK — swapping providers is a
config.yaml edit, not a code change at every call site.
"""

from __future__ import annotations

from claude_agent_lab.config import Settings
from claude_agent_lab.llm.anthropic_client import AnthropicLLMClient
from claude_agent_lab.llm.base import Embedder, LLMClient
from claude_agent_lab.llm.embedders import FakeEmbedder, VoyageEmbedder


def get_llm_client(settings: Settings) -> LLMClient:
    provider = settings.llm.provider
    if provider == "anthropic":
        return AnthropicLLMClient(
            model=settings.llm.model,
            max_tokens=settings.llm.max_tokens,
            api_key=settings.anthropic_api_key,
        )
    raise ValueError(f"Unknown LLM provider: {provider!r}")


def get_embedder(settings: Settings) -> Embedder:
    provider = settings.embedding.provider
    if provider == "fake":
        return FakeEmbedder()
    if provider == "voyage":
        return VoyageEmbedder(model=settings.embedding.model, api_key=settings.voyage_api_key)
    raise ValueError(f"Unknown embedding provider: {provider!r}")
