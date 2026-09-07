"""Entry point: config load, logging setup, and the REPL loop.

Four things happen in a REPL turn now:
- plain text -> straight to the LLM, same as Phase 1's bare chat loop.
- `/index [path]` -> chunk and index a directory (default: cwd) into the
  vector store.
- `/ask <question>` -> retrieve relevant chunks (hybrid search) and ask the
  LLM to answer grounded in them — one retrieval call plus one LLM call,
  not a multi-step agent.
- `/agent <goal>` -> hand the goal to the Phase 3 tool-use loop, which can
  read files and list directories on its own (possibly several times) to
  work out an answer, instead of relying on whatever was retrieved once.
"""

from __future__ import annotations

from pathlib import Path

from claude_agent_lab.agent.factory import build_agent
from claude_agent_lab.config import get_settings
from claude_agent_lab.llm.base import ChatMessage
from claude_agent_lab.llm.factory import get_embedder, get_llm_client
from claude_agent_lab.observability.logger import configure_logging, get_logger
from claude_agent_lab.rag.indexer import Indexer
from claude_agent_lab.rag.pipeline import build_ask_prompt, index_repo
from claude_agent_lab.rag.retriever import HybridRetriever
from claude_agent_lab.rag.store import get_qdrant_client

CHAT_SYSTEM_PROMPT = "You are claude_agent_lab, a CLI coding assistant under active development."
ASK_SYSTEM_PROMPT = (
    "You are claude_agent_lab's codebase assistant. Answer using only the "
    "provided code context. If the context doesn't contain the answer, say "
    "so plainly instead of guessing."
)
ASK_TOP_K = 5
EXIT_COMMANDS = {"/exit", "/quit"}
HELP_TEXT = (
    "Commands:\n"
    "  /index [path]    chunk and index a directory (default: current directory)\n"
    "  /ask <question>  answer a question using retrieved code context (RAG)\n"
    "  /agent <goal>    let the agent read files/directories on its own to work it out\n"
    "  /exit, /quit     quit\n"
    "  anything else is sent straight to the LLM as plain chat\n"
)

logger = get_logger("main")


def handle_index(path_arg: str, *, indexer: Indexer, chunking) -> None:
    root = Path(path_arg or ".").expanduser().resolve()
    if not root.is_dir():
        print(f"[error] not a directory: {root}")
        return

    print(f"Indexing {root} ...")
    result = index_repo(root, indexer=indexer, chunking=chunking)
    print(
        f"Indexed {result.files_indexed} files ({result.chunks_indexed} chunks); "
        f"skipped {result.files_skipped} unreadable file(s)."
    )


def handle_ask(question: str, *, retriever: HybridRetriever, llm_client) -> None:
    if not question:
        print("[error] usage: /ask <question>")
        return

    chunks = retriever.retrieve(question, top_k=ASK_TOP_K)
    prompt = build_ask_prompt(question, chunks)
    try:
        answer = llm_client.complete(
            [{"role": "user", "content": prompt}], system=ASK_SYSTEM_PROMPT
        )
    except RuntimeError as exc:
        print(f"[error] {exc}")
        return

    print(answer)
    if chunks:
        sources = ", ".join(f"{c.file_path}:{c.start_line}-{c.end_line}" for c in chunks)
        print(f"\n[sources: {sources}]")


def handle_agent(goal: str, *, orchestrator) -> None:
    if not goal:
        print("[error] usage: /agent <goal>")
        return
    print(orchestrator.run(goal))


def run_repl() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Starting claude_agent_lab REPL (model=%s)", settings.llm.model)

    try:
        llm_client = get_llm_client(settings)
        embedder = get_embedder(settings)
        qdrant_client = get_qdrant_client(settings.vector_store.path)
        agent = build_agent(settings, root=Path.cwd())
    except Exception as exc:  # a bad provider/config shouldn't crash with a traceback
        print(f"Failed to initialize: {exc}")
        return

    indexer = Indexer(
        client=qdrant_client,
        embedder=embedder,
        collection_name=settings.vector_store.collection_name,
    )
    retriever = HybridRetriever(
        client=qdrant_client,
        embedder=embedder,
        collection_name=settings.vector_store.collection_name,
        rrf_k=settings.retrieval.rrf_k,
    )

    history: list[ChatMessage] = []
    print("claude_agent_lab — phase 3. Type /help for commands, /exit to quit.\n")

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
        if user_input in ("/help", "/?"):
            print(HELP_TEXT)
            continue
        if user_input == "/index" or user_input.startswith("/index "):
            handle_index(user_input[len("/index") :].strip(), indexer=indexer, chunking=settings.chunking)
            continue
        if user_input.startswith("/ask "):
            handle_ask(user_input[len("/ask ") :].strip(), retriever=retriever, llm_client=llm_client)
            continue
        if user_input.startswith("/agent "):
            handle_agent(user_input[len("/agent ") :].strip(), orchestrator=agent)
            continue

        history.append({"role": "user", "content": user_input})
        try:
            reply = llm_client.complete(history, system=CHAT_SYSTEM_PROMPT)
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
