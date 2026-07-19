"""groq provider adapter: invoke(model_cfg, payload) -> normalized result.
The ONLY file allowed to import the Groq SDK/HTTP surface (RULES.md #1). Plain httpx against
Groq's OpenAI-compatible chat completions endpoint - no groq SDK needed."""
from __future__ import annotations

import httpx

from app.ai.providers import ProviderError, ProviderResult
from app.core.config import ModelSpec, settings

_API_URL = "https://api.groq.com/openai/v1/chat/completions"


async def invoke(model_cfg: ModelSpec, *, system: str, prompt: str) -> ProviderResult:
    if not settings.groq_api_key:
        raise ProviderError("GROQ_API_KEY not configured")
    try:
        async with httpx.AsyncClient(timeout=model_cfg.timeout_s) as client:
            res = await client.post(
                _API_URL,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                json={
                    "model": model_cfg.model,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                },
            )
        res.raise_for_status()
        body = res.json()
        text = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        return ProviderResult(text=text, input_tokens=usage.get("prompt_tokens", 0), output_tokens=usage.get("completion_tokens", 0))
    except httpx.HTTPError as exc:
        raise ProviderError(f"groq request failed: {type(exc).__name__}: {exc}") from exc
