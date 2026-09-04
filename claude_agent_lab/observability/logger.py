"""Minimal logging setup for claude_agent_lab.

One function configures the root `claude_agent_lab` logger once per process;
everything else asks for a named child logger. Structured, observability-
grade logging (spans, request IDs, external sinks, semantic cache hit/miss
metrics) is a Phase 7 concern — this is deliberately just stdlib `logging`
with a readable format, so the rest of the codebase has somewhere to log to
starting on day one.
"""

from __future__ import annotations

import logging
import sys

_configured = False


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger. Safe to call more than once — a no-op after
    the first call, so every entry point can call it defensively."""
    global _configured
    if _configured:
        return

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger namespaced under claude_agent_lab, e.g. get_logger('main')
    -> "claude_agent_lab.main"."""
    return logging.getLogger(f"claude_agent_lab.{name}")
