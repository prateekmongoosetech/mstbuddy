from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams
from app.config import settings

_client: AsyncQdrantClient | None = None


def get_qdrant_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        kwargs: dict = {"url": settings.QDRANT_URL}
        if settings.QDRANT_API_KEY:
            kwargs["api_key"] = settings.QDRANT_API_KEY
        _client = AsyncQdrantClient(**kwargs)
    return _client


async def close_qdrant_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


async def ensure_collection(embed_dims: int = 768) -> None:
    client = get_qdrant_client()
    resp = await client.get_collections()
    existing = {c.name for c in resp.collections}
    if settings.QDRANT_COLLECTION not in existing:
        await client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=embed_dims, distance=Distance.COSINE),
        )
        print(f"[qdrant] Created collection '{settings.QDRANT_COLLECTION}' (dims={embed_dims})")
    else:
        print(f"[qdrant] Collection '{settings.QDRANT_COLLECTION}' already exists")
