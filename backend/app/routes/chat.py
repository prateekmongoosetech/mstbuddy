import json
import re
import time
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.models.chat import ChatRequest
from app.services.retriever import retrieve, keyword_retrieve
from app.services.router import route_query
from app.services.web_search import ddgo_search, fetch_and_extract
from app.services.mst_price import get_mst_price_context
from app.services.mstscan import get_explorer_context
from app.services.conversation_logger import log_conversation
from app.services.llm import stream_llm
from app.utils.prompt_builder import build_system_prompt, build_messages
from app.utils.language import is_non_english, detect_language, translate_to_english
from app.utils.logger import get_logger
from app.config import settings

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
logger = get_logger()

# Domain-specific terms that vector search often misses — used for keyword fallback
_KEYWORD_PATTERNS: list[tuple[re.Pattern, list[str]]] = [
    (re.compile(r"\baudit\b", re.I),          ["QuillAudits", "audit", "security audit"]),
    (re.compile(r"\bstaking\b", re.I),         ["staking", "stake", "lockup"]),
    (re.compile(r"\breferral\b", re.I),        ["referral", "commission", "MLM"]),
    (re.compile(r"\brapiddex\b", re.I),        ["RapidDex", "DEX", "swap"]),
    (re.compile(r"\bvalidator\b", re.I),       ["validator", "fractional validator"]),
    (re.compile(r"\bwallet\b", re.I),          ["wallet", "MetaMask", "BridgeKey"]),
    (re.compile(r"\bwhitepaper\b", re.I),      ["whitepaper", "tokenomics"]),
    (re.compile(r"\bteam|founder|owner\b", re.I), ["team", "founder", "CEO"]),
    (re.compile(r"\bgrant\b", re.I),           ["grant", "developer grant"]),
    (re.compile(r"\bambassador\b", re.I),      ["ambassador", "Ambassador program"]),
]

def _extract_keywords(query: str) -> list[str]:
    """Return keyword terms to use for fallback retrieval based on query content."""
    terms: list[str] = []
    for pattern, keywords in _KEYWORD_PATTERNS:
        if pattern.search(query):
            terms.extend(keywords)
    return list(dict.fromkeys(terms))  # dedupe, preserve order


async def _generate_sse(
    req: ChatRequest,
    request: Request,
):
    chat_model = getattr(request.app.state, "chat_model", settings.LLM_MODEL)
    embed_model = getattr(request.app.state, "embed_model", None)
    router_model = getattr(request.app.state, "router_model", settings.ROUTER_MODEL)

    t0 = time.monotonic()

    # 1. Detect language — translate to English for routing + retrieval if needed
    user_lang = detect_language(req.message)
    search_query = req.message
    if is_non_english(req.message):
        search_query = await translate_to_english(req.message, model=router_model)

    # 2. Route the query (use English version for reliable regex/LLM routing)
    route = await route_query(search_query, router_model=router_model)
    strategy = route.get("strategy", "qdrant")

    context_chunks: list[dict] = []

    # 3. Always retrieve from Qdrant using English query for better vector match
    qdrant_chunks = await retrieve(search_query, embed_model=embed_model)
    seen_ids = {(c["source"], c["chunk_index"]) for c in qdrant_chunks}

    # 3b. If original was non-English, also search with original to catch any gaps
    if is_non_english(req.message) and search_query != req.message:
        extra_chunks = await retrieve(req.message, embed_model=embed_model, top_k=4)
        for c in extra_chunks:
            key = (c["source"], c["chunk_index"])
            if key not in seen_ids:
                qdrant_chunks.append(c)
                seen_ids.add(key)

    # 3c. Keyword fallback — extract domain terms from translated query for exact matches
    kw_terms = _extract_keywords(search_query)
    if kw_terms:
        kw_chunks = await keyword_retrieve(kw_terms, top_k=3)
        for c in kw_chunks:
            key = (c["source"], c["chunk_index"])
            if key not in seen_ids:
                qdrant_chunks.append(c)
                seen_ids.add(key)

    context_chunks.extend(qdrant_chunks)

    # 3. Web search if needed
    if strategy in ("web_search", "combined"):
        web_query = route.get("web_query") or req.message
        search_results = await ddgo_search(web_query)
        for r in search_results:
            if settings.WEB_SEARCH_FETCH_CONTENT:
                page_text = await fetch_and_extract(r["url"])
            else:
                page_text = r.get("snippet", "")
            context_chunks.append(
                {
                    "text": page_text,
                    "source": r["url"],
                    "title": r.get("title"),
                    "source_type": "web_search",
                    "score": 0.7,
                    "page": None,
                    "chunk_index": None,
                }
            )

    # 4. Live blockchain explorer data from mstscan.com
    if strategy == "mst_explorer":
        explorer_text = await get_explorer_context(req.message)
        context_chunks.append(
            {
                "text": explorer_text,
                "source": "mstscan.com",
                "title": "MST Mainnet Explorer (Blockscout)",
                "source_type": "url_fetch",
                "score": 1.0,
                "page": None,
                "chunk_index": None,
            }
        )

    # 5. Live MST price from official API
    elif strategy == "mst_price":
        price_text = await get_mst_price_context()
        context_chunks.append(
            {
                "text": price_text,
                "source": "api.mstblockchain.com/fractions/price",
                "title": "Live MST Token Price",
                "source_type": "url_fetch",
                "score": 1.0,
                "page": None,
                "chunk_index": None,
            }
        )

    # 6. Fetch specific URL if needed
    elif strategy == "fetch_url" and route.get("url"):
        page_text = await fetch_and_extract(route["url"])
        context_chunks.append(
            {
                "text": page_text,
                "source": route["url"],
                "source_type": "url_fetch",
                "score": 0.9,
                "page": None,
                "chunk_index": None,
            }
        )

    # 6. Build prompt — inject language instruction if non-English
    system = build_system_prompt(context_chunks, user_lang=user_lang)
    messages = build_messages(req.message, [h.model_dump() for h in req.history], user_lang=user_lang)

    # 7. Stream response via SSE
    sources = [
        {
            "source": c["source"],
            "chunk_index": c.get("chunk_index"),
            "score": c.get("score", 0),
            "snippet": c["text"][:120] if c.get("text") else "",
            "page": c.get("page"),
            "title": c.get("title"),
            "source_type": c.get("source_type", "qdrant"),
        }
        for c in context_chunks
    ]

    # Send sources as first SSE event
    yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'strategy': strategy})}\n\n"

    full_answer = ""
    try:
        async for token in stream_llm(messages, system, chat_model=chat_model):
            full_answer += token
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
    except Exception as llm_err:
        logger.error("llm_stream_error", error=str(llm_err), model=chat_model)
        yield f"data: {json.dumps({'type': 'error', 'content': f'The AI model encountered an error: {llm_err}'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    latency = round((time.monotonic() - t0) * 1000)
    logger.info(
        "chat_request",
        session_id=req.session_id,
        query=req.message[:100],
        strategy=strategy,
        chunks_retrieved=len(context_chunks),
        model=chat_model,
        latency_ms=latency,
    )

    # Persist conversation for analytics / future training
    try:
        log_conversation(
            session_id=req.session_id,
            question=req.message,
            answer=full_answer,
            strategy=strategy,
            sources=[s["source"] for s in sources],
            model=chat_model,
            latency_ms=latency,
        )
    except Exception as e:
        logger.error("conversation_log_error", error=str(e))

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@router.post("/chat")
@limiter.limit("10/minute")
async def chat(req: ChatRequest, request: Request):
    api_key = request.headers.get("X-API-Key", "")
    if settings.CHATBOT_API_KEY and api_key != settings.CHATBOT_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")

    return StreamingResponse(
        _generate_sse(req, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
