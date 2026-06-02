"""
MST Blockchain explorer integration via mstscan.com (Blockscout).
Uses GraphQL API at /api/v1/graphql for rich queries,
falls back to REST API v2 for stats/network data.
"""
import re
import httpx
from app.utils.logger import get_logger

logger = get_logger()

GRAPHQL_URL = "https://mstscan.com/api/v1/graphql"
REST_API_URL = "https://mstscan.com/api/v2"
EXPLORER_URL = "https://mstscan.com"
_HEADERS = {"User-Agent": "Mozilla/5.0 MST-Buddy-Bot/1.0", "Content-Type": "application/json"}
_TIMEOUT = 10


async def _graphql(query: str, variables: dict | None = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(GRAPHQL_URL, json=payload, headers=_HEADERS)
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            raise ValueError(f"GraphQL errors: {data['errors']}")
        return data.get("data", {})


async def _rest(path: str) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{REST_API_URL}{path}", headers=_HEADERS)
        r.raise_for_status()
        return r.json()


# ── GraphQL queries ────────────────────────────────────────────────────────────

_BLOCK_FIELDS = "number timestamp minerHash gasUsed gasLimit hash size totalDifficulty"

async def get_block_gql(number: int) -> dict:
    data = await _graphql(
        f"{{ block(number: {number}) {{ {_BLOCK_FIELDS} }} }}"
    )
    return data.get("block") or {}


async def get_transaction_gql(tx_hash: str) -> dict:
    data = await _graphql(
        """query($hash: FullHash!) {
          transaction(hash: $hash) {
            blockNumber hash status
            fromAddressHash toAddressHash
            value gasUsed error
          }
        }""",
        {"hash": tx_hash},
    )
    return data.get("transaction") or {}


async def get_address_gql(address: str) -> dict:
    data = await _graphql(
        """query($hash: AddressHash!) {
          address(hash: $hash) {
            hash fetchedCoinBalance contractCode
          }
        }""",
        {"hash": address},
    )
    return data.get("address") or {}


# ── REST API (stats not in GraphQL schema) ─────────────────────────────────────

async def get_network_stats() -> dict:
    try:
        return await _rest("/stats")
    except Exception as e:
        logger.warning("mstscan_stats_failed", error=str(e))
        return {}


# ── Context builder ────────────────────────────────────────────────────────────

async def get_explorer_context(query: str) -> str:
    parts: list[str] = []
    q_lower = query.lower()

    # Network stats — always useful for explorer queries
    stats = await get_network_stats()
    if stats:
        parts.append(
            "MST Mainnet Network Stats (live from mstscan.com):\n"
            f"- Total blocks: {stats.get('total_blocks', 'N/A')}\n"
            f"- Total transactions: {stats.get('total_transactions', 'N/A')}\n"
            f"- Average block time: {stats.get('average_block_time', 'N/A')} ms\n"
            f"- Total addresses: {stats.get('total_addresses', 'N/A')}\n"
            f"- Network utilization: {stats.get('network_utilization_percentage', 'N/A')}%"
        )

    # Genesis / launch date queries → fetch block #1 via GraphQL
    if any(w in q_lower for w in ["first", "genesis", "launch", "start", "creat", "when", "date", "origin", "mainnet"]):
        try:
            b = await get_block_gql(1)
            if b:
                parts.append(
                    f"\nMST Mainnet Genesis Block (Block #1) via mstscan.com GraphQL:\n"
                    f"- Launch date: {b.get('timestamp', 'N/A')} UTC\n"
                    f"- Block hash: {b.get('hash', 'N/A')}\n"
                    f"- Miner/Validator: {b.get('minerHash', 'N/A')}\n"
                    f"- Gas used: {b.get('gasUsed', 'N/A')} / Gas limit: {b.get('gasLimit', 'N/A')}\n"
                    f"- Block size: {b.get('size', 'N/A')} bytes\n"
                    f"- Explorer link: {EXPLORER_URL}/block/1"
                )
        except Exception as e:
            logger.warning("mstscan_block1_failed", error=str(e))

    # Specific block number query
    block_match = re.search(r"block\s*#?\s*(\d+)", query, re.IGNORECASE)
    if block_match:
        num = int(block_match.group(1))
        if num != 1:
            try:
                b = await get_block_gql(num)
                if b:
                    parts.append(
                        f"\nBlock #{num} on MST Mainnet:\n"
                        f"- Timestamp: {b.get('timestamp', 'N/A')}\n"
                        f"- Gas used: {b.get('gasUsed', 'N/A')}\n"
                        f"- Miner: {b.get('minerHash', 'N/A')}\n"
                        f"- Hash: {b.get('hash', 'N/A')}\n"
                        f"- Explorer link: {EXPLORER_URL}/block/{num}"
                    )
            except Exception as e:
                logger.warning("mstscan_block_failed", block=num, error=str(e))

    # Transaction hash lookup (0x + 64 hex chars)
    tx_match = re.search(r"0x[0-9a-fA-F]{64}", query)
    if tx_match:
        tx_hash = tx_match.group(0)
        try:
            tx = await get_transaction_gql(tx_hash)
            if tx:
                parts.append(
                    f"\nTransaction {tx_hash}:\n"
                    f"- Status: {tx.get('status', 'N/A')}\n"
                    f"- Block: {tx.get('blockNumber', 'N/A')}\n"
                    f"- From: {tx.get('fromAddressHash', 'N/A')}\n"
                    f"- To: {tx.get('toAddressHash', 'N/A')}\n"
                    f"- Value: {tx.get('value', '0')} wei\n"
                    f"- Explorer link: {EXPLORER_URL}/tx/{tx_hash}"
                )
        except Exception as e:
            logger.warning("mstscan_tx_failed", tx=tx_hash, error=str(e))

    # Wallet/contract address lookup (0x + 40 hex chars, not tx hash)
    addr_match = re.search(r"0x[0-9a-fA-F]{40}(?![0-9a-fA-F])", query)
    if addr_match:
        addr = addr_match.group(0)
        try:
            a = await get_address_gql(addr)
            if a:
                is_contract = bool(a.get("contractCode"))
                parts.append(
                    f"\nAddress {addr} on MST Mainnet:\n"
                    f"- Balance: {a.get('fetchedCoinBalance', 'N/A')} MSTC\n"
                    f"- Type: {'Smart Contract' if is_contract else 'Wallet'}\n"
                    f"- Explorer link: {EXPLORER_URL}/address/{addr}"
                )
        except Exception as e:
            logger.warning("mstscan_addr_failed", addr=addr, error=str(e))

    return "\n".join(parts) if parts else "No blockchain explorer data available from mstscan.com."
