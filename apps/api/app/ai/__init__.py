"""AI facade: the ONLY import surface for feature code (RULES.md #1).
async def generate(task, **ctx)   # task selects prompt file + chain from config/ai.yaml
async def embed(texts) -> list[list[float]]
async def ocr(image_bytes)        # dormant until features.ocr
Gateway contract (gateway.py): lookup generated_artifacts by cache_key BEFORE any provider call;
write artifact + ai_invocations row AFTER; per-provider timeout; failover down the chain; demo_mode serves demo_cache first."""
from __future__ import annotations

import uuid
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import gateway
from app.ai.gateway import GatewayError, GenerateResult
from app.ai.providers import gemini as _gemini_provider
from app.core.config import ModelSpec, settings

__all__ = ["generate", "embed", "GatewayError", "GenerateResult"]


async def generate(
    task: str,
    *,
    db: AsyncSession,
    scope: str,
    artifact_type: str,
    render_user_prompt: Callable[[], str],
    topic_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    params: dict | None = None,
    source_hash: str | None = None,
    validate: Callable[[dict], None] | None = None,
) -> GenerateResult:
    return await gateway.generate(
        task, db=db, scope=scope, artifact_type=artifact_type, topic_id=topic_id, user_id=user_id,
        params=params or {}, source_hash=source_hash, render_user_prompt=render_user_prompt, validate=validate,
    )


async def embed(texts: list[str]) -> list[list[float]]:
    """Dormant until M8 (doubts/explore); implemented now so the facade contract is real, not a stub."""
    chain = settings.get("ai", "chains", "embeddings", default=[])
    if not chain:
        raise GatewayError("No provider chain configured for task 'embeddings'")
    model_cfg = settings.get("ai", "models", chain[0], default=None)
    if model_cfg is None:
        raise GatewayError(f"Unknown embeddings model '{chain[0]}'")
    return await _gemini_provider.embed(ModelSpec(**model_cfg), texts)
