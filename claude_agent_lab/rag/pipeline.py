"""Orchestration for the two things the CLI actually does with RAG:
indexing a directory of source files, and building a grounded prompt from
retrieved chunks for `/ask`.

Kept separate from `main.py` so the REPL stays about I/O (reading input,
printing output) and this module stays about the actual RAG logic — testable
without a terminal or a real LLM/Qdrant instance in the loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from claude_agent_lab.config import ChunkingConfig
from claude_agent_lab.rag.chunking import chunk_file
from claude_agent_lab.rag.indexer import Indexer
from claude_agent_lab.rag.retriever import RetrievedChunk

# Directories never worth indexing: version control internals, this
# project's own local vector store, caches, and virtualenvs. Anything else
# under the given root is a candidate — including non-Python text files
# (README, config.yaml, ...), since a codebase assistant answering "how do I
# configure X" from the docs is a reasonable thing to want.
IGNORED_DIR_NAMES = frozenset(
    {".git", ".agent_lab", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules"}
)


@dataclass(frozen=True)
class IndexResult:
    files_indexed: int
    files_skipped: int
    chunks_indexed: int


def _iter_indexable_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(root).parts
        if any(part in IGNORED_DIR_NAMES or part.startswith(".") for part in relative_parts):
            continue
        yield path


def index_repo(root: Path, *, indexer: Indexer, chunking: ChunkingConfig) -> IndexResult:
    """Chunk and index every text file under `root`, skipping binary files
    and the directories in IGNORED_DIR_NAMES.

    A file that can't be read as UTF-8 text is skipped, not fatal — a repo
    with a handful of binary assets (images, a lockfile with odd encoding)
    shouldn't stop indexing from making progress on everything else.
    """
    files_indexed = 0
    files_skipped = 0
    chunks_indexed = 0

    for path in _iter_indexable_files(root):
        try:
            chunks = chunk_file(
                path,
                fallback_window_lines=chunking.fallback_window_lines,
                fallback_overlap_lines=chunking.fallback_overlap_lines,
            )
        except ValueError:
            files_skipped += 1
            continue

        chunks_indexed += indexer.index_chunks(chunks)
        files_indexed += 1

    return IndexResult(
        files_indexed=files_indexed, files_skipped=files_skipped, chunks_indexed=chunks_indexed
    )


def format_context(chunks: list[RetrievedChunk]) -> str:
    """Render retrieved chunks as labeled code blocks for a prompt."""
    blocks = []
    for chunk in chunks:
        header = f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}"
        if chunk.symbol:
            header += f" ({chunk.kind} {chunk.symbol})"
        blocks.append(f"# {header}\n{chunk.text}")
    return "\n\n".join(blocks)


def build_ask_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    """The user-turn text for `/ask`: retrieved context plus the question.

    If nothing was retrieved (nothing indexed yet, or a genuinely irrelevant
    query), the model is told so explicitly rather than silently getting a
    bare question that looks the same as if retrieval had simply found
    nothing relevant — the two situations call for different answers.
    """
    if not chunks:
        return (
            "No relevant code context was found in the index (nothing may be "
            "indexed yet — try /index first). Answer from general knowledge "
            f"if you can, but say so explicitly.\n\nQuestion: {question}"
        )
    return f"Context from the codebase:\n\n{format_context(chunks)}\n\nQuestion: {question}"
