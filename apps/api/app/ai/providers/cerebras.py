"""cerebras provider adapter: invoke(model_cfg, payload) -> normalized result.
The ONLY file allowed to import the Cerebras SDK/HTTP surface (RULES.md #1). Plain httpx against
Cerebras's OpenAI-compatible chat completions endpoint - no cerebras SDK needed.

Tuning: response_format json_object (confirmed supported) so the model returns raw JSON instead of
prose-wrapped JSON, cutting parse-fence stripping risk; temperature comes from model_cfg (ai.yaml)
kept low (0.2-0.3) for deterministic structured item-bank output - this is factual content
generation, not open-ended chat. Cerebras's inference models have no separate "thinking mode" to
disable (unlike DeepSeek's V4 line)."""
from __future__ import annotations

import httpx

from app.ai.providers import ProviderError, ProviderResult
from app.core.config import ModelSpec, settings

_API_URL = "https://api.cerebras.ai/v1/chat/completions"


async def invoke(model_cfg: ModelSpec, *, system: str, prompt: str) -> ProviderResult:
    if not settings.cerebras_api_key:
        raise ProviderError("CEREBRAS_API_KEY not configured")
    try:
        async with httpx.AsyncClient(timeout=model_cfg.timeout_s) as client:
            res = await client.post(
                _API_URL,
                headers={"Authorization": f"Bearer {settings.cerebras_api_key}"},
                json={
                    "model": model_cfg.model,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                    "temperature": model_cfg.temperature,
                    "response_format": {"type": "json_object"},
                },
            )
        res.raise_for_status()
        body = res.json()
        text = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        return ProviderResult(text=text, input_tokens=usage.get("prompt_tokens", 0), output_tokens=usage.get("completion_tokens", 0))
    except httpx.HTTPError as exc:
        raise ProviderError(f"cerebras request failed: {type(exc).__name__}: {exc}") from exc
