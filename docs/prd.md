# claude-agent-lab — Product Requirements Document

## Main Objective

Rebuild a RAG-powered, agentic CLI code assistant — originally studied from a reference implementation (`capstone_project` / `educosys_claude`) — from the ground up, one architectural layer at a time, in order to:

1. Deeply understand every subsystem of a production-shaped agentic AI application (RAG indexing/retrieval, agent orchestration, memory, MCP tool integration, task planning, caching, observability) by building it rather than just reading it.
2. Produce a public, portfolio-quality repository with an honest, incremental commit history reflecting real day-by-day learning.
3. Generate reusable interview-preparation material (HLD, LLD, and targeted Q&A) tied directly to real, working code — not abstract theory.

This is a learning project first, a portfolio artifact second. No fabricated history, no skipped understanding — see `WORKFLOW.md` (to follow) for the operating rules.

## Background

The reference project is a CLI tool ("Educosys Claude" in the original) that lets a user run `/ask <question>` against an indexed codebase and get RAG-grounded answers, with additional capabilities: semantic caching, session memory, MCP-based tool access (GitHub, filesystem), and an agentic task planner that can decompose and execute multi-step goals (`/plan <goal>`) with an approval/recovery loop.

Renaming applied throughout this rebuild (package `educosys_claude` → `claude_agent_lab`; see prior discussion for the full mapping) — no upstream branding carried into this repo.

MCP demo script (`mcp_demo/github_mcp_demo.py`) was evaluated and excluded — the capstone project's `mcp/` module already supersedes it with a config-driven, logged, reusable implementation. Not part of this build.

## Phase-Wise Action Items

| Phase | Branch | Focus | Deliverables |
|---|---|---|---|
| **1** | `phase-1-foundations` | Config system, LLM factory, embeddings, CLI skeleton | Working REPL shell, `config.py`/`config.yaml`, `llm/factory.py`, root `README.md` (status/limitations/roadmap), `.env.example` |
| **2** | `phase-2-rag-core` | Code indexing & retrieval | Indexers (semantic + hybrid), retrievers, tree-sitter-based code-aware chunking, HLD/LLD doc entry with architecture-decision log for chosen matching strategy |
| **3** | `phase-3-agent-core` | Agent orchestration + tool execution | `agent/factory.py`, `agent/orchestrator.py`, `agent/tools.py`, filesystem/terminal tools |
| **4** | `phase-4-memory` | Session & short-term memory | `memory/session.py`, `memory/short_term.py`, session switching |
| **5** | `phase-5-mcp` | MCP tool integration | `mcp/mcp_client.py`, `mcp/mcp_config.py`, `mcp_servers.json` (renamed per mapping), GitHub + filesystem servers wired in |
| **6** | `phase-6-task-planning` | Agentic task planner | `tasks/planner.py`, `executor.py`, `approval.py`, `recovery.py`, `status.py`, `task_store.py`, `orchestrator.py` |
| **7** | `phase-7-production` | Production-grade concerns | Semantic cache (Redis-backed), observability/logging, skills registry, file watcher with cache invalidation, tests (`tests/`), optional CI |

Each phase branches off the previous phase's branch (stacked), gets its own PR, and updates the running phase documentation per the `repo-doc-architect` skill (what changed / architecture decisions / HLD / LLD / ~40-50 interview questions).

## Success Criteria

- Every phase's code actually runs and is demoable on its own
- Every phase's doc entry explains *why*, not just *what* — a reader with zero context on this project should be able to understand the system by reading the docs alone
- Interview-question bank grows to a meaningful, review-ready size by Phase 7
- Commit history reflects real work done on the days it claims to be done — no backdating, no batch-then-spread pushes

## Out of Scope (for now)

- `mcp_demo/` reference script (superseded, not carried forward)
- Production deployment/hosting concerns beyond what's covered in Phase 7
- Multi-tenancy / auth (not present in the reference project either)
