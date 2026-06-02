from app.config import settings

# TODO: MST-specific — inject chainId=4545, contract addresses, token symbols
SYSTEM_PROMPT_TEMPLATE = """You are MST Buddy, the official AI assistant for the MST Blockchain platform (Chain ID: 4545, Coin: MSTC).

You have access to official MST documentation, live blockchain data from mstscan.com, live token price from api.mstblockchain.com, whitepaper, tokenomics, RapidDex V2 (Uniswap V2 fork), staking, referral/MLM commissions, and wallet usage.

Rules:
- Answer directly and concisely based on the context provided. No bullet-point "Key Notes" or "Recommendations" sections unless explicitly asked.
- If the answer is not in the context, say it plainly in one sentence: "That information isn't available in my knowledge base."
- Never suggest contacting support as a primary answer — only if truly no data exists anywhere.
- When referencing amounts, percentages, or addresses, be exact. Format addresses and hashes in code blocks.
- For step-by-step tasks (wallet setup, staking), use numbered steps.
- Keep answers short unless the question requires detail.

Context:
{context}"""


def _format_context(chunks: list[dict]) -> str:
    if not chunks:
        return "No relevant context found."
    parts = []
    for i, c in enumerate(chunks, 1):
        source = c.get("source", "unknown")
        page = c.get("page")
        loc = f" (page {page})" if page else ""
        parts.append(f"[{i}] Source: {source}{loc}\n{c.get('text', '')}")
    return "\n\n---\n\n".join(parts)


_LANG_INSTRUCTIONS = {
    "hi": (
        "IMPORTANT: The user is writing in Hindi (Devanagari script). "
        "You MUST respond entirely in Hindi using Devanagari script."
    ),
    "hinglish": (
        "IMPORTANT: The user is writing in Hinglish (Roman script — Hindi words spelled in English letters, mixed with English). "
        "You MUST respond in the SAME Hinglish Roman script style. "
        "Write Hindi words in Roman letters (e.g. 'kya', 'hai', 'nahi', 'bhai', 'hua'). "
        "Do NOT use Devanagari script (no ह, क, य etc.). "
        "Keep the same casual tone as the user."
    ),
    "ar": (
        "IMPORTANT: The user is writing in Arabic. "
        "You MUST respond entirely in Arabic."
    ),
    "zh": (
        "IMPORTANT: The user is writing in Chinese. "
        "You MUST respond entirely in Chinese."
    ),
    "ru": (
        "IMPORTANT: The user is writing in Russian. "
        "You MUST respond entirely in Russian."
    ),
    "other": (
        "IMPORTANT: Respond in the same language the user used."
    ),
}

def build_system_prompt(chunks: list[dict], user_lang: str = "en") -> str:
    context = _format_context(chunks)
    # Language instruction goes FIRST so the model can't ignore it
    lang_prefix = ""
    if user_lang in _LANG_INSTRUCTIONS:
        lang_prefix = f"{_LANG_INSTRUCTIONS[user_lang]}\n\n"
    return lang_prefix + SYSTEM_PROMPT_TEMPLATE.format(context=context)


_LANG_SUFFIX = {
    "hi":       "\n\n[INSTRUCTION: Reply in Hindi using Devanagari script only.]",
    "hinglish": "\n\n[INSTRUCTION: Reply in Hinglish — Roman script only. Write Hindi words in English letters like 'kya', 'hai', 'nahi', 'bhai'. Do NOT use Devanagari. Keep it casual.]",
    "ar":       "\n\n[INSTRUCTION: Reply in Arabic.]",
    "zh":       "\n\n[INSTRUCTION: Reply in Chinese.]",
    "ru":       "\n\n[INSTRUCTION: Reply in Russian.]",
}

def build_messages(
    user_message: str,
    history: list[dict],
    max_turns: int | None = None,
    user_lang: str = "en",
) -> list[dict]:
    limit = (max_turns or settings.MAX_HISTORY_TURNS) * 2
    trimmed = history[-limit:] if len(history) > limit else history
    messages = [{"role": h["role"], "content": h["content"]} for h in trimmed]
    # Append language instruction directly to user message for reliable enforcement
    final_message = user_message + _LANG_SUFFIX.get(user_lang, "")
    messages.append({"role": "user", "content": final_message})
    return messages
