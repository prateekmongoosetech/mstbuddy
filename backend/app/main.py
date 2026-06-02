import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.services.model_selector import auto_select_models
from app.services.qdrant_init import ensure_collection, close_qdrant_client
from app.services.site_crawler import crawl_mst_website
from app.services.conversation_logger import init_db, get_stats, export_training_jsonl
from app.routes import chat, ingest, health
from app.utils.logger import configure_logging, get_logger

configure_logging()
logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Auto-detect Ollama models
    models = await auto_select_models()
    app.state.chat_model = models["chat_model"]
    app.state.embed_model = models["embed_model"]
    app.state.router_model = models["router_model"]
    app.state.embed_dims = models["embed_dims"]

    # 2. Init conversation DB
    init_db()

    # 3. Ensure Qdrant collection
    await ensure_collection(embed_dims=models["embed_dims"])

    # 3. Background web crawl
    if settings.CRAWL_ON_STARTUP:
        asyncio.create_task(crawl_mst_website(embed_model=models["embed_model"]))
        logger.info("startup_crawl_scheduled", urls=settings.MST_WEBSITE_URLS)

    logger.info("startup_complete", models=models)
    yield

    # Cleanup
    await close_qdrant_client()
    logger.info("shutdown_complete")


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="MST Buddy RAG API",
    description="AI assistant for the MST Blockchain platform",
    version=settings.VERSION,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global error handler — never expose stack traces
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=str(request.url), error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": "An internal server error occurred.", "code": "INTERNAL_ERROR"},
    )


# Admin re-crawl endpoint (protected)
from fastapi import Depends, HTTPException

def _require_admin_key(request: Request) -> None:
    key = request.headers.get("X-API-Key", "")
    if settings.CHATBOT_API_KEY and key != settings.CHATBOT_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/admin/crawl", tags=["admin"])
async def trigger_crawl(
    request: Request,
    _auth: None = Depends(_require_admin_key),
):
    embed_model = getattr(request.app.state, "embed_model", None)
    asyncio.create_task(crawl_mst_website(embed_model=embed_model))
    return {"status": "crawl_started", "seeds": settings.MST_WEBSITE_URLS}


app.include_router(chat.router, tags=["chat"])
app.include_router(ingest.router, tags=["ingest"])
app.include_router(health.router, tags=["health"])


@app.get("/admin/analytics", tags=["admin"])
async def analytics(_auth: None = Depends(_require_admin_key)):
    """Top questions, session counts, total conversations."""
    return get_stats()


@app.get("/admin/export-training", tags=["admin"])
async def export_training(
    limit: int = 5000,
    _auth: None = Depends(_require_admin_key),
):
    """Export Q&A pairs as JSONL for fine-tuning."""
    from fastapi.responses import Response
    import json
    rows = export_training_jsonl(limit=limit)
    content = "\n".join(json.dumps(r) for r in rows)
    return Response(
        content=content,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=mst_training.jsonl"},
    )
