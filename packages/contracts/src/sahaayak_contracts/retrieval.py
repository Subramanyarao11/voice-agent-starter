"""Contracts for source-grounded retrieval over the hosted knowledge base."""

from pydantic import BaseModel, Field


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    max_results: int = Field(default=5, ge=1, le=10)


class RetrievedSource(BaseModel):
    source_id: str
    filename: str
    score: float = Field(ge=0)
    excerpt: str
    source_url: str = ""
    attributes: dict[str, str | float | bool] = Field(default_factory=dict)


class RagSearchResponse(BaseModel):
    query: str
    sources: list[RetrievedSource] = Field(default_factory=list)


class RagAnswerResponse(BaseModel):
    query: str
    answer: str
    sources: list[RetrievedSource] = Field(default_factory=list)
