"""The agentic tool-use loop: send a goal plus tool definitions to the LLM,
execute any tool it calls, feed the results back, and repeat until it stops
calling tools (or a hard iteration cap is hit).

Written as a manual loop, not the Anthropic SDK's beta Tool Runner — see
docs/progress.md's architecture-decision log. Depends on `LLMClient`
(`llm.base`), not the Anthropic SDK directly, so the same exception-to-
RuntimeError mapping Phase 1 built for plain chat covers this loop too,
without duplicating it here.
"""

from __future__ import annotations

from claude_agent_lab.agent.tools import Tool, ToolError
from claude_agent_lab.llm.base import LLMClient, ToolCall
from claude_agent_lab.observability.logger import get_logger

logger = get_logger("agent.orchestrator")

DEFAULT_MAX_ITERATIONS = 10


class Orchestrator:
    """Runs one goal through the tool-use loop and returns the final answer."""

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        tools: list[Tool],
        system: str,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self._llm_client = llm_client
        self._tools_by_name = {tool.name: tool for tool in tools}
        self._tool_schemas = [tool.to_api_schema() for tool in tools]
        self._system = system
        self._max_iterations = max_iterations

    def run(self, goal: str) -> str:
        # Not a ChatMessage list — an assistant turn's content becomes the
        # provider-native tool_use blocks and a tool turn's content becomes
        # a list of tool_result blocks, neither of which fits ChatMessage's
        # plain-string shape. See llm/base.py's ToolCallResult docstring.
        messages: list[dict] = [{"role": "user", "content": goal}]

        for _ in range(self._max_iterations):
            try:
                result = self._llm_client.complete_with_tools(
                    messages, self._tool_schemas, system=self._system
                )
            except RuntimeError as exc:
                return f"[error] {exc}"

            if result.stop_reason != "tool_use":
                return result.text

            messages.append({"role": "assistant", "content": result.raw_content})
            tool_results = [self._execute(call) for call in result.tool_calls]
            messages.append({"role": "user", "content": tool_results})

        return (
            f"[error] gave up after {self._max_iterations} tool-use steps "
            "without a final answer"
        )

    def _execute(self, call: ToolCall) -> dict:
        tool = self._tools_by_name.get(call.name)
        if tool is None:
            logger.warning("Model called unknown tool: %s", call.name)
            return {
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": f"Unknown tool: {call.name}",
                "is_error": True,
            }

        try:
            output = tool.handler(call.input)
        except ToolError as exc:
            logger.info("Tool %s failed: %s", call.name, exc)
            return {
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": str(exc),
                "is_error": True,
            }

        return {"type": "tool_result", "tool_use_id": call.id, "content": output}
