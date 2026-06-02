import json
import uuid
from datetime import datetime, timezone
from typing import Any

from langchain.text_splitter import RecursiveCharacterTextSplitter
from qdrant_client.models import PointStruct

from app.config import settings
from app.services.embedder import embed
from app.services.qdrant_init import get_qdrant_client

_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=64)


def _load_text(file_bytes: bytes, filename: str) -> list[dict[str, Any]]:
    """Parse file bytes into a list of {text, page} dicts."""
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        import fitz  # PyMuPDF
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []
        for i, page in enumerate(doc):
            pages.append({"text": page.get_text(), "page": i + 1})
        return pages

    if ext == "docx":
        import io
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return [{"text": text, "page": 1}]

    if ext == "json":
        data = json.loads(file_bytes.decode("utf-8"))
        text = json.dumps(data, indent=2)
        return [{"text": text, "page": 1}]

    # md, txt, or anything else
    return [{"text": file_bytes.decode("utf-8", errors="replace"), "page": 1}]


async def ingest_file(
    file_bytes: bytes,
    filename: str,
    embed_model: str | None = None,
    collection: str | None = None,
) -> int:
    """Ingest a single file. Returns number of chunks upserted."""
    col = collection or settings.QDRANT_COLLECTION
    pages = _load_text(file_bytes, filename)
    ingested_at = datetime.now(timezone.utc).isoformat()

    points: list[PointStruct] = []
    chunk_idx = 0

    for page_data in pages:
        chunks = _splitter.split_text(page_data["text"])
        for chunk_text in chunks:
            if not chunk_text.strip():
                continue
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=[],  # filled below
                    payload={
                        "text": chunk_text,
                        "source": filename,
                        "chunk_index": chunk_idx,
                        "page": page_data["page"],
                        "ingested_at": ingested_at,
                        "type": "document",
                    },
                )
            )
            chunk_idx += 1

    if not points:
        return 0

    texts = [p.payload["text"] for p in points]
    vectors = await embed(texts, model=embed_model)
    for point, vec in zip(points, vectors):
        point.vector = vec

    client = get_qdrant_client()
    await client.upsert(collection_name=col, points=points)
    return len(points)


async def ingest_text_chunks(
    text: str,
    metadata: dict[str, Any],
    embed_model: str | None = None,
    collection: str | None = None,
) -> int:
    """Ingest raw text (e.g. from web crawler). Returns chunks upserted."""
    col = collection or settings.QDRANT_COLLECTION
    ingested_at = datetime.now(timezone.utc).isoformat()
    chunks = _splitter.split_text(text)

    points: list[PointStruct] = []
    for idx, chunk_text in enumerate(chunks):
        if not chunk_text.strip():
            continue
        payload = {
            "text": chunk_text,
            "chunk_index": idx,
            "ingested_at": ingested_at,
            **metadata,
        }
        points.append(PointStruct(id=str(uuid.uuid4()), vector=[], payload=payload))

    if not points:
        return 0

    texts = [p.payload["text"] for p in points]
    vectors = await embed(texts, model=embed_model)
    for point, vec in zip(points, vectors):
        point.vector = vec

    client = get_qdrant_client()
    await client.upsert(collection_name=col, points=points)
    return len(points)
