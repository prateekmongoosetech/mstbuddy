"""
Auto-selects the best chat, embedding, and router models.
- Ollama: queries local Ollama instance and picks the best available model.
- OpenRouter / Claude: uses env-configured model names directly (no local discovery).
"""

import httpx
from app.config import settings

CHAT_MODEL_PRIORITY = [
    "qwen3:14b", "qwen3:8b", "qwen3:4b", "qwen3:1.7b", "qwen3:0.6b",
    "llama3.3:70b", "llama3.1:70b", "llama3.1:8b", "llama3:8b", "llama3:7b",
    "mistral:7b", "mistral", "mixtral:8x7b",
    "deepseek-r1:14b", "deepseek-r1:8b", "deepseek-r1:7b",
    "phi4:14b", "phi3:14b", "phi3:3.8b",
    "gemma3:12b", "gemma3:4b", "gemma2:9b", "gemma2:2b",
    "command-r:35b", "command-r",
]

EMBED_MODEL_PRIORITY = [
    "nomic-embed-text",
    "mxbai-embed-large",
    "all-minilm",
    "snowflake-arctic-embed",
    "bge-m3",
    "bge-large",
]

ROUTER_MODEL_PRIORITY = [
    "qwen3:1.7b", "qwen3:0.6b", "qwen3:4b", "qwen3:8b",
    "phi3:3.8b", "gemma2:2b", "llama3.2:1b", "llama3.2:3b",
    "mistral:7b", "llama3:8b",
]

EMBED_DIMS_MAP: dict[str, int] = {
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
    "all-minilm": 384,
    "snowflake-arctic-embed": 1024,
    "bge-m3": 1024,
    "bge-large": 1024,
    "text-embedding-3-small": 1536,
    "text-embedding-ada-002": 1536,
    # Jina models
    "jina-embeddings-v2-base-en": 768,
    "jina-embeddings-v2-small-en": 512,
    "jina-embeddings-v3": 1024,
    "jina-clip-v1": 768,
}


_NGROK_HEADERS = {"ngrok-skip-browser-warning": "true"}

async def list_ollama_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.OLLAMA_URL}/api/tags", headers=_NGROK_HEADERS)
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        print(f"[model_selector] Cannot reach Ollama at {settings.OLLAMA_URL}: {e}")
        return []


def pick_best(available: list[str], priority: list[str]) -> str | None:
    available_lower = {m.lower(): m for m in available}
    for candidate in priority:
        if candidate in available:
            return candidate
        for name, original in available_lower.items():
            if name.startswith(candidate.lower()):
                return original
    return None


def get_embed_dims(model_name: str) -> int:
    lower = model_name.lower()
    for key, dims in EMBED_DIMS_MAP.items():
        if key in lower:
            return dims
    return 768


def _banner(chat_model: str, embed_model: str, router_model: str, embed_dims: int, provider: str) -> None:
    pad = lambda s, n: (s or "")[:n].ljust(n)
    print(f"""
╔══════════════════════════════════════════╗
║        MST Buddy — Model Selection       ║
╠══════════════════════════════════════════╣
║  Provider   : {pad(provider, 27)}║
║  Chat LLM   : {pad(chat_model, 27)}║
║  Embeddings : {pad(embed_model, 27)}║
║  Router     : {pad(router_model, 27)}║
║  Embed dims : {pad(str(embed_dims), 27)}║
╚══════════════════════════════════════════╝""")


async def auto_select_models() -> dict:
    provider = settings.LLM_PROVIDER

    # ── Cloud providers: use env-configured models directly ───────────────────
    if provider in ("claude", "openrouter"):
        chat_model = settings.LLM_MODEL
        router_model = settings.ROUTER_MODEL or settings.LLM_MODEL
        embed_model = settings.EMBED_MODEL
        embed_dims = get_embed_dims(embed_model)

        if not chat_model:
            raise RuntimeError(
                f"LLM_PROVIDER={provider} but LLM_MODEL is not set in .env"
            )
        if provider == "openrouter" and not settings.OPENROUTER_API_KEY:
            raise RuntimeError("LLM_PROVIDER=openrouter but OPENROUTER_API_KEY is not set")
        if settings.EMBEDDING_PROVIDER == "jina" and not settings.JINA_API_KEY:
            raise RuntimeError("EMBEDDING_PROVIDER=jina but JINA_API_KEY is not set")

        _banner(chat_model, embed_model, router_model, embed_dims, provider)
        return {
            "chat_model": chat_model,
            "embed_model": embed_model,
            "router_model": router_model,
            "embed_dims": embed_dims,
            "all_models": [chat_model],
        }

    # ── Ollama: auto-discover from local instance ─────────────────────────────
    available = await list_ollama_models()

    if not available:
        raise RuntimeError(
            f"No Ollama models found. Is Ollama running?\n"
            f"Tried: {settings.OLLAMA_URL}\n"
            "Fix: ollama pull qwen3:4b && ollama pull nomic-embed-text"
        )

    chat_model = pick_best(available, CHAT_MODEL_PRIORITY)
    embed_model = pick_best(available, EMBED_MODEL_PRIORITY)
    router_model = pick_best(available, ROUTER_MODEL_PRIORITY)

    if not embed_model and chat_model:
        embed_model = chat_model
        print("[model_selector] WARNING: No dedicated embedding model found. Using chat model (quality degraded).")

    if not chat_model:
        raise RuntimeError(
            f"No supported chat model found in Ollama.\n"
            f"Available: {available}\n"
            "Fix: ollama pull qwen3:4b"
        )

    final_router = router_model or chat_model
    embed_dims = get_embed_dims(embed_model) if embed_model else 768

    _banner(chat_model, embed_model, final_router, embed_dims, "ollama")
    print("  Available models:")
    for m in available:
        print(f"    • {m}")

    return {
        "chat_model": chat_model,
        "embed_model": embed_model,
        "router_model": final_router,
        "embed_dims": embed_dims,
        "all_models": available,
    }
