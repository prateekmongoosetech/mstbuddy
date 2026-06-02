"""
Plain-HTML crawler using httpx + BeautifulSoup.
Used for static/SSR sites like docs.mstblockchain.com.
"""

import asyncio
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from app.services.ingestion import ingest_text_chunks

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MSTBuddy-Crawler/1.0)"}


async def html_crawl(
    seed_urls: list[str],
    allowed_domains: set[str],
    max_pages: int = 50,
    max_depth: int = 3,
    embed_model: str | None = None,
) -> int:
    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(u, 0) for u in seed_urls]
    total_chunks = 0

    print(f"[html_crawler] Starting: {seed_urls}, max_pages={max_pages}, depth={max_depth}")

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        while queue and len(visited) < max_pages:
            url, depth = queue.pop(0)
            norm = url.rstrip("/")
            if norm in visited:
                continue
            visited.add(norm)

            try:
                resp = await client.get(url, headers=_HEADERS)
                if "text/html" not in resp.headers.get("content-type", ""):
                    continue

                soup = BeautifulSoup(resp.text, "lxml")
                title = soup.title.string if soup.title else url
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()

                text = soup.get_text(separator="\n", strip=True)
                lines = [l for l in text.splitlines() if l.strip()]
                clean = "\n".join(lines)

                if clean.strip():
                    n = await ingest_text_chunks(
                        text=clean,
                        metadata={"source": url, "type": "web_crawl", "title": title},
                        embed_model=embed_model,
                    )
                    total_chunks += n
                    print(f"[html_crawler] Indexed {url} → {n} chunks")

                if depth < max_depth:
                    for a in soup.select("a[href]"):
                        href = urljoin(url, a.get("href", "")).split("#")[0].split("?")[0]
                        parsed = urlparse(href)
                        if (
                            parsed.scheme in ("http", "https")
                            and parsed.netloc in allowed_domains
                            and href.rstrip("/") not in visited
                        ):
                            queue.append((href, depth + 1))

                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"[html_crawler] Error {url}: {e}")

    print(f"[html_crawler] Done. {len(visited)} pages, {total_chunks} chunks.")
    return total_chunks
