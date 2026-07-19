"""gemini provider adapter: invoke(model_cfg, payload) -> normalized result; embed(...) for the
embeddings chain (dormant until M8 doubts/explore - implemented now since ai/__init__'s embed()
facade method needs a real backend, but nothing calls it yet).
The ONLY file allowed to import the Gemini SDK/HTTP surface (RULES.md #1). Plain httpx."""
from __future__ import annotations

import httpx

from app.ai.providers import ProviderError, ProviderResult
from app.core.config import ModelSpec, settings

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


async def invoke(model_cfg: ModelSpec, *, system: str, prompt: str) -> ProviderResult:
    if not settings.gemini_api_key:
        raise ProviderError("GEMINI_API_KEY not configured")
    try:
        async with httpx.AsyncClient(timeout=model_cfg.timeout_s) as client:
            res = await client.post(
                f"{_BASE_URL}/{model_cfg.model}:generateContent",
                params={"key": settings.gemini_api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "systemInstruction": {"parts": [{"text": system}]},
                },
            )
        res.raise_for_status()
        body = res.json()
        candidates = body.get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(p.get("text", "") for p in parts)
        usage = body.get("usageMetadata", {})
        return ProviderResult(
            text=text, input_tokens=usage.get("promptTokenCount", 0), output_tokens=usage.get("candidatesTokenCount", 0)
        )
    except httpx.HTTPError as exc:
        raise ProviderError(f"gemini request failed: {type(exc).__name__}: {exc}") from exc


async def embed(model_cfg: ModelSpec, texts: list[str]) -> list[list[float]]:
    if not settings.gemini_api_key:
        raise ProviderError("GEMINI_API_KEY not configured")
    try:
        vectors: list[list[float]] = []
        async with httpx.AsyncClient(timeout=model_cfg.timeout_s) as client:
            for text in texts:
                res = await client.post(
                    f"{_BASE_URL}/{model_cfg.model}:embedContent",
                    params={"key": settings.gemini_api_key},
                    json={"content": {"parts": [{"text": text}]}},
                )
                res.raise_for_status()
                vectors.append(res.json()["embedding"]["values"])
        return vectors
    except httpx.HTTPError as exc:
        raise ProviderError(f"gemini embed failed: {type(exc).__name__}: {exc}") from exc
