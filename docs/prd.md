# claude-agent-lab — Product Requirements Document

## Main Objective

Rebuild a RAG-powered, agentic CLI code assistant — ported from a reference implementation (`capstone_project` / `educosys_claude`, kept outside this repo) — in order to:

1. Deeply understand every subsystem of a production-shaped agentic AI application (RAG indexing/retrieval, agent orchestration, memory, MCP tool integration, task planning, caching, observability) by porting and adapting real, working code — not reading about it in the abstract.
2. Produce a public, portfolio-quality repository with an honest, incremental commit history.
3. Generate reusable interview-preparation material (HLD, LLD, and targeted Q&A) tied directly to real, working code — not abstract theory.

This is a learning project first, a portfolio artifact second.

## Background

The reference project is a CLI tool ("Educosys Claude" in the original) that lets a user run `/ask <question>` against an indexed codebase and get RAG-grounded answers, with additional capabilities: semantic caching, session memory, MCP-based tool access (GitHub, filesystem), and an agentic task planner that can decompose and execute multi-step goals (`/plan <goal>`) with an approval/recovery loop.

**How this repo is actually built (the process, not just the goal):** find the relevant portion of the source codebase for a phase, port it in with the renaming mapping below applied, fix whatever's broken (dependency rot, config bugs, Python-version incompatibilities), and enhance where it clearly helps. Independent design happens only where the source has no equivalent (Phase 8's dashboard, later removed — see below). See `CLAUDE.md` for the full process.

**Renaming applied throughout** (package `educosys_claude` → `claude_agent_lab`; full table in `CLAUDE.md`) — no upstream branding carried into this repo.

**Provider defaults changed from the source:** the source defaults to OpenAI for both chat (`gpt-5.5`) and embeddings (`text-embedding-3-small`). This fork defaults `llm.provider` to `anthropic` (`claude-opus-5`) — matching the project's own name and purpose — and `embeddings.provider` to `huggingface` (a local, no-API-key model) rather than OpenAI, so running this fork doesn't require a second provider's API key for no reason. Both providers were already supported by the source's `llm/factory.py` — this is a config default change, not new code.

**LLM provider enhancement (Phase 1, post-port):** `llm/factory.py::get_llm()` extended with three more provider branches beyond the source's `anthropic`/`openai` — `gemini`, `groq`, `ollama` — same pattern, same config-only switch. See `docs/progress.md`.

`mcp_demo` reference script was evaluated and excluded — the reference project's own `mcp/` module already supersedes it with a config-driven, logged, reusable implementation. Not part of this build.

## Phase-Wise Action Items

Each row is a directory that already exists in the source reference — porting it is the deliverable, not designing it from scratch.

| Phase | Branch | Focus | Source directory | Status |
|---|---|---|---|---|
| **1** | `phase-1-foundations` | Config system, LLM/embedder factory, CLI skeleton | `config.py`, `config.yaml`, `llm/`, `observability/`, `main.py` (skeleton) | Ported, verified |
| **2** | `phase-2-rag-core` | Code indexing & retrieval | `context/indexers/`, `context/retrievers/` | Ported, verified against live Qdrant |
| **3** | `phase-3-agent-core` | Agent orchestration + tool execution | `agent/`, `tools/` | Ported, verified (real MCP tools loaded, agent compiles) |
| **4** | `phase-4-memory` | Session & short-term memory | `memory/` | Ported |
| **5** | `phase-5-mcp` | MCP tool integration | `mcp/`, `mcp_servers.json` (renamed per mapping) | Ported, verified (GitHub + filesystem servers, 40 tools loaded) |
| **6** | `phase-6-task-planning` | Agentic task planner | `tasks/` | Ported |
| **7** | `phase-7-production` | Production-grade concerns | `cache/`, `skills/`, `context/indexers/watcher.py` | Ported |
| **8** | `phase-8-frontend` | Dashboard UI over the existing backend | *(no source equivalent — new work)* | Built, then removed — see below |

**Phase 8 detail** (the one phase with no source to port from): a FastAPI service (`api/app.py`, `api/routes.py`) exposing indexing, `/ask` retrieval, and the agent's tool-use loop over HTTP (streaming for the agent's live trace), plus a React + Vite SPA (`frontend/`) with three views — indexing status, an ask view showing the answer plus its retrieved sources, and an agent view showing the tool-call trace live. Additive to the CLI, not a replacement for it — the REPL stayed the primary interface.

**Phase 8 was removed.** The dashboard never reached the reliability bar the rest of this project holds itself to and added a second UI surface (`api/` + `frontend/`, a Node toolchain, a FastAPI dependency) for a capability the REPL already covers. Both `claude_agent_lab/api/` and `frontend/` were deleted; `fastapi`, `uvicorn`, and `sse-starlette` were dropped from `pyproject.toml`. The CLI (`main.py`) remains the only interface.

Each phase branches off the previous phase's branch (stacked), gets its own PR, and updates the running phase documentation (`docs/progress.md`: what was ported / what broke and how it was fixed / architecture notes / HLD / LLD / interview questions).

## Success Criteria

- Every phase's code actually runs and is demoable — verified against real infrastructure (a live Qdrant instance, real MCP servers), not just "it imports"
- Every bug found during porting is documented with what broke and why, not silently patched
- Every phase's doc entry explains *why*, not just *what*
- Interview-question bank grows to a meaningful, review-ready size
- Commit history reflects real work done on the days it claims to be done

## Out of Scope (for now)

- `mcp_demo/` reference script (superseded, not carried forward)
- Production deployment/hosting concerns beyond what's covered in Phase 7
- Multi-tenancy / auth (not present in the reference project either)
- A dashboard/HTTP UI over the CLI — attempted once as Phase 8, removed; the REPL stays the primary, only interface
