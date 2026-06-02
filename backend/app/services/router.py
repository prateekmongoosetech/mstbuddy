import json
import re
from app.services.llm import call_llm_json

# TODO: MST-specific — update this URL if the portal moves
MST_PORTAL_URL = "https://mstblockchain.com/portal/"

# MST-specific terms that must always go to local Qdrant — bypass the LLM router
_MST_QDRANT_KEYWORDS = re.compile(
    r"\b(saral|wasmify|wasm\s*ify|rapiddex|rapid\s*dex|mst\s+blockchain|mst\s+chain|"
    r"fractional\s+validator|ambassador\s+program|mst\s+grant|mst\s+staking|"
    r"mst\s+token|mst\s+wallet|mst\s+testnet|mst\s+mainnet|mst\s+rpc|"
    r"mst\s+whitepaper|mst\s+tokenomics|mst\s+roadmap|mst\s+team|mst\s+founder|"
    r"chain\s+id\s+45|nft\s+ticketing|on.chain\s+certificate|"
    r"supply\s+chain\s+transparency|tokenized\s+real\s+estate|insurance\s+automation|"
    r"post.quantum\s+cryptography|mst\s+dex|mst\s+swap|"
    r"who\s+(is|are|owns?|founded|created|built|made|runs?|leads?)\s+(mst|the\s+mst)|"
    r"what\s+is\s+(mst|the\s+mst))\b",
    re.IGNORECASE,
)

MSTSCAN_API = "https://mstscan.com/api/v2"

# Blockchain explorer queries — route to mstscan.com API
_MST_EXPLORER_KEYWORDS = re.compile(
    r"\b(block\s*#?\d+|first\s+block|genesis\s+block|block\s+height|latest\s+block|"
    r"transaction\s+hash|tx\s+hash|txn?\s+0x[0-9a-fA-F]+|"
    r"0x[0-9a-fA-F]{40,}|"  # wallet/tx addresses
    r"total\s+(blocks?|transactions?|txns?)|"
    r"when\s+(was|did)\s+(mst|the\s+mst).*(launch|start|begin|creat|deploy|mainnet)|"
    r"(mainnet|chain)\s+(launch|start|creat|deploy)\s+date|"
    r"first\s+(block|transaction|tx)|genesis|block\s+time|"
    r"validator\s+count|active\s+validators?|network\s+stats|"
    r"mstscan|block\s+explorer)\b",
    re.IGNORECASE,
)

# Keywords that indicate the user wants live MST price / market data
_MST_PRICE_KEYWORDS = re.compile(
    r"\b(price|prices|rate|rates|cost|worth|value|market\s*cap|mcap|"
    r"current\s+mst|mst\s+price|mst\s+rate|mst\s+value|how\s+much\s+is\s+mst|"
    r"token\s+price|coin\s+price|trading|chart|ath|all.time.high)\b",
    re.IGNORECASE,
)

ROUTER_PROMPT = """You are a query router for the MST Blockchain chatbot.
Given the user query, decide the best retrieval strategy.
Respond ONLY with valid JSON, no explanation:

{{
  "strategy": "qdrant" | "web_search" | "fetch_url" | "combined",
  "web_query": "<optimized search query if strategy involves web, else null>",
  "url": "<URL to fetch if strategy is fetch_url, else null>"
}}

Rules:
- DEFAULT to "qdrant" when in doubt — prefer local knowledge over web search
- Use "qdrant" for ANY question about MST Blockchain products, protocols, or features:
  - SARAL Protocol, WASMify, RapidDex V2, MST token, staking, referral/MLM, smart contracts, wallet
  - Fractional Validator, Ambassador program, Grant program, NFT Ticketing, On-Chain Certificate
  - Supply Chain, Tokenized Real Estate, Insurance Automation, KYC/AML, team members, ownership
  - Chain ID 4545, RPC, developer docs, whitepaper, tokenomics, roadmap, events
- Use "web_search" ONLY for clearly external topics: general blockchain news, non-MST projects, price comparisons with BTC/ETH
- Use "fetch_url" if the user message contains a URL (http:// or https://)
- Use "combined" if the question explicitly asks for both MST knowledge AND current news/market data
- For "web_query", rephrase as an optimized search engine query

User query: {query}"""

_URL_RE = re.compile(r"https?://[^\s]+")


def _extract_url(text: str) -> str | None:
    match = _URL_RE.search(text)
    return match.group(0) if match else None


async def route_query(query: str, router_model: str) -> dict:
    # Fast-path: URL pasted in message → fetch that URL directly
    url = _extract_url(query)
    if url:
        return {"strategy": "fetch_url", "web_query": None, "url": url}

    # Fast-path: MST price / market data → call the live MST API directly
    if _MST_PRICE_KEYWORDS.search(query):
        return {"strategy": "mst_price", "web_query": None, "url": None}

    # Fast-path: blockchain explorer queries → fetch live data from mstscan.com
    if _MST_EXPLORER_KEYWORDS.search(query):
        return {"strategy": "mst_explorer", "web_query": None, "url": None}

    # Fast-path: known MST-specific terms → always use local Qdrant knowledge
    if _MST_QDRANT_KEYWORDS.search(query):
        return {"strategy": "qdrant", "web_query": None, "url": None}

    try:
        raw = await call_llm_json(
            prompt=ROUTER_PROMPT.format(query=query), router_model=router_model
        )
        result = json.loads(raw)
        # Validate strategy field
        valid = {"qdrant", "web_search", "fetch_url", "combined"}
        if result.get("strategy") not in valid:
            result["strategy"] = "qdrant"
        return result
    except Exception as e:
        print(f"[router] Routing failed, defaulting to qdrant: {e}")
        return {"strategy": "qdrant", "web_query": None, "url": None}
