"""
Playwright-based SPA crawler.
Renders JavaScript pages (React/Vue/Angular) and extracts clean text.
Falls back to httpx+BeautifulSoup for plain HTML pages.
"""

import asyncio
import re
from urllib.parse import urljoin, urlparse
from app.services.ingestion import ingest_text_chunks

_NOISE_TAGS = ["script", "style", "noscript", "iframe", "svg"]
_SKIP_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
                    ".mp4", ".mp3", ".zip", ".glb", ".woff", ".woff2", ".ttf"}
_SKIP_PATTERNS = re.compile(r"(linkedin|twitter|facebook|instagram|t\.me|youtube|"
                             r"walletconnect|googleapis|gstatic|cloudflare|imagekit|"
                             r"imagedelivery|px\.ads|googletagmanager|analytics|"
                             r"firebase|walletconnect|pulse\.wallet|web3modal)", re.I)


def _is_crawlable(url: str, allowed_domains: set[str]) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        if parsed.netloc not in allowed_domains:
            return False
        ext = parsed.path.rsplit(".", 1)[-1].lower() if "." in parsed.path.split("/")[-1] else ""
        if f".{ext}" in _SKIP_EXTENSIONS:
            return False
        if _SKIP_PATTERNS.search(url):
            return False
        return True
    except Exception:
        return False


async def _render_page(page, url: str) -> tuple[str, list[str]]:
    """
    Navigate to url, wait for JS to render, extract text + internal links.
    Returns (clean_text, [absolute_href, ...])
    """
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        # Wait for React/Vue to hydrate content
        await asyncio.sleep(4)
    except Exception as e:
        return f"[render error: {e}]", []

    # Extract text
    text = await page.evaluate("""() => {
        const noise = ['script','style','noscript','svg','iframe'];
        noise.forEach(t => document.querySelectorAll(t).forEach(e => e.remove()));
        const raw = document.body.innerText || document.body.textContent || '';
        return raw.replace(/\\n{3,}/g, '\\n\\n').trim();
    }""")

    # Extract all internal links
    hrefs = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(h => h.startsWith('http'));
    }""")

    # Resolve relative links
    base = url.rstrip("/")
    links = []
    for h in hrefs:
        abs_url = urljoin(base, h).split("#")[0].split("?")[0]
        links.append(abs_url)

    return text, links


async def playwright_crawl(
    seed_urls: list[str],
    allowed_domains: set[str],
    max_pages: int = 80,
    max_depth: int = 3,
    embed_model: str | None = None,
) -> int:
    """
    BFS deep crawler using Playwright for JS rendering.
    Ingests all discovered pages into Qdrant.
    Returns total chunks ingested.
    """
    from playwright.async_api import async_playwright

    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(u.rstrip("/"), 0) for u in seed_urls]
    total_chunks = 0

    print(f"[playwright_crawler] Starting deep crawl: {len(seed_urls)} seeds, "
          f"max_pages={max_pages}, max_depth={max_depth}, domains={allowed_domains}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; MSTBuddy-Crawler/1.0)",
            java_script_enabled=True,
        )
        page = await context.new_page()
        # Block heavy resources to speed up crawl
        await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,mp4,mp3,woff,woff2,ttf,glb,gltf}",
                         lambda route: route.abort())

        while queue and len(visited) < max_pages:
            url, depth = queue.pop(0)
            norm = url.rstrip("/")
            if norm in visited:
                continue
            visited.add(norm)

            print(f"[playwright_crawler] ({len(visited)}/{max_pages}) depth={depth} {url}")

            text, links = await _render_page(page, url)

            if text and len(text.strip()) > 100:
                n = await ingest_text_chunks(
                    text=text,
                    metadata={
                        "source": url,
                        "type": "web_crawl_spa",
                        "title": url.split("/")[-1] or urlparse(url).netloc,
                    },
                    embed_model=embed_model,
                )
                total_chunks += n
                print(f"[playwright_crawler] Ingested {url} → {n} chunks")

            # Enqueue discovered links
            if depth < max_depth:
                for link in links:
                    norm_link = link.rstrip("/")
                    if norm_link not in visited and _is_crawlable(link, allowed_domains):
                        queue.append((link, depth + 1))
                        # De-duplicate queue entries
                        queue = list({item[0]: item for item in queue}.values())

            await asyncio.sleep(0.3)

        await browser.close()

    print(f"[playwright_crawler] Done. {len(visited)} pages, {total_chunks} chunks.")
    return total_chunks
