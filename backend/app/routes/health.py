import httpx
from fastapi import APIRouter, Request
from app.config import settings
from app.services.qdrant_init import get_qdrant_client

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    # Qdrant check
    qdrant_status = "ok"
    try:
        client = get_qdrant_client()
        await client.get_collections()  # returns CollectionsResponse
    except Exception:
        qdrant_status = "fail"

    # Ollama / embedding check
    embedding_status = "ok"
    if settings.EMBEDDING_PROVIDER == "ollama":
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{settings.OLLAMA_URL}/api/tags")
                resp.raise_for_status()
        except Exception:
            embedding_status = "fail"

    # Selected models from app state
    models = {
        "chat": getattr(request.app.state, "chat_model", settings.LLM_MODEL),
        "embed": getattr(request.app.state, "embed_model", settings.EMBED_MODEL),
        "router": getattr(request.app.state, "router_model", settings.ROUTER_MODEL),
    }

    overall = "ok" if qdrant_status == "ok" and embedding_status == "ok" else "degraded"

    return {
        "status": overall,
        "qdrant": qdrant_status,
        "embedding": embedding_status,
        "models": models,
        "version": settings.VERSION,
    }
