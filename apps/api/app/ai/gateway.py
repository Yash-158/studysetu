"""Provider-chain resolver + Generated Content Store integration (RULES.md #4, #13).
cache_key = sha256(f"{artifact_type}|{topic_id}|{params}|{source_hash}|{prompt_version}")

Call order per task: demo_cache lookup (only if ai.cache.demo_mode) -> generated_artifacts lookup
by cache_key -> on miss, walk config/ai.yaml's chain for the task, one same-provider parse retry,
failover to the next provider on any failure -> write generated_artifacts BEFORE returning ->
log ai_invocations exactly once per attempt (hit, cache read, or each provider try) so a killed
key shows up as a logged failure, never silence."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Callable

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import ProviderError
from app.ai.providers import claude as claude_provider
from app.ai.providers import gemini as gemini_provider
from app.ai.providers import groq as groq_provider
from app.core.config import ModelSpec, settings
from app.core.db import AiInvocation, DemoCache, GeneratedArtifact

_PROVIDER_BY_MODEL_KEY = {
    "claude_sonnet": claude_provider,
    "gemini_flash": gemini_provider,
    "gemini_embed": gemini_provider,
    "groq_llama": groq_provider,
}


class GatewayError(Exception):
    """Raised when an entire provider chain is exhausted. Callers turn this into the typed
    {code, message, hint} API error (RULES.md #13) - never a raw provider exception."""


def compute_cache_key(artifact_type: str, topic_id: uuid.UUID | None, params: dict, source_hash: str | None, prompt_version: str) -> str:
    payload = json.dumps(
        {"artifact_type": artifact_type, "topic_id": str(topic_id) if topic_id else None, "params": params,
         "source_hash": source_hash, "prompt_version": prompt_version},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _load_system_prompt(task: str) -> str:
    path = Path(settings.prompts_dir) / f"{task}.md"
    return path.read_text()


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.endswith("```"):
            t = t[: -3]
        if t.startswith("json"):
            t = t[4:]
    return t.strip()


async def _log_invocation(
    db: AsyncSession, *, task: str, provider: str, model: str, cache_hit: bool, success: bool,
    ref_artifact: uuid.UUID | None = None, latency_ms: int | None = None,
    input_tokens: int | None = None, output_tokens: int | None = None, error: str | None = None,
) -> None:
    db.add(AiInvocation(
        id=uuid.uuid4(), task=task, provider=provider, model=model, cache_hit=cache_hit,
        ref_artifact=ref_artifact, latency_ms=latency_ms, input_tokens=input_tokens,
        output_tokens=output_tokens, success=success, error=error,
    ))
    await db.flush()


class GenerateResult:
    def __init__(self, content: dict, cache_hit: bool, artifact_id: uuid.UUID) -> None:
        self.content = content
        self.cache_hit = cache_hit
        self.artifact_id = artifact_id


async def generate(
    task: str,
    *,
    db: AsyncSession,
    scope: str,
    artifact_type: str,
    topic_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    params: dict,
    source_hash: str | None,
    render_user_prompt: Callable[[], str],
    validate: Callable[[dict], None] | None = None,
) -> GenerateResult:
    prompt_version = settings.get("ai", "cache", "prompt_version", default="v1")
    cache_key = compute_cache_key(artifact_type, topic_id, params, source_hash, prompt_version)
    cache_enabled = settings.get("ai", "cache", "enabled", default=True)
    demo_mode = settings.get("ai", "cache", "demo_mode", default=False)

    if demo_mode:
        demo_row = (
            await db.execute(select(DemoCache).where(DemoCache.task == task, DemoCache.input_hash == cache_key))
        ).scalar_one_or_none()
        if demo_row is not None:
            await _log_invocation(db, task=task, provider="demo", model="demo", cache_hit=True, success=True)
            # Not a fresh artifact row - demo responses are pre-seeded, not generated this call.
            existing = (
                await db.execute(select(GeneratedArtifact).where(GeneratedArtifact.cache_key == cache_key))
            ).scalar_one_or_none()
            artifact_id = existing.id if existing else uuid.uuid4()
            return GenerateResult(content=demo_row.response, cache_hit=True, artifact_id=artifact_id)

    if cache_enabled:
        existing = (
            await db.execute(select(GeneratedArtifact).where(GeneratedArtifact.cache_key == cache_key))
        ).scalar_one_or_none()
        if existing is not None:
            await _log_invocation(
                db, task=task, provider="cache", model=existing.model or "unknown",
                cache_hit=True, success=True, ref_artifact=existing.id,
            )
            return GenerateResult(content=existing.content, cache_hit=True, artifact_id=existing.id)

    chain = settings.get("ai", "chains", task, default=[])
    if not chain:
        raise GatewayError(f"No provider chain configured for task '{task}'")

    system_prompt = _load_system_prompt(task)
    user_prompt = render_user_prompt()

    for model_key in chain:
        provider_module = _PROVIDER_BY_MODEL_KEY.get(model_key)
        model_cfg = settings.get("ai", "models", model_key, default=None)
        if provider_module is None or model_cfg is None:
            continue
        cfg = ModelSpec(**model_cfg)

        last_error: Exception | None = None
        for attempt in (1, 2):  # one same-provider parse retry (RULES.md #13)
            started = time.monotonic()
            try:
                result = await provider_module.invoke(cfg, system=system_prompt, prompt=user_prompt)
            except ProviderError as exc:
                latency_ms = int((time.monotonic() - started) * 1000)
                await _log_invocation(
                    db, task=task, provider=model_key, model=cfg.model, cache_hit=False, success=False,
                    latency_ms=latency_ms, error=str(exc),
                )
                last_error = exc
                break  # provider itself failed (timeout/auth/http) - failover, don't retry it

            latency_ms = int((time.monotonic() - started) * 1000)
            try:
                parsed = json.loads(_strip_fences(result.text))
                if validate is not None:
                    validate(parsed)
            except Exception as exc:  # noqa: BLE001 - any parse/shape failure triggers the one retry
                last_error = exc
                await _log_invocation(
                    db, task=task, provider=model_key, model=cfg.model, cache_hit=False, success=False,
                    latency_ms=latency_ms, input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                    error=f"parse failed (attempt {attempt}): {exc}",
                )
                logger.warning("ai gateway parse failure task={} provider={} attempt={}", task, model_key, attempt)
                continue  # same-provider retry

            artifact = GeneratedArtifact(
                id=uuid.uuid4(), scope=scope, artifact_type=artifact_type, topic_id=topic_id, user_id=user_id,
                cache_key=cache_key, content=parsed, source_hash=source_hash, prompt_version=prompt_version,
                model=cfg.model, tokens=result.input_tokens + result.output_tokens,
            )
            db.add(artifact)
            await db.flush()  # written BEFORE being shown to any caller (RULES.md #4)

            await _log_invocation(
                db, task=task, provider=model_key, model=cfg.model, cache_hit=False, success=True,
                ref_artifact=artifact.id, latency_ms=latency_ms,
                input_tokens=result.input_tokens, output_tokens=result.output_tokens,
            )
            return GenerateResult(content=parsed, cache_hit=False, artifact_id=artifact.id)

        logger.warning("ai gateway failing over from {} for task={}: {}", model_key, task, last_error)

    raise GatewayError(f"All providers in chain for task '{task}' failed")
