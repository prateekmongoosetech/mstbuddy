from pydantic import BaseModel, Field
from typing import Literal


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096)
    session_id: str = Field(..., min_length=1, max_length=128)
    history: list[HistoryMessage] = Field(default_factory=list)


class SourceChunk(BaseModel):
    source: str
    chunk_index: int | None = None
    score: float
    snippet: str
    page: int | None = None
    title: str | None = None
    source_type: Literal["qdrant", "web_search", "url_fetch"] = "qdrant"


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    session_id: str
    strategy: str = "qdrant"
