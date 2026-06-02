"""
Fetches live MST token price from official MST API endpoints.
Discovered by intercepting portal network requests.

Endpoints:
  GET https://api.mstblockchain.com/fractions/price  → raw price in INR
  GET https://api.mstblockchain.com/fiat-pricing     → USD/INR conversion rate
"""

import asyncio
import httpx
from datetime import datetime, timezone

MST_PRICE_URL = "https://api.mstblockchain.com/fractions/price"
MST_FIAT_URL = "https://api.mstblockchain.com/fiat-pricing"

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MSTBuddy/1.0)"}


async def get_mst_price() -> dict:
    """
    Returns live MST price from official API.
    {
        "price_inr": float,
        "price_usd": float | None,
        "inr_per_usd": float,
        "fetched_at": str
    }
    """
    async with httpx.AsyncClient(timeout=10) as client:
        price_resp, fiat_resp = await asyncio.gather(
            client.get(MST_PRICE_URL, headers=_HEADERS),
            client.get(MST_FIAT_URL, headers=_HEADERS),
        )

    price_inr = float(price_resp.text.strip())
    fiat_data = fiat_resp.json()
    inr_per_usd = float(fiat_data["data"]["value"])
    price_usd = round(price_inr / inr_per_usd, 6) if inr_per_usd else None

    return {
        "price_inr": price_inr,
        "price_usd": price_usd,
        "inr_per_usd": inr_per_usd,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


async def get_mst_price_context() -> str:
    """Formatted string ready to inject into RAG context."""
    try:
        data = await get_mst_price()
        return (
            f"Live MST Token Price (fetched at {data['fetched_at']}):\n"
            f"  Price (INR): ₹{data['price_inr']:,.4f}\n"
            f"  Price (USD): ${data['price_usd']:,.6f}\n"
            f"  USD/INR rate used: {data['inr_per_usd']}\n"
            f"  Source: api.mstblockchain.com (official MST API)"
        )
    except Exception as e:
        return f"[MST price currently unavailable: {e}]"
