"""deepseek provider adapter: invoke(model_cfg, payload) -> normalized result.
The ONLY file allowed to import the DeepSeek SDK/HTTP surface (RULES.md #1). Plain httpx against
DeepSeek's OpenAI-compatible chat completions endpoint - no deepseek SDK needed.

Tuning: model is deepseek-chat (general-purpose), never deepseek-reasoner (thinking-heavy, slow,
unsuited to fast structured JSON). "thinking": {"type": "disabled"} explicitly turns off V4's
default extended-reasoning mode - reasoning_effort is deliberately omitted (its lowest value is the
implicit default when thinking is disabled, and the field isn't required). response_format
json_object (confirmed supported per DeepSeek's docs) + low temperature from model_cfg (ai.yaml)
for deterministic structured output - this is factual content generation, not open-ended chat."""
from __future__ import annotations

import httpx

from app.ai.providers import ProviderError, ProviderResult
from app.core.config import ModelSpec, settings

_API_URL = "https://api.deepseek.com/chat/completions"


async def invoke(model_cfg: ModelSpec, *, system: str, prompt: str) -> ProviderResult:
    if not settings.deepseek_api_key:
        raise ProviderError("DEEPSEEK_API_KEY not configured")
    try:
        async with httpx.AsyncClient(timeout=model_cfg.timeout_s) as client:
            res = await client.post(
                _API_URL,
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json={
                    "model": model_cfg.model,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                    "temperature": model_cfg.temperature,
                    "response_format": {"type": "json_object"},
                    "thinking": {"type": "disabled"},
                },
            )
        res.raise_for_status()
        body = res.json()
        text = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        return ProviderResult(text=text, input_tokens=usage.get("prompt_tokens", 0), output_tokens=usage.get("completion_tokens", 0))
    except httpx.HTTPError as exc:
        raise ProviderError(f"deepseek request failed: {type(exc).__name__}: {exc}") from exc
