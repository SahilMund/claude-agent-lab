"""Pydantic request/response models for the API."""

from __future__ import annotations

from pydantic import BaseModel


class IndexResponse(BaseModel):
    repo_path: str
    collection_name: str
    chunks_indexed: int


class SourceChunk(BaseModel):
    source: str
    name: str
    type: str
    start_line: int
    end_line: int
    distance: float | None = None


class AskRequest(BaseModel):
    question: str
    thread_id: str | None = None


class AskResponse(BaseModel):
    answer: str
    thread_id: str
    sources: list[SourceChunk]


class AgentStreamRequest(BaseModel):
    question: str
    thread_id: str | None = None
