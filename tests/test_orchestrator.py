from __future__ import annotations

from claude_agent_lab.agent.orchestrator import Orchestrator
from claude_agent_lab.agent.tools import Tool, ToolError
from claude_agent_lab.llm.base import ToolCall, ToolCallResult


class ScriptedLLMClient:
    """Returns a pre-programmed sequence of ToolCallResults, one per call to
    complete_with_tools — lets a test script an exact multi-turn
    conversation without a real LLM."""

    def __init__(self, results: list[ToolCallResult]) -> None:
        self._results = list(results)
        self.calls: list[list[dict]] = []  # messages seen on each call, for assertions

    def complete(self, messages, *, system=None) -> str:
        raise NotImplementedError("not used by the orchestrator")

    def complete_with_tools(self, messages, tools, *, system=None) -> ToolCallResult:
        self.calls.append(messages)
        return self._results.pop(0)


class RaisingLLMClient:
    def complete(self, messages, *, system=None) -> str:
        raise NotImplementedError

    def complete_with_tools(self, messages, tools, *, system=None) -> ToolCallResult:
        raise RuntimeError("simulated API failure")


def _echo_tool(name: str = "echo") -> Tool:
    def handler(tool_input: dict) -> str:
        return f"echoed: {tool_input.get('value')}"

    return Tool(
        name=name,
        description="Echoes back its input.",
        input_schema={"type": "object", "properties": {"value": {"type": "string"}}},
        handler=handler,
    )


def _failing_tool(name: str = "boom") -> Tool:
    def handler(tool_input: dict) -> str:
        raise ToolError("simulated tool failure")

    return Tool(name=name, description="Always fails.", input_schema={"type": "object"}, handler=handler)


def test_orchestrator_returns_text_immediately_when_no_tool_is_called():
    client = ScriptedLLMClient(
        [ToolCallResult(stop_reason="end_turn", text="the answer", tool_calls=[], raw_content=[])]
    )
    orchestrator = Orchestrator(llm_client=client, tools=[], system="sys")

    assert orchestrator.run("a question") == "the answer"
    assert len(client.calls) == 1


def test_orchestrator_executes_a_tool_call_and_continues_the_loop():
    tool_call = ToolCall(id="call_1", name="echo", input={"value": "hi"})
    client = ScriptedLLMClient(
        [
            ToolCallResult(stop_reason="tool_use", text="", tool_calls=[tool_call], raw_content=["assistant turn 1"]),
            ToolCallResult(stop_reason="end_turn", text="done", tool_calls=[], raw_content=[]),
        ]
    )
    orchestrator = Orchestrator(llm_client=client, tools=[_echo_tool()], system="sys")

    result = orchestrator.run("please echo hi")

    assert result == "done"
    assert len(client.calls) == 2
    # second call's messages include the tool result fed back in
    second_call_messages = client.calls[1]
    tool_result_message = second_call_messages[-1]
    assert tool_result_message["role"] == "user"
    assert tool_result_message["content"][0]["content"] == "echoed: hi"
    assert tool_result_message["content"][0]["tool_use_id"] == "call_1"


def test_orchestrator_reports_unknown_tool_as_an_error_result_without_crashing():
    tool_call = ToolCall(id="call_1", name="does_not_exist", input={})
    client = ScriptedLLMClient(
        [
            ToolCallResult(stop_reason="tool_use", text="", tool_calls=[tool_call], raw_content=[]),
            ToolCallResult(stop_reason="end_turn", text="recovered", tool_calls=[], raw_content=[]),
        ]
    )
    orchestrator = Orchestrator(llm_client=client, tools=[], system="sys")

    result = orchestrator.run("call a tool that doesn't exist")

    assert result == "recovered"
    tool_result_message = client.calls[1][-1]
    assert tool_result_message["content"][0]["is_error"] is True


def test_orchestrator_turns_a_tool_error_into_an_error_result_without_crashing():
    tool_call = ToolCall(id="call_1", name="boom", input={})
    client = ScriptedLLMClient(
        [
            ToolCallResult(stop_reason="tool_use", text="", tool_calls=[tool_call], raw_content=[]),
            ToolCallResult(stop_reason="end_turn", text="recovered", tool_calls=[], raw_content=[]),
        ]
    )
    orchestrator = Orchestrator(llm_client=client, tools=[_failing_tool()], system="sys")

    result = orchestrator.run("trigger the failing tool")

    assert result == "recovered"
    tool_result_message = client.calls[1][-1]
    assert tool_result_message["content"][0]["is_error"] is True
    assert "simulated tool failure" in tool_result_message["content"][0]["content"]


def test_orchestrator_gives_up_after_max_iterations():
    tool_call = ToolCall(id="call_1", name="echo", input={"value": "x"})
    # Always asks for another tool call — never terminates on its own.
    infinite_results = [
        ToolCallResult(stop_reason="tool_use", text="", tool_calls=[tool_call], raw_content=[])
        for _ in range(10)
    ]
    client = ScriptedLLMClient(infinite_results)
    orchestrator = Orchestrator(llm_client=client, tools=[_echo_tool()], system="sys", max_iterations=3)

    result = orchestrator.run("loop forever")

    assert "gave up" in result
    assert len(client.calls) == 3


def test_orchestrator_surfaces_llm_failures_as_an_error_string_not_an_exception():
    orchestrator = Orchestrator(llm_client=RaisingLLMClient(), tools=[], system="sys")
    result = orchestrator.run("anything")
    assert result == "[error] simulated API failure"
