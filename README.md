# claude_agent_lab

An incremental, from-scratch rebuild of a RAG-powered, agentic CLI code assistant — built phase-by-phase as a system-design learning project.

This is **not** a copy of the reference implementation it's studied from (a separate `capstone_project` codebase). Each phase is implemented fresh, with its own architecture-decision log, so the commit history reflects real day-by-day understanding rather than a port. See [`docs/prd.md`](docs/prd.md) for the full objective and phase breakdown, and [`docs/progress.md`](docs/progress.md) for the running build log (what changed, why, HLD/LLD, and interview questions per phase).

## Status

**Phase 1 — Foundations: done.** **Phase 2 — RAG core: done.**

Landed so far:
- Layered config system (`claude_agent_lab/config.py` + `config.yaml`): env vars > `.env` > `config.yaml` > built-in defaults, with API keys read only from the environment.
- LLM/embedder factory (`claude_agent_lab/llm/`): provider-agnostic `LLMClient`/`Embedder` protocols, an Anthropic-backed chat client, and a Voyage AI embedder (implemented, not yet exercised) behind a dependency-free `FakeEmbedder` default.
- Minimal logger (`claude_agent_lab/observability/logger.py`): stdlib `logging`, one setup call, namespaced child loggers.
- CLI (`claude_agent_lab/main.py`): a REPL with plain chat (Phase 1), plus `/index [path]` and `/ask <question>` (Phase 2) — no agent loop or tool use yet, that's Phase 3.
- Code-aware chunking (`claude_agent_lab/rag/chunking.py`): splits a Python file into chunks at function/class boundaries using tree-sitter, with a fixed-size overlapping-line-window fallback for every other file type.
- Indexing & retrieval (`claude_agent_lab/rag/indexer.py`, `retriever.py`, `fusion.py`, `store.py`): embeds chunks into a local (embedded) Qdrant vector store, with both pure-semantic and hybrid (semantic + BM25, combined via Reciprocal Rank Fusion) retrieval, reachable from the CLI via `/index` and `/ask` (`rag/pipeline.py`).

## Getting Started

```bash
# 1. Install dependencies (Poetry)
poetry install

# 2. Configure credentials
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY

# 3. Run the REPL
poetry run claude-agent-lab
# or: poetry run python -m claude_agent_lab.main
```

Non-secret settings (model, max tokens, embedding provider, log level) live in [`config.yaml`](config.yaml) and can be overridden per-run with `AGENT_LAB_<SECTION>_<FIELD>` environment variables — see the comments in `config.yaml` and `.env.example`.

Once running, index a codebase and ask questions about it:

```
> /index .
Indexing /path/to/some/repo ...
Indexed 30 files (135 chunks); skipped 0 unreadable file(s).

> /ask how does the config system decide precedence between config.yaml and env vars?
<answer, grounded in the retrieved chunks, followed by their source file:line locations>
```

Anything not starting with `/index` or `/ask` is sent straight to the LLM as plain chat (Phase 1 behavior, unchanged).

## Limitations

By design, none of the following exist yet:
- `/ask` is one retrieval call plus one LLM call — no multi-turn follow-up, no memory of previous `/ask` questions, no agent loop deciding to search again or use a tool. That's Phase 3+.
- No agent orchestration or tool use — the REPL is a plain single-turn-per-message chat loop (or a single retrieve-then-answer call for `/ask`), not an agent (Phase 3).
- No session or short-term memory — conversation history is in-process only and is lost on exit (Phase 4).
- No MCP tool integration (Phase 5).
- No task planner / `/plan` command (Phase 6).
- No semantic cache, skills registry, file watcher, or CI (Phase 7). A `tests/` directory exists starting Phase 2, but only covers what each phase adds — it's not a project-wide suite yet.
- The Voyage AI embedder is implemented against the documented client shape but has not been exercised against a live account — `config.yaml` defaults `embedding.provider` to a deterministic `FakeEmbedder` so the CLI runs with zero setup. This also means hybrid retrieval's semantic half hasn't been tested against real embeddings yet — see `docs/progress.md`'s open item on retuning `retrieval.rrf_k` once it has.
- Chunking only has a syntax-aware path for Python; every other file type gets fixed-size line-window chunks.
- No incremental re-indexing — running the indexer again over an edited codebase updates chunks whose location didn't move, but doesn't clean up chunks that shifted or were deleted (closer to a Phase 7 file-watcher concern).

## Roadmap

| Phase | Branch | Focus |
|---|---|---|
| 1 | `phase-1-foundations` | Config system, LLM/embedder factory, CLI skeleton *(done)* |
| 2 | `phase-2-rag-core` | Code indexing & retrieval (semantic + hybrid, tree-sitter chunking) *(done)* |
| 3 | `phase-3-agent-core` | Agent orchestration + tool execution |
| 4 | `phase-4-memory` | Session & short-term memory |
| 5 | `phase-5-mcp` | MCP tool integration (GitHub, filesystem) |
| 6 | `phase-6-task-planning` | Agentic task planner with approval/recovery loop |
| 7 | `phase-7-production` | Semantic cache, observability, skills registry, tests, CI |

Full detail per phase: [`docs/prd.md`](docs/prd.md).

## Project Layout

```
claude_agent_lab/              ← repo
├── claude_agent_lab/          ← the package
│   ├── llm/                   ← LLMClient / Embedder protocols, factory, providers
│   ├── rag/                   ← chunking, indexing, retrieval (Phase 2)
│   ├── observability/         ← logging
│   ├── config.py              ← Settings model + config.yaml/.env loader
│   └── main.py                ← entry point / REPL
├── tests/                      ← pytest, one file per module under test
├── .agent_lab/                  ← local runtime data (Qdrant store) — gitignored, not versioned
├── config.yaml                 ← non-secret runtime config (versioned)
├── .env.example                 ← secret config template (copy to .env)
├── docs/
│   ├── prd.md                  ← objective + phase plan
│   └── progress.md             ← per-phase build log (what/why/HLD/LLD/Q&A)
├── CLAUDE.md
└── pyproject.toml
```
