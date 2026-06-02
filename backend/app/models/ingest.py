from pydantic import BaseModel


class FileIngestResult(BaseModel):
    filename: str
    chunks_ingested: int
    status: str
    error: str | None = None


class IngestResponse(BaseModel):
    results: list[FileIngestResult]
    collection: str
    total_chunks: int
