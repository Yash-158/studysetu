"""claude provider adapter: invoke(model_cfg, payload) -> normalized result.
The ONLY file allowed to import the Anthropic SDK/HTTP surface (RULES.md #1).
Plain httpx (already a dependency) against the Messages API - no anthropic SDK needed for one
JSON-in/JSON-out call."""
from __future__ import annotations

import httpx

from app.ai.providers import ProviderError, ProviderResult
from app.core.config import ModelSpec, settings

_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


async def invoke(model_cfg: ModelSpec, *, system: str, prompt: str) -> ProviderResult:
    if not settings.anthropic_api_key:
        raise ProviderError("ANTHROPIC_API_KEY not configured")
    try:
        async with httpx.AsyncClient(timeout=model_cfg.timeout_s) as client:
            res = await client.post(
                _API_URL,
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": _ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": model_cfg.model,
                    "max_tokens": 4096,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        res.raise_for_status()
        body = res.json()
        text = "".join(block.get("text", "") for block in body.get("content", []) if block.get("type") == "text")
        usage = body.get("usage", {})
        return ProviderResult(text=text, input_tokens=usage.get("input_tokens", 0), output_tokens=usage.get("output_tokens", 0))
    except httpx.HTTPError as exc:
        # str(exc) is often empty for timeout exceptions - the type name is what actually carries
        # the meaning ("ReadTimeout" vs "ConnectError"), and a blank ai_invocations.error is useless.
        raise ProviderError(f"claude request failed: {type(exc).__name__}: {exc}") from exc
