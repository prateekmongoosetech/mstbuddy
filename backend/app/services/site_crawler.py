"""
MST website crawler.
- Uses Playwright for JS-rendered SPAs (mstblockchain.com)
- Falls back to httpx+BeautifulSoup for plain HTML (docs.mstblockchain.com)
- Deep link following up to CRAWL_DEPTH levels
"""

from app.config import settings


def _get_seed_urls() -> list[str]:
    return [u.strip() for u in settings.MST_WEBSITE_URLS.split(",") if u.strip()]


def _get_allowed_domains() -> set[str]:
    return {d.strip() for d in settings.ALLOWED_CRAWL_DOMAINS.split(",") if d.strip()}


# Domains that are SPAs — need Playwright rendering
_SPA_DOMAINS = {"mstblockchain.com", "www.mstblockchain.com"}


async def crawl_mst_website(embed_model: str | None = None) -> None:
    seeds = _get_seed_urls()
    allowed = _get_allowed_domains()

    # Separate SPA seeds from plain HTML seeds
    spa_seeds = [u for u in seeds if any(d in u for d in _SPA_DOMAINS)]
    html_seeds = [u for u in seeds if not any(d in u for d in _SPA_DOMAINS)]

    total = 0

    # Playwright deep crawl for SPA sites (optional — falls back to HTML crawler)
    if spa_seeds:
        try:
            from app.services.playwright_crawler import playwright_crawl
            n = await playwright_crawl(
                seed_urls=spa_seeds,
                allowed_domains=allowed,
                max_pages=settings.CRAWL_MAX_PAGES,
                max_depth=settings.CRAWL_DEPTH,
                embed_model=embed_model,
            )
            total += n
        except (ImportError, Exception) as e:
            print(f"[site_crawler] Playwright unavailable ({e}), falling back to HTML crawler")
            from app.services.html_crawler import html_crawl
            n = await html_crawl(
                seed_urls=spa_seeds,
                allowed_domains=allowed,
                max_pages=settings.CRAWL_MAX_PAGES,
                max_depth=settings.CRAWL_DEPTH,
                embed_model=embed_model,
            )
            total += n

    # httpx crawler for plain HTML / docs sites
    if html_seeds:
        from app.services.html_crawler import html_crawl
        n = await html_crawl(
            seed_urls=html_seeds,
            allowed_domains=allowed,
            max_pages=settings.CRAWL_MAX_PAGES,
            max_depth=settings.CRAWL_DEPTH,
            embed_model=embed_model,
        )
        total += n

    print(f"[site_crawler] Total chunks ingested: {total}")
