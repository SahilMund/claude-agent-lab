"""FastAPI app factory.

Startup does exactly what main.py's REPL does on launch (index the repo,
build the semantic cache, build the agent with a checkpointer) — same
functions, same order — so the API and the CLI are two front ends on one
backend, not two backends that happen to agree.
"""

from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from claude_agent_lab.agent.factory import build_agent
from claude_agent_lab.cache.semantic_cache import build_semantic_cache, get_repo_domain
from claude_agent_lab.context.indexers.factory import get_indexer
from claude_agent_lab.context.indexers.watcher import start_watcher, stop_watcher
from claude_agent_lab.memory.session import get_current_session
from claude_agent_lab.memory.short_term import get_checkpointer_db_path
from claude_agent_lab.observability.logger import get_logger

logger = get_logger(__name__)

# The Vite dev server's default origin. Not read from config.yaml — this is
# a dev-time convenience, not a deployment concern (see docs/prd.md's Phase
# 8 out-of-scope note: no auth, no multi-user, single-machine use).
DEV_FRONTEND_ORIGIN = "http://localhost:5173"


@asynccontextmanager
async def lifespan(app: FastAPI):
    repo_path = str(Path.cwd())
    logger.info(f"API starting up — indexing {repo_path}")

    async with (
        AsyncSqliteSaver.from_conn_string(get_checkpointer_db_path()) as checkpointer,
        AsyncExitStack() as exit_stack,
    ):
        app.state.repo_path = repo_path
        app.state.index = get_indexer()(repo_path)
        # `exit_stack` keeps MCP tool sessions open for the API's whole
        # lifetime instead of reconnecting (respawning stdio subprocesses)
        # on every tool call — see mcp/mcp_client.py.
        app.state.agent = await build_agent(checkpointer, exit_stack)
        app.state.session_id = get_current_session()

        semantic_cache = await build_semantic_cache()
        app.state.semantic_cache = semantic_cache
        app.state.cache_domain = get_repo_domain(repo_path) if semantic_cache else None

        def _invalidate_cache_on_change() -> None:
            if semantic_cache is not None:
                import asyncio

                asyncio.create_task(semantic_cache.invalidate_domain(app.state.cache_domain))

        # NOTE (known issue, ported as-is — see docs/progress.md): the
        # watcher's on-change handler is hardcoded to Chroma's per-file
        # index functions regardless of vector_store.provider. With the
        # qdrant/hybrid default this fork uses, file changes do NOT
        # actually update the live index — only /index (a full re-embed)
        # does. Included here anyway for CLI/API parity: main.py has the
        # same gap, and silently dropping it from just the API would be a
        # third, undocumented inconsistency on top of two already-known ones.
        observer = start_watcher(repo_path, on_change=_invalidate_cache_on_change)

        logger.info(f"API ready — session {app.state.session_id}")
        yield

        stop_watcher(observer)

    logger.info("API shutting down")


def create_app() -> FastAPI:
    app = FastAPI(title="claude_agent_lab API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[DEV_FRONTEND_ORIGIN],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from claude_agent_lab.api.routes import router

    app.include_router(router)
    return app


app = create_app()
