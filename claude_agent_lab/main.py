"""Entry point: config load, logging setup, and the bare REPL loop.

No RAG, no agent orchestration, no tool use yet — those land in Phases 2-3.
This loop exists to prove the config system and LLM factory work end to
end: type a message, get a Claude response back, keep the turn in history.
"""

from __future__ import annotations

from claude_agent_lab.config import get_settings
from claude_agent_lab.llm.base import ChatMessage
from claude_agent_lab.llm.factory import get_llm_client
from claude_agent_lab.observability.logger import configure_logging, get_logger

SYSTEM_PROMPT = "You are claude_agent_lab, a CLI coding assistant under active development."
EXIT_COMMANDS = {"/exit", "/quit"}

logger = get_logger("main")


def run_repl() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Starting claude_agent_lab REPL (model=%s)", settings.llm.model)

    try:
        client = get_llm_client(settings)
    except Exception as exc:  # a bad provider/config shouldn't crash with a traceback
        print(f"Failed to initialize LLM client: {exc}")
        return

    history: list[ChatMessage] = []
    print("claude_agent_lab — phase 1 skeleton. Type /exit to quit.\n")

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input in EXIT_COMMANDS:
            break

        history.append({"role": "user", "content": user_input})
        try:
            reply = client.complete(history, system=SYSTEM_PROMPT)
        except RuntimeError as exc:
            print(f"[error] {exc}")
            history.pop()  # don't poison history with a failed turn
            continue

        history.append({"role": "assistant", "content": reply})
        print(reply)

    print("Goodbye.")


def main() -> None:
    run_repl()


if __name__ == "__main__":
    main()
