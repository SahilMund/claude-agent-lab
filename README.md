# claude_agent_lab

An incremental, from-scratch rebuild of a RAG-powered, agentic CLI code assistant — built phase-by-phase as a system-design learning project.

This is **not** a copy of the reference implementation it's studied from (a separate `capstone_project` codebase). Each phase is implemented fresh, with its own architecture-decision log, so the commit history reflects real day-by-day understanding rather than a port. See [`docs/prd.md`](docs/prd.md) for the full objective and phase breakdown, and [`docs/progress.md`](docs/progress.md) for the running build log (what changed, why, HLD/LLD, and interview questions per phase).

## Status

**Phase 1 — Foundations: done.** **Phase 2 — RAG core: in progress.**

Landed so far:
- Layered config system (`claude_agent_lab/config.py` + `config.yaml`): env vars > `.env` > `config.yaml` > built-in defaults, with API keys read only from the environment.
- LLM/embedder factory (`claude_agent_lab/llm/`): provider-agnostic `LLMClient`/`Embedder` protocols, an Anthropic-backed chat client, and a Voyage AI embedder (implemented, not yet exercised) behind a dependency-free `FakeEmbedder` default.
- Minimal logger (`claude_agent_lab/observability/logger.py`): stdlib `logging`, one setup call, namespaced child loggers.
- Bare CLI skeleton (`claude_agent_lab/main.py`): a REPL loop that sends each turn straight to the configured LLM client — no RAG, no tools, no agent loop yet.
- Code-aware chunking (`claude_agent_lab/rag/chunking.py`): splits a Python file into chunks at function/class boundaries using tree-sitter, with a fixed-size overlapping-line-window fallback for every other file type. Not yet wired to indexing or retrieval — that's the rest of Phase 2.

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

## Limitations

By design, none of the following exist yet:
- No indexing or retrieval yet — chunking (Phase 2, in progress) has no vector store or search behind it.
- No agent orchestration or tool use — the REPL is a plain single-turn-per-message chat loop, not an agent (Phase 3).
- No session or short-term memory — conversation history is in-process only and is lost on exit (Phase 4).
- No MCP tool integration (Phase 5).
- No task planner / `/plan` command (Phase 6).
- No semantic cache, skills registry, file watcher, or CI (Phase 7). A `tests/` directory exists starting Phase 2, but only covers what each phase adds — it's not a project-wide suite yet.
- The Voyage AI embedder is implemented against the documented client shape but has not been exercised against a live account — `config.yaml` defaults `embedding.provider` to a deterministic `FakeEmbedder` so the CLI runs with zero setup.
- Chunking only has a syntax-aware path for Python; every other file type gets fixed-size line-window chunks.

## Roadmap

| Phase | Branch | Focus |
|---|---|---|
| 1 | `phase-1-foundations` | Config system, LLM/embedder factory, CLI skeleton *(done)* |
| 2 | `phase-2-rag-core` | Code indexing & retrieval (semantic + hybrid, tree-sitter chunking) *(in progress)* |
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
│   ├── rag/                   ← chunking (Phase 2); indexing/retrieval land alongside it
│   ├── observability/         ← logging
│   ├── config.py              ← Settings model + config.yaml/.env loader
│   └── main.py                ← entry point / REPL
├── tests/                      ← pytest, one file per module under test
├── config.yaml                 ← non-secret runtime config (versioned)
├── .env.example                 ← secret config template (copy to .env)
├── docs/
│   ├── prd.md                  ← objective + phase plan
│   └── progress.md             ← per-phase build log (what/why/HLD/LLD/Q&A)
├── CLAUDE.md
└── pyproject.toml
```
