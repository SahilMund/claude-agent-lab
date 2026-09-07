"""API routes.

Every handler calls the same functions main.py's REPL calls
(get_indexer(), get_retriever(), handle_query(), agent.astream_events())
— this module is a thin HTTP wrapper, not a second implementation of any
of this logic.

/ask makes two calls where the CLI's /ask makes one: it calls the
retriever directly (for structured `sources` the dashboard can render)
*and* invokes the agent (whose own search_codebase tool call re-retrieves
internally). That duplicate retrieval call is cheap (no LLM involved) and
the alternative — parsing the agent's own formatted tool-result string
back into structured fields — is more fragile than it's worth.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from claude_agent_lab.agent.orchestrator import handle_query
from claude_agent_lab.config import config
from claude_agent_lab.context.indexers.factory import get_indexer
from claude_agent_lab.context.retrievers.factory import get_retriever
from claude_agent_lab.observability.logger import get_logger

from .schemas import AgentStreamRequest, AskRequest, AskResponse, IndexResponse, SourceChunk

logger = get_logger(__name__)
router = APIRouter()


def _collection_point_count(vector_store) -> int:
    collection_name = config["qdrant"]["collection_name"]
    return vector_store.client.get_collection(collection_name).points_count


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/index/status", response_model=IndexResponse)
async def index_status(request: Request) -> IndexResponse:
    """Current index size — for the dashboard's indexing-status view."""
    return IndexResponse(
        repo_path=request.app.state.repo_path,
        collection_name=config["qdrant"]["collection_name"],
        chunks_indexed=_collection_point_count(request.app.state.index),
    )


@router.post("/index", response_model=IndexResponse)
async def reindex(request: Request) -> IndexResponse:
    """Re-index the repo path the API was started with — same as the CLI's /reindex."""
    repo_path = request.app.state.repo_path
    vector_store = get_indexer()(repo_path)
    request.app.state.index = vector_store
    return IndexResponse(
        repo_path=repo_path,
        collection_name=config["qdrant"]["collection_name"],
        chunks_indexed=_collection_point_count(vector_store),
    )


@router.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest, request: Request) -> AskResponse:
    """One question, one grounded answer, plus the sources it was grounded in."""
    thread_id = body.thread_id or request.app.state.session_id

    retrieve = get_retriever()
    raw_sources = retrieve(body.question, k=5)

    answer = await handle_query(
        request.app.state.agent,
        body.question,
        thread_id,
        semantic_cache=request.app.state.semantic_cache,
        cache_domain=request.app.state.cache_domain,
    )

    sources = [
        SourceChunk(
            source=chunk["source"],
            name=chunk["name"],
            type=chunk["type"],
            start_line=chunk["start_line"],
            end_line=chunk["end_line"],
            distance=chunk.get("distance"),
        )
        for chunk in raw_sources
    ]
    return AskResponse(answer=answer, thread_id=thread_id, sources=sources)


@router.post("/agent/stream")
async def agent_stream(body: AgentStreamRequest, request: Request) -> EventSourceResponse:
    """Same question as /ask, but streamed as Server-Sent Events showing
    each tool call as it happens, ending with the final answer — the
    "watch the agent work" view /ask's single JSON response can't give you.
    """
    agent = request.app.state.agent
    thread_id = body.thread_id or request.app.state.session_id
    run_config = {"configurable": {"thread_id": thread_id}}

    async def event_generator():
        try:
            async for event in agent.astream_events(
                {"messages": [{"role": "user", "content": body.question}]},
                run_config,
                version="v2",
            ):
                kind = event["event"]

                if kind == "on_tool_start":
                    yield {
                        "event": "tool_start",
                        "data": json.dumps(
                            {"tool": event["name"], "input": event["data"].get("input")}
                        ),
                    }
                elif kind == "on_tool_end":
                    output = event["data"].get("output")
                    content = getattr(output, "content", str(output))
                    yield {
                        "event": "tool_end",
                        "data": json.dumps({"tool": event["name"], "output": content}),
                    }
                elif kind == "on_chain_end" and event["name"] == "LangGraph":
                    messages = event["data"]["output"]["messages"]
                    final_text = next(
                        (
                            message.content
                            for message in reversed(messages)
                            if getattr(message, "type", None) == "ai" and message.content
                        ),
                        "",
                    )
                    yield {"event": "final", "data": json.dumps({"answer": final_text})}
        except Exception as exc:  # keep the stream alive long enough to report the failure
            logger.error(f"Agent stream error: {exc}")
            yield {"event": "error", "data": json.dumps({"error": str(exc)})}

    return EventSourceResponse(event_generator())
