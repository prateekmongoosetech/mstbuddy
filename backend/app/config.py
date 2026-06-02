from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── LLM Provider ──────────────────────────────────────────────────────────
    LLM_PROVIDER: str = "ollama"                  # "ollama" | "claude" | "openrouter"
    LLM_MODEL: str = "qwen3:8b"
    ROUTER_MODEL: str = "qwen3:8b"
    OLLAMA_URL: str = "http://host.docker.internal:11434"

    # ── Claude (only needed if LLM_PROVIDER=claude) ───────────────────────────
    ANTHROPIC_API_KEY: str = ""

    # ── OpenRouter (only needed if LLM_PROVIDER=openrouter) ──────────────────
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_SITE_URL: str = "https://mstblockchain.com"
    OPENROUTER_SITE_NAME: str = "MST Buddy"

    # ── Embeddings ────────────────────────────────────────────────────────────
    EMBEDDING_PROVIDER: str = "ollama"            # "ollama" | "openai" | "jina"
    EMBED_MODEL: str = "nomic-embed-text"
    OPENAI_API_KEY: str = ""
    JINA_API_KEY: str = ""                        # free 1M tokens/month at jina.ai

    # ── Qdrant ────────────────────────────────────────────────────────────────
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_API_KEY: str = ""                      # required for Qdrant Cloud
    QDRANT_COLLECTION: str = "mst_docs"
    TOP_K: int = 6

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379"

    # ── Web Search & Crawl ────────────────────────────────────────────────────
    MST_WEBSITE_URLS: str = "https://mstchain.io,https://rapiddex.io"
    CRAWL_ON_STARTUP: bool = True
    CRAWL_MAX_PAGES: int = 50
    CRAWL_DEPTH: int = 2
    ALLOWED_CRAWL_DOMAINS: str = "mstchain.io,rapiddex.io"
    WEB_SEARCH_MAX_RESULTS: int = 4
    WEB_SEARCH_FETCH_CONTENT: bool = True

    # ── Security ──────────────────────────────────────────────────────────────
    CHATBOT_API_KEY: str = "change-me"
    CORS_ORIGINS: str = "http://localhost:3000"

    # ── Misc ──────────────────────────────────────────────────────────────────
    MAX_HISTORY_TURNS: int = 10
    RERANK_ENABLED: bool = False
    COHERE_API_KEY: str = ""
    VERSION: str = "1.0.0"

    class Config:
        env_file = ".env"


settings = Settings()
