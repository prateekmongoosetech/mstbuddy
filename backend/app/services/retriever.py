from app.config import settings
from app.services.embedder import embed
from app.services.qdrant_init import get_qdrant_client
from qdrant_client.models import Filter, FieldCondition, MatchText


def _to_chunk(payload: dict, score: float) -> dict:
    return {
        "text": payload.get("text", ""),
        "score": round(float(score), 4),
        "source": payload.get("source", "unknown"),
        "page": payload.get("page"),
        "chunk_index": payload.get("chunk_index"),
        "title": payload.get("title"),
        "source_type": payload.get("type", "qdrant"),
    }


async def retrieve(
    query: str,
    top_k: int | None = None,
    embed_model: str | None = None,
    collection: str | None = None,
) -> list[dict]:
    k = top_k or settings.TOP_K
    col = collection or settings.QDRANT_COLLECTION

    vectors = await embed([query], model=embed_model)
    query_vec = vectors[0]

    client = get_qdrant_client()
    results = await client.search(
        collection_name=col,
        query_vector=query_vec,
        limit=k,
        with_payload=True,
    )

    chunks = [_to_chunk(hit.payload or {}, hit.score) for hit in results]

    if settings.RERANK_ENABLED and chunks:
        chunks = await _rerank(query, chunks)

    return chunks


async def keyword_retrieve(
    keywords: list[str],
    top_k: int = 4,
    collection: str | None = None,
) -> list[dict]:
    """
    Fallback keyword search using Qdrant payload text matching.
    Returns chunks containing any of the given keywords.
    Used to catch domain-specific terms that vector search misses.
    """
    col = collection or settings.QDRANT_COLLECTION
    client = get_qdrant_client()
    chunks = []
    seen: set[tuple] = set()

    for kw in keywords:
        try:
            results, _ = await client.scroll(
                collection_name=col,
                scroll_filter=Filter(
                    must=[FieldCondition(key="text", match=MatchText(text=kw))]
                ),
                limit=top_k,
                with_payload=True,
            )
            for point in results:
                payload = point.payload or {}
                key = (payload.get("source"), payload.get("chunk_index"))
                if key not in seen:
                    seen.add(key)
                    chunks.append(_to_chunk(payload, score=0.75))
        except Exception:
            pass

    return chunks


async def _rerank(query: str, chunks: list[dict]) -> list[dict]:
    try:
        import cohere
        co = cohere.AsyncClient(api_key=settings.COHERE_API_KEY)
        docs = [c["text"] for c in chunks]
        result = await co.rerank(
            query=query,
            documents=docs,
            model="rerank-english-v3.0",
            top_n=len(docs),
        )
        reranked = []
        for r in result.results:
            chunk = dict(chunks[r.index])
            chunk["score"] = round(float(r.relevance_score), 4)
            reranked.append(chunk)
        return reranked
    except Exception as e:
        print(f"[retriever] Rerank failed, returning original order: {e}")
        return chunks
