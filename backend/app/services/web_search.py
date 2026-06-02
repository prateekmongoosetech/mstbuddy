import hashlib
import json
import httpx
from bs4 import BeautifulSoup
from app.config import settings

DDGO_URL = "https://html.duckduckgo.com/html/"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MSTBuddy/1.0; +https://mstchain.io)"}


async def _get_redis():
    try:
        import redis.asyncio as aioredis
        return aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception:
        return None


async def ddgo_search(query: str, max_results: int | None = None) -> list[dict]:
    n = max_results or settings.WEB_SEARCH_MAX_RESULTS
    cache_key = f"websearch:{hashlib.sha256(query.encode()).hexdigest()}"

    redis = await _get_redis()
    if redis:
        cached = await redis.get(cache_key)
        if cached:
            await redis.aclose()
            return json.loads(cached)

    results: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(DDGO_URL, data={"q": query}, headers=_HEADERS)
        soup = BeautifulSoup(resp.text, "lxml")
        for r in soup.select(".result__body")[:n]:
            title_el = r.select_one(".result__title")
            url_el = r.select_one(".result__url")
            snippet_el = r.select_one(".result__snippet")
            if title_el and url_el:
                raw_url = url_el.get_text(strip=True).strip()
                if not raw_url.startswith("http"):
                    raw_url = "https://" + raw_url
                results.append(
                    {
                        "title": title_el.get_text(strip=True),
                        "url": raw_url,
                        "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                    }
                )
    except Exception as e:
        print(f"[web_search] DuckDuckGo search failed: {e}")

    if redis:
        await redis.setex(cache_key, 3600, json.dumps(results))
        await redis.aclose()

    return results


async def fetch_and_extract(url: str) -> str:
    """Fetch a URL and return clean readable text (max 3000 chars)."""
    cache_key = f"urlcache:{hashlib.sha256(url.encode()).hexdigest()}"

    redis = await _get_redis()
    if redis:
        cached = await redis.get(cache_key)
        if cached:
            await redis.aclose()
            return cached

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=_HEADERS)
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [l for l in text.splitlines() if l.strip()]
        result = "\n".join(lines)[:3000]
    except Exception as e:
        result = f"[fetch_and_extract] Could not fetch {url}: {e}"

    if redis:
        await redis.setex(cache_key, 21600, result)
        await redis.aclose()

    return result
