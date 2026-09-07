"""Builds an Orchestrator wired up from Settings — mirrors llm/factory.py's
job of turning config into a ready-to-use object, so callers (the REPL)
depend on Settings + this module, not on Orchestrator's constructor shape.
"""

from __future__ import annotations

from pathlib import Path

from claude_agent_lab.agent.orchestrator import Orchestrator
from claude_agent_lab.agent.tools import default_tools
from claude_agent_lab.config import Settings
from claude_agent_lab.llm.factory import get_llm_client

AGENT_SYSTEM_PROMPT = (
    "You are claude_agent_lab's coding agent. You can read files and list "
    "directories within the project root using the provided tools. Use "
    "them to ground your answer in what's actually there — don't guess "
    "about file contents you haven't read."
)


def build_agent(settings: Settings, *, root: Path) -> Orchestrator:
    llm_client = get_llm_client(settings)
    tools = default_tools(root)
    return Orchestrator(
        llm_client=llm_client,
        tools=tools,
        system=AGENT_SYSTEM_PROMPT,
        max_iterations=settings.agent.max_tool_iterations,
    )
