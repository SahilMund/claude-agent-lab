from langchain.agents import create_agent

from claude_agent_lab.llm.factory import get_llm
from claude_agent_lab.agent.tools import search_codebase
from claude_agent_lab.observability.logger import get_logger
from claude_agent_lab.tools.terminal_tools import run_command, run_in_directory
from claude_agent_lab.mcp.mcp_client import get_agent_mcp_tools
from claude_agent_lab.skills.skill_tools import load_skill, build_skills_prompt

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a senior software engineer with deep knowledge of the codebase.
Always use the search_codebase tool before answering any question.
Reference specific file names, function names and line numbers in your answers.
If you cannot find the answer in the codebase, say so explicitly."""

async def build_agent(checkpointer):
   """Create and return a LangChain agent with persistent memory."""
   llm = get_llm()
   mcp_tools = await get_agent_mcp_tools()

   skills_prompt = build_skills_prompt()
   full_prompt = SYSTEM_PROMPT
   if skills_prompt:
       full_prompt = SYSTEM_PROMPT + "\n\n" + skills_prompt

   tools = [
       search_codebase,
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