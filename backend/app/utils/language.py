"""
Language detection and query translation for multilingual support.
Handles:
  - Devanagari script Hindi
  - Hinglish (romanized Hindi mixed with English — Latin script)
  - Arabic, Chinese, Russian, and other non-Latin scripts
"""
import re
from app.utils.logger import get_logger

logger = get_logger()

# ── Script-based detection (non-Latin Unicode) ────────────────────────────────
_NON_LATIN = re.compile(
    r"[ऀ-ॿ"            # Devanagari (Hindi, Marathi, Sanskrit)
    r"؀-ۿ"              # Arabic / Urdu
    r"一-鿿"             # CJK Chinese
    r"Ѐ-ӿ"              # Cyrillic / Russian
    r"ঀ-৿਀-੿઀-૿"      # Bengali, Punjabi, Gujarati
    r"஀-௿ఀ-౿ಀ-೿ഀ-ൿ]"  # Tamil, Telugu, Kannada, Malayalam
)

# ── Hinglish detection (romanized Hindi words in Latin script) ────────────────
# Words that appear in Hindi conversation but NOT in standard English
_HINGLISH_WORDS = re.compile(
    r"\b("
    # ── Greetings / address ───────────────────────────────────────────────────
    r"bhai|yaar|dost|boss|guru|ji|sahab|jee|bhaiya|didi|arre|oye|oi|"
    r"namaste|namaskar|shukriya|dhanyawad|alvida|"

    # ── Question words ────────────────────────────────────────────────────────
    r"kya|kyun|kyunki|kaise|kahan|kab|kaun|kitna|kitne|kitni|"
    r"kaisa|kaisi|kaunsa|kaunsi|kahaan|"

    # ── Core auxiliaries / to-be ──────────────────────────────────────────────
    r"hai|hain|tha|thi|the|hoga|hogi|honge|hongi|"
    r"hua|hui|hue|hoke|hokar|"
    r"hona|ho|hote|hoti|hota|"
    r"raha|rahi|rahe|rahega|rahegi|rahenge|"

    # ── Common verbs ──────────────────────────────────────────────────────────
    r"karo|karna|karta|karti|karte|kar|kiya|kiye|karo|karein|"
    r"dena|dete|deta|deti|do|de|diya|diye|dijiye|"
    r"lena|leta|leti|lete|lo|liya|liye|lijiye|"
    r"jana|jata|jati|jate|jao|gaya|gayi|gaye|jaiye|"
    r"aana|aata|aati|aate|aao|aaya|aayi|aaye|aaiye|"
    r"batao|bata|batana|bataye|batayein|"
    r"samjhao|samjha|samjhana|samjhe|samajh|"
    r"dekho|dekh|dekhna|dekha|dekhe|dekhiye|"
    r"suno|sun|sunna|suna|sune|suniye|"
    r"bolo|bol|bolna|bola|boli|bole|"
    r"chahiye|chahta|chahti|chahte|chaho|"
    r"milta|milti|milte|milo|mila|mile|milenge|"
    r"nikla|nikli|nikle|nikalna|nikalte|"
    r"dikhta|dikhti|dikhte|dikha|dikhi|dikhe|dikhao|"
    r"lagta|lagti|lagte|laga|lagi|lage|"
    r"pata|malum|maalom|"
    r"rukna|ruko|ruk|"
    r"chalao|chalo|chale|chal|chalti|chalta|"

    # ── Negation / affirmation ────────────────────────────────────────────────
    r"nahi|nahin|naa|mat|na|bilkul nahi|"
    r"haan|han|ha|bilkul|zaroor|pakka|sahi|theek|"
    r"nope|haan ji|"

    # ── Pronouns ──────────────────────────────────────────────────────────────
    r"main|mai|mujhe|mujhko|mera|meri|mere|"
    r"tum|tu|tumhe|tumko|tera|teri|tere|"
    r"aap|aapko|aapka|aapki|aapke|"
    r"woh|wo|usse|use|usko|uska|uski|uske|"
    r"hum|humein|humko|humara|hamara|hamari|hamare|"
    r"yeh|ye|isko|isse|iska|iski|iske|"
    r"woh|unhe|unko|unka|unki|unke|"
    r"apna|apni|apne|khud|swayam|"

    # ── Postpositions / conjunctions ──────────────────────────────────────────
    r"mein|me|se|ko|ka|ki|ke|pe|par|tak|"
    r"aur|ya|lekin|magar|balki|isliye|isiliye|"
    r"toh|to|phir|fir|phir bhi|"
    r"jab|tab|jabse|tabse|jaise|waisa|"
    r"agar|aggar|yadi|warna|waise|"
    r"kyunki|isliye|wajah|"

    # ── Adverbs / intensifiers ────────────────────────────────────────────────
    r"bahut|bohot|bohat|bht|"
    r"zyada|jyada|thoda|thodi|"
    r"abhi|abhi tak|pehle|baad|baad mein|"
    r"jaldi|dhire|aaram se|"
    r"sirf|bas|hi|bhi|"
    r"accha|acha|achha|"
    r"galat|ghalat|"
    r"seedha|seedhi|"

    # ── Common nouns ──────────────────────────────────────────────────────────
    r"paisa|paise|rupaye|rupees|"
    r"kaam|kaamkaj|kaamkaaj|"
    r"baat|baatein|"
    r"log|logon|"
    r"cheez|chiz|cheezein|"
    r"jagah|jagha|"
    r"taraf|tarike|"
    r"samay|time pe|waqt|"
    r"saal|mahina|din|ghanta|"
    r"baar|dafa|"
    r"tarah|tarha|"
    r"matlab|matalab|"
    r"seedha|"

    # ── Numbers in Hindi ──────────────────────────────────────────────────────
    r"ek|do|teen|char|paanch|chhe|saat|aath|nau|das|"
    r"bees|tees|chalis|pachas|sau|hazaar|lakh|crore|"

    # ── Tech / blockchain Hinglish ────────────────────────────────────────────
    r"khareedna|khareed|kharidna|kharido|"
    r"bhejo|bhejna|bheja|"
    r"connect karo|connect karna|"
    r"invest kiya|invest karo|invest karna|"
    r"stake karo|stake karna|staking karo|"
    r"withdraw karo|transfer karo|"
    r"wallet mein|wallet ka|"
    r"transaction hua|transaction hogi|"

    # ── Fillers / sentence particles ──────────────────────────────────────────
    r"wala|wali|wale|waala|waali|waale|"
    r"sab|sabhi|sabko|sab log|"
    r"kuch|koi|kuch bhi|koi bhi|"
    r"iska|iski|iske|"
    r"unka|unki|unke|"
    r"yahan|wahan|idhar|udhar|"
    r"iske alawa|uske alawa|"
    r"shuruaat|shuru|khatam|"
    r"poora|puri|poori|"
    r"naya|nayi|naye|purana|purani|purane"
    r")\b",
    re.IGNORECASE,
)

# Minimum number of Hinglish word matches to classify as Hinglish
_HINGLISH_THRESHOLD = 2


def _hinglish_score(text: str) -> int:
    return len(_HINGLISH_WORDS.findall(text))


def is_non_english(text: str) -> bool:
    """True if text contains non-Latin script OR is Hinglish."""
    if _NON_LATIN.search(text):
        return True
    if _hinglish_score(text) >= _HINGLISH_THRESHOLD:
        return True
    return False


def detect_language(text: str) -> str:
    """Return language code: hi, ar, zh, ru, hinglish, other, en."""
    if re.search(r"[ऀ-ॿ]", text):
        return "hi"
    if re.search(r"[؀-ۿ]", text):
        return "ar"
    if re.search(r"[一-鿿]", text):
        return "zh"
    if re.search(r"[Ѐ-ӿ]", text):
        return "ru"
    if _NON_LATIN.search(text):
        return "other"
    if _hinglish_score(text) >= _HINGLISH_THRESHOLD:
        return "hinglish"
    return "en"


async def translate_to_english(text: str, model: str) -> str:
    """
    Translate query to English for retrieval using the router model (fast).
    Falls back to original text on failure or timeout.
    """
    from app.services.llm import call_llm_plain
    from app.config import settings
    # Ollama: use a small fast model; cloud providers: use the configured router model
    _TRANSLATE_MODEL = "qwen3:1.7b" if settings.LLM_PROVIDER == "ollama" else model
    try:
        result = await call_llm_plain(
            "You are a blockchain assistant translator. Convert the following Hinglish or Hindi text to English.\n"
            "Context: MST Blockchain platform — staking, tokenomics, smart contracts, security audits, wallet, DEX.\n"
            "Rules: Output ONLY the English translation. No explanation. No extra text.\n\n"
            f"Input: {text}\n"
            "English translation:",
            model=_TRANSLATE_MODEL,
        )
        # Strip common model artifacts
        result = result.strip().removeprefix("English translation:").strip()
        # Reject if model returned same text (failed translation)
        if result and result.lower() != text.lower():
            lang = detect_language(text)
            logger.info("query_translated", lang=lang, original=text[:80], english=result[:80])
            return result
    except Exception as e:
        logger.warning("translation_failed", error=str(e))
    return text
