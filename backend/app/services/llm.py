import httpx
import json
from typing import AsyncIterator
from app.config import settings

_NGROK_HEADERS = {"ngrok-skip-browser-warning": "true"}


# ── Ollama ────────────────────────────────────────────────────────────────────

async def stream_ollama(
    messages: list[dict], system: str, model: str
) -> AsyncIterator[str]:
    payload = {
        "model": model,
        "stream": True,
        "options": {"temperature": 0.2, "num_ctx": 8192, "top_p": 0.9},
        "messages": [{"role": "system", "content": system}, *messages],
    }
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST", f"{settings.OLLAMA_URL}/api/chat", json=payload, headers=_NGROK_HEADERS
        ) as resp:
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done"):
                    break


async def call_ollama_json(prompt: str, model: str) -> str:
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0},
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{settings.OLLAMA_URL}/api/chat", json=payload, headers=_NGROK_HEADERS)
        resp.raise_for_status()
    return resp.json()["message"]["content"]


# ── Claude ────────────────────────────────────────────────────────────────────

async def stream_claude(
    messages: list[dict], system: str, model: str
) -> AsyncIterator[str]:
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    async with client.messages.stream(
        model=model,
        max_tokens=2048,
        system=system,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def call_claude_json(prompt: str, model: str) -> str:
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    resp = await client.messages.create(
        model=model,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


# ── OpenRouter (OpenAI-compatible, free models available) ─────────────────────

def _openrouter_client():
    from openai import AsyncOpenAI
    return AsyncOpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": settings.OPENROUTER_SITE_URL,
            "X-Title": settings.OPENROUTER_SITE_NAME,
        },
    )


async def stream_openrouter(
    messages: list[dict], system: str, model: str
) -> AsyncIterator[str]:
    client = _openrouter_client()
    stream = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, *messages],
        max_tokens=1024,
        temperature=0.2,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def call_openrouter_json(prompt: str, model: str) -> str:
    client = _openrouter_client()
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.0,
    )
    return resp.choices[0].message.content or ""


# ── Unified interface ─────────────────────────────────────────────────────────

async def stream_llm(
    messages: list[dict], system: str, chat_model: str
) -> AsyncIterator[str]:
    if settings.LLM_PROVIDER == "ollama":
        async for token in stream_ollama(messages, system, chat_model):
            yield token
    elif settings.LLM_PROVIDER == "claude":
        async for token in stream_claude(messages, system, chat_model):
            yield token
    elif settings.LLM_PROVIDER == "openrouter":
        async for token in stream_openrouter(messages, system, chat_model):
            yield token
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER}")


async def call_llm_json(prompt: str, router_model: str) -> str:
    if settings.LLM_PROVIDER == "ollama":
        return await call_ollama_json(prompt, router_model)
    elif settings.LLM_PROVIDER == "claude":
        return await call_claude_json(prompt, router_model)
    elif settings.LLM_PROVIDER == "openrouter":
        return await call_openrouter_json(prompt, router_model)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER}")


async def call_llm_plain(prompt: str, model: str) -> str:
    """Non-JSON completion — used for translation and other plain-text tasks."""
    if settings.LLM_PROVIDER == "ollama":
        payload = {
            "model": model,
            "stream": False,
            "options": {"temperature": 0.0, "num_ctx": 2048},
            "messages": [{"role": "user", "content": prompt}],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{settings.OLLAMA_URL}/api/chat", json=payload, headers=_NGROK_HEADERS)
            resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    elif settings.LLM_PROVIDER == "claude":
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = await client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    elif settings.LLM_PROVIDER == "openrouter":
        client = _openrouter_client()
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.0,
        )
        return (resp.choices[0].message.content or "").strip()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER}")
