# claude_agent_lab

A RAG-powered, agentic CLI code assistant — ported phase by phase from a reference implementation, as a system-design learning project.

Unlike this repo's earlier history (see `git log` before this branch), this is **not** an independent reimplementation. It's a direct port of `source/capstone_project/educosys_claude/` (kept outside this repo), renamed per `CLAUDE.md`'s mapping table, with real bugs fixed and small enhancements made along the way — documented as they're found, not silently. See `docs/prd.md` for the phase breakdown and `docs/progress.md` for what was ported, fixed, and why.

## Status

**Fully ported and verified working end to end** — indexing, retrieval, and the agent all tested against a live Qdrant instance and real MCP servers (not just "it imports").

What's here:
- **Config** (`config.py`, `config.yaml`) — plain YAML, loaded once at import time. `.env` for secrets.
- **LLM/embeddings** (`llm/factory.py`) — LangChain-based, provider chosen by `config.yaml`'s `llm.provider`, no code change needed to switch: `anthropic` (default — the source defaults to OpenAI), `openai`, `gemini`, `groq`, or `ollama` (local, no API key). `HuggingFaceEmbeddings` for embeddings (runs locally, no API key — the source defaults to OpenAI embeddings, which would need a second API key for no real reason here).
- **Indexing & retrieval** (`context/indexers/`, `context/retrievers/`) — tree-sitter-based code-aware chunking (15 languages), semantic (Chroma or Qdrant) or hybrid (Qdrant native sparse+dense) retrieval, chosen via `config.yaml`. Default: Qdrant + hybrid.
- **Agent** (`agent/`) — LangChain's `create_agent` + LangGraph checkpointer-backed memory, with a `search_codebase` tool, filesystem tools (`tools/filesystem_tools.py`), a terminal tool (`tools/terminal_tools.py`), MCP tools (GitHub + filesystem servers), and skill-as-tool loading.
- **Memory** (`memory/`) — session tracking (which conversation thread is "current") plus a SQLite-backed LangGraph checkpointer with automatic summarization once a conversation gets long.
- **MCP** (`mcp/`) — connects to the servers listed in `mcp_servers.json` (GitHub, filesystem, by default).
- **Tasks** (`tasks/`) — a `/plan <goal>` planner/executor with approval and recovery steps.
- **Cache** (`cache/`) — Redis-backed semantic cache for `/ask` answers; degrades to "disabled" instead of crashing if Redis isn't running.
- **Skills** (`skills/`) — a skill registry loaded as agent tools.
- File watcher (`context/indexers/watcher.py`) — re-invalidates the semantic cache when the codebase changes. **Known gap:** hardcoded to Chroma's per-file update functions regardless of `vector_store.provider` — with this fork's Qdrant default, file changes don't actually reach the live index; only a full re-index (`/reindex`, or the dashboard's "Re-index now") does. Ported as-is, documented rather than silently fixed — see `docs/progress.md`.
- **Dashboard** (`claude_agent_lab/api/`, `frontend/`) — a FastAPI backend and React/Vite frontend over the same CLI backend: indexing status, `/ask` with its sources, and a live streamed view of the agent's tool calls. The one phase with no source to port from — see `docs/prd.md`'s Phase 8 detail.

## Getting Started

**Prerequisites:**
- Python ≥3.12
- A running Qdrant instance — `docker run -p 6333:6333 qdrant/qdrant` (or point `QDRANT_URL`/`QDRANT_API_KEY` at a remote one). The CLI does not run without this — indexing happens at startup.
- Node.js/`npx` — the MCP servers (GitHub, filesystem) launch via `npx`.
- Optional: Redis (`redis://localhost:6379`) for the semantic cache — the app runs fine without it, just without caching.

The first run downloads the local embedding model from Hugging Face Hub; after that it's
cached (`~/.cache/huggingface`). If you restart the app often during development and hit
`HTTP Error 429 ... Rate limited` on startup, set `HF_HUB_OFFLINE=1` to skip the network
metadata check and use the cached model directly.

```bash
# 1. Install dependencies (Poetry, or plain pip -e .)
poetry install

# 2. Configure credentials
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY (and GITHUB_TOKEN if you'll use the github MCP server)

# 3. Start Qdrant
docker run -p 6333:6333 qdrant/qdrant

# 4. Run the REPL
poetry run claude_agent_lab
```

On startup, the CLI indexes the current directory (skipping unchanged data on repeat runs), connects to configured MCP servers, and starts a session:

```
> /ask how does the config system work?
<answer, grounded in retrieved code, from the agent's search_codebase tool>

> /reindex               # re-index the current directory after changes
> /new_session           # start a fresh conversation
> /switch <session_id>   # resume a past session
> /plan <goal>           # generate and execute a multi-step plan
> /task_status           # show progress on active plans
```

### Switching LLM providers

`llm/factory.py` supports five providers — a `config.yaml` edit, no code change:

```yaml
llm:
  provider: anthropic   # anthropic | openai | gemini | groq | ollama
  model: claude-opus-5  # a model name valid for that provider
```

Each provider (except `ollama`, which talks to a local server instead) reads its API key
from its own env var — see `.env.example`. Only the branches for `anthropic` and `openai`
came from the source; `gemini`, `groq`, and `ollama` are an enhancement on top of the same
factory pattern (see `docs/progress.md`).

### Dashboard (Phase 8)

The same backend, over HTTP, with a React frontend on top:

```bash
# with Qdrant already running and .env configured (see above)
uvicorn claude_agent_lab.api.app:app --port 8000

# in a second terminal
cd frontend
npm install
npm run dev
```

Open the printed Vite URL (usually `http://localhost:5173`). See `frontend/README.md` for details.

## What was fixed during the port

Real bugs found and fixed while porting, not hypothetical:

1. **`tree-sitter-languages` is unmaintained** and has no wheels for current Python — swapped for `tree-sitter-language-pack`, the actively maintained fork with the same `get_language()`/`get_parser()` API.
2. **Byte-offset/character-offset bug in the code parser** — tree-sitter's `start_byte`/`end_byte` are UTF-8 *byte* offsets, but the code sliced the Python `str` (character-indexed) with them, silently corrupting every chunk's name and content as soon as a multi-byte character (em dash, arrow, smart quote — common throughout this codebase's own docstrings) appeared anywhere earlier in the file. Fixed by slicing the encoded bytes and decoding the result.
3. **`config.yaml` had a duplicate `vector_store:` key** (the second silently overwrote the first) — consolidated into one block.
4. **Missing `sentence-transformers` dependency** — required by `langchain_huggingface.HuggingFaceEmbeddings` at runtime but not declared in `pyproject.toml`.
5. **A blank `QDRANT_API_KEY=` in `.env` silently forces HTTPS against a local Qdrant, causing an `SSL: WRONG_VERSION_NUMBER` error** — `qdrant-client` treats "empty string" and "not provided" as different states (only `None` skips the HTTPS inference), and `os.getenv()` returns `""` for a blank env line, not `None`. Fixed at all four call sites (`context/{indexers,retrievers}/{semantic,hybrid}_qdrant.py`) with `os.getenv(...) or None`. Found by a user actually running the CLI per this README's own instructions — see `docs/progress.md` for how it was actually diagnosed.

See `docs/progress.md` for the full writeup, including what was *not* changed and why.

## Roadmap

| Phase | Focus | Status |
|---|---|---|
| 1 | Config system, LLM/embedder factory, CLI skeleton | Ported, verified |
| 2 | Code indexing & retrieval (semantic + hybrid) | Ported, verified against live Qdrant |
| 3 | Agent orchestration + tool execution | Ported, verified (real MCP tools loaded) |
| 4 | Session & short-term memory | Ported (LangGraph checkpointer) |
| 5 | MCP tool integration | Ported, verified (GitHub + filesystem servers, 40 tools) |
| 6 | Agentic task planner | Ported |
| 7 | Production concerns (cache, watcher, skills) | Ported |
| 8 | Dashboard UI (FastAPI + React) | Built, verified end-to-end (real Qdrant, real MCP servers, real retrieval quality) — no source equivalent, genuinely new work |

Full detail: `docs/prd.md`.

## Project Layout

```
claude_agent_lab/              ← repo
├── claude_agent_lab/           ← the package
│   ├── agent/                  ← LangChain/LangGraph agent factory + orchestrator
│   ├── api/                    ← FastAPI app + routes (Phase 8)
│   ├── cache/                  ← Redis-backed semantic cache
│   ├── context/
│   │   ├── indexers/           ← tree-sitter chunking, semantic/hybrid indexers, file watcher
│   │   └── retrievers/         ← semantic/hybrid retrieval
│   ├── llm/                    ← LangChain LLM/embedder factory
│   ├── mcp/                    ← MCP client + config
│   ├── memory/                 ← session tracking, LangGraph checkpointer
│   ├── observability/          ← logging
│   ├── skills/                 ← skill registry + skill-as-tool loading
│   ├── tasks/                  ← planner/executor/approval/recovery
│   ├── tools/                  ← filesystem + terminal tools
│   ├── config.py / config.yaml
│   ├── mcp_servers.json
│   └── main.py
├── frontend/                    ← React + Vite dashboard (Phase 8)
├── docs/
│   ├── prd.md
│   └── progress.md
├── .env.example
├── CLAUDE.md
└── pyproject.toml
```
