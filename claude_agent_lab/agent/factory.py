from contextlib import AsyncExitStack

from langchain.agents import create_agent

from claude_agent_lab.llm.factory import get_llm
from claude_agent_lab.agent.tools import search_codebase, recall, remember
from claude_agent_lab.observability.logger import get_logger
from claude_agent_lab.tools.terminal_tools import run_command, run_in_directory
from claude_agent_lab.mcp.mcp_client import get_agent_mcp_tools
from claude_agent_lab.skills.skill_tools import load_skill, build_skills_prompt

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a senior software engineer with deep knowledge of the codebase.
Always use the search_codebase tool before answering any question.
Reference specific file names, function names and line numbers in your answers.
If you cannot find the answer in the codebase, say so explicitly.

You also have long-term memory that persists across sessions, separate from
this conversation's own history:
- Use the recall tool before answering if a past preference, correction, or
  project convention might be relevant — it searches every past session,
  not just this one.
- Use the remember tool when the user states a durable preference,
  convention, or correction that should apply in future sessions too — not
  for one-off details only relevant to this turn."""

async def build_agent(checkpointer, exit_stack: AsyncExitStack):
   """Create and return a LangChain agent with persistent memory.

   `exit_stack` is the caller's `AsyncExitStack` (open for the app's whole
   lifetime) — MCP tool sessions are registered on it so they stay open for
   reuse across every tool call instead of reconnecting each time. See
   mcp/mcp_client.py.
   """
   llm = get_llm()
   mcp_tools = await get_agent_mcp_tools(exit_stack)

   skills_prompt = build_skills_prompt()
   full_prompt = SYSTEM_PROMPT
   if skills_prompt:
       full_prompt = SYSTEM_PROMPT + "\n\n" + skills_prompt

   tools = [
       search_codebase,
       recall,
       remember,
       load_skill,
       run_command,
       run_in_directory,
       *mcp_tools,
   ]

   return create_agent(
       llm,
       tools=tools,
       system_prompt=full_prompt,
       checkpointer=checkpointer,
   )