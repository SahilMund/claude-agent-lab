"""Anthropic-backed LLMClient implementation."""

from __future__ import annotations

import anthropic

from claude_agent_lab.llm.base import ChatMessage, ToolCall, ToolCallResult


class AnthropicLLMClient:
    """Thin wrapper around the Anthropic Messages API.

    `complete()`: one call in, one string out — callers don't need to know
    about content blocks or SDK-specific exception types.
    `complete_with_tools()`: for the agent orchestrator (Phase 3) — needs
    `stop_reason` and any `tool_use` blocks, which a bare string can't carry.
    Both share `_create_message`'s exception handling: API failures surface
    as a plain RuntimeError with an actionable message either way.
    """

    def __init__(self, *, model: str, max_tokens: int, api_key: str | None = None) -> None:
        self._model = model
        self._max_tokens = max_tokens
        # A bare Anthropic() already resolves ANTHROPIC_API_KEY from the
        # environment; passing api_key explicitly only matters when the
        # caller wants to inject a specific key.
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def _create_message(
        self,
        *,
        messages: list,
        system: str | None,
        tools: list[dict] | None = None,
    ):
        kwargs = {"model": self._model, "max_tokens": self._max_tokens, "messages": messages}
        if system is not None:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        try:
            return self._client.messages.create(**kwargs)
        except anthropic.AuthenticationError as exc:
            raise RuntimeError(
                "Anthropic API rejected the credentials — check ANTHROPIC_API_KEY in .env."
            ) from exc
        except anthropic.PermissionDeniedError as exc:
            raise RuntimeError("Anthropic API key lacks permission for this request.") from exc
        except anthropic.NotFoundError as exc:
            raise RuntimeError(
                f"Anthropic API returned not-found — check the model id ({self._model!r})."
            ) from exc
        except anthropic.RateLimitError as exc:
            raise RuntimeError("Anthropic API rate limit hit — try again shortly.") from exc
        except anthropic.APIConnectionError as exc:
            raise RuntimeError("Could not reach the Anthropic API — check your network.") from exc
        except anthropic.APIStatusError as exc:
            raise RuntimeError(f"Anthropic API error ({exc.status_code}): {exc.message}") from exc
        except TypeError as exc:
            # The SDK raises a bare TypeError (not an anthropic.* exception)
            # when it can't resolve any credentials at all — no API key, no
            # auth token, no `ant auth login` profile.
            raise RuntimeError(
                "No Anthropic credentials found — set ANTHROPIC_API_KEY in .env "
                "(or run `ant auth login`)."
            ) from exc

    def complete(self, messages: list[ChatMessage], *, system: str | None = None) -> str:
        response = self._create_message(messages=messages, system=system)
        return "".join(block.text for block in response.content if block.type == "text")

    def complete_with_tools(
        self, messages: list[dict], tools: list[dict], *, system: str | None = None
    ) -> ToolCallResult:
        response = self._create_message(messages=messages, system=system, tools=tools)
        text = "".join(block.text for block in response.content if block.type == "text")
        tool_calls = [
            ToolCall(id=block.id, name=block.name, input=block.input)
            for block in response.content
            if block.type == "tool_use"
        ]
        return ToolCallResult(
            stop_reason=response.stop_reason,
            text=text,
            tool_calls=tool_calls,
            raw_content=response.content,
        )
