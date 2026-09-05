"""Anthropic-backed LLMClient implementation."""

from __future__ import annotations

import anthropic

from claude_agent_lab.llm.base import ChatMessage


class AnthropicLLMClient:
    """Thin wrapper around the Anthropic Messages API.

    One call in, one string out — callers don't need to know about content
    blocks or SDK-specific exception types; API failures surface as a plain
    RuntimeError with an actionable message.
    """

    def __init__(self, *, model: str, max_tokens: int, api_key: str | None = None) -> None:
        self._model = model
        self._max_tokens = max_tokens
        # A bare Anthropic() already resolves ANTHROPIC_API_KEY from the
        # environment; passing api_key explicitly only matters when the
        # caller wants to inject a specific key.
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def complete(self, messages: list[ChatMessage], *, system: str | None = None) -> str:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                messages=messages,  # type: ignore[arg-type]
            )
        except anthropic.AuthenticationError as exc:
            raise RuntimeError(
                "Anthropic API rejected the credentials — check ANTHROPIC_API_KEY in .env."
            ) from exc
        except anthropic.PermissionDeniedError as exc:
            raise RuntimeError(
                "Anthropic API key lacks permission for this request."
            ) from exc
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

        return "".join(block.text for block in response.content if block.type == "text")
