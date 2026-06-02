import asyncio
import httpx
from app.config import settings

_BATCH_SIZE = 100
_MAX_RETRIES = 3


async def _embed_ollama_batch(texts: list[str], model: str) -> list[list[float]]:
    async with httpx.AsyncClient(timeout=60) as client:
        results: list[list[float]] = []
        for text in texts:
            for attempt in range(_MAX_RETRIES):
                try:
                    resp = await client.post(
                        f"{settings.OLLAMA_URL}/api/embeddings",
                        json={"model": model, "prompt": text},
                    )
                    resp.raise_for_status()
                    results.append(resp.json()["embedding"])
                    break
                except Exception as e:
                    if attempt == _MAX_RETRIES - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)
        return results


async def _embed_openai_batch(texts: list[str]) -> list[list[float]]:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    resp = await client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [item.embedding for item in resp.data]


async def _embed_jina_batch(texts: list[str], model: str) -> list[list[float]]:
    """Jina AI embeddings — free tier: 1M tokens/month. Sign up at jina.ai."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.jina.ai/v1/embeddings",
            headers={
                "Authorization": f"Bearer {settings.JINA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"input": texts, "model": model},
        )
        resp.raise_for_status()
    data = resp.json()
    # sort by index to guarantee order matches input
    return [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]


async def embed(texts: list[str], model: str | None = None) -> list[list[float]]:
    """Embed a list of texts. Batches automatically, retries on failure."""
    if not texts:
        return []

    results: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        if settings.EMBEDDING_PROVIDER == "openai":
            results.extend(await _embed_openai_batch(batch))
        elif settings.EMBEDDING_PROVIDER == "jina":
            embed_model = model or settings.EMBED_MODEL
            results.extend(await _embed_jina_batch(batch, embed_model))
        else:
            embed_model = model or settings.EMBED_MODEL
            results.extend(await _embed_ollama_batch(batch, embed_model))
    return results
