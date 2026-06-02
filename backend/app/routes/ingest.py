from fastapi import APIRouter, File, Form, UploadFile, Request, Depends, HTTPException
from app.models.ingest import IngestResponse, FileIngestResult
from app.services.ingestion import ingest_file
from app.config import settings
from app.utils.logger import get_logger
import time

router = APIRouter()
logger = get_logger()

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "md", "json"}


def _require_api_key(request: Request) -> None:
    key = request.headers.get("X-API-Key", "")
    if settings.CHATBOT_API_KEY and key != settings.CHATBOT_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    request: Request,
    files: list[UploadFile] = File(...),
    collection_name: str | None = Form(None),
    _auth: None = Depends(_require_api_key),
):
    embed_model = getattr(request.app.state, "embed_model", None)
    results: list[FileIngestResult] = []
    total = 0

    for file in files:
        fname = file.filename or "unknown"
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        if ext not in ALLOWED_EXTENSIONS:
            results.append(FileIngestResult(
                filename=fname, chunks_ingested=0, status="error",
                error=f"Unsupported file type: .{ext}"
            ))
            continue

        t0 = time.monotonic()
        try:
            data = await file.read()
            n = await ingest_file(
                file_bytes=data,
                filename=fname,
                embed_model=embed_model,
                collection=collection_name,
            )
            total += n
            latency = round((time.monotonic() - t0) * 1000)
            logger.info("file_ingested", filename=fname, chunks=n, latency_ms=latency)
            results.append(FileIngestResult(filename=fname, chunks_ingested=n, status="ok"))
        except Exception as e:
            logger.error("ingest_error", filename=fname, error=str(e))
            results.append(FileIngestResult(
                filename=fname, chunks_ingested=0, status="error", error=str(e)
            ))

    return IngestResponse(
        results=results,
        collection=collection_name or settings.QDRANT_COLLECTION,
        total_chunks=total,
    )
