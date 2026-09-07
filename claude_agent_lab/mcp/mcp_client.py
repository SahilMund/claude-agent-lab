from contextlib import AsyncExitStack

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from claude_agent_lab.mcp.mcp_config import load_mcp_configs
from claude_agent_lab.observability.logger import get_logger


logger = get_logger(__name__)


async def get_agent_mcp_tools(exit_stack: AsyncExitStack) -> list:
  """Connect to all configured MCP servers and return their tools.

  `MultiServerMCPClient.get_tools()` — the simple one-liner — opens a brand
  new session for every single tool *call*, not once per app run (it says so
  in its own docstring). For a stdio server that means spawning a fresh
  subprocess (e.g. `npx @modelcontextprotocol/server-filesystem`) on every
  tool invocation, which is slow and was the actual cause of `/ask` taking
  several seconds per tool call, repeated MCP server restarts in the logs.

  Instead we open one session per server via `client.session(...)` and keep
  it alive for the life of the app, registered on the caller's
  `exit_stack` (the same `AsyncExitStack` the caller holds open for its own
  lifetime, e.g. across an `async with` in main.py/api/app.py) so it's torn
  down cleanly on shutdown rather than per call.
  """
  configs = load_mcp_configs()
  logger.info(f"Connecting to MCP servers: {list(configs.keys())}")

  client = MultiServerMCPClient(configs)
  tools = []
  for server_name in configs:
      session = await exit_stack.enter_async_context(client.session(server_name))
      tools.extend(await load_mcp_tools(session))

  logger.info(f"Loaded {len(tools)} tools from MCP servers")
  return tools
