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
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import ProviderError
from app.ai.providers import cerebras as cerebras_provider
from app.ai.providers import claude as claude_provider
from app.ai.providers import deepseek as deepseek_provider
from app.ai.providers import gemini as gemini_provider
from app.ai.providers import groq as groq_provider
from app.core.config import ModelSpec, settings
from app.core.db import AiInvocation, DemoCache, GeneratedArtifact

_PROVIDER_BY_MODEL_KEY = {
    "claude": claude_provider,
    "gemini": gemini_provider,
    "gemini_embed": gemini_provider,
    "groq": groq_provider,
    "cerebras": cerebras_provider,
    "deepseek": deepseek_provider,
}

# The 4 providers eligible for ai_primary_provider/ai_fallback_provider (Claude excluded - it's
# still a valid onboarded provider but deliberately outside this comparison, same as production
# leaving ANTHROPIC_API_KEY unconfigured since M4 - see docs/MEMORY.md). Fixed order used to fill
# the remaining fallback depth once primary/fallback are placed first.
_COMPARABLE_PROVIDERS = ["groq", "gemini", "cerebras", "deepseek"]

# Tasks whose provider order is resolved dynamically from ai_primary_provider/ai_fallback_provider
# instead of a static config/ai.yaml list - see _resolve_dynamic_chain().
# "segment" (M5, prompts/segment.md) added here - the task name must match the prompt filename
# (_load_system_prompt below), and "segment" is what M5's planner actually calls. "session" was
# pre-built here at M4/PR#7 anticipating this need but guessed the task name; left in place and
# dormant (not removed) rather than reused, since M5's per-student composition layer (the bridge
# card) turned out cheap enough to template deterministically - no LLM call, no task name needed.
_DYNAMIC_CHAIN_TASKS = {"item_bank", "session", "segment", "dialogue", "fast_text"}


def _resolve_dynamic_chain() -> list[str]:
    """[primary, fallback, <remaining two in fixed order>] - switching either config value changes
    real behavior with zero code changes; the other two always serve as deeper fallback."""
    primary = settings.get("ai", "ai_primary_provider", default="groq")
    fallback = settings.get("ai", "ai_fallback_provider", default="gemini")
    remaining = [p for p in _COMPARABLE_PROVIDERS if p not in (primary, fallback)]
    return [primary, fallback, *remaining]


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

    chain = _resolve_dynamic_chain() if task in _DYNAMIC_CHAIN_TASKS else settings.get("ai", "chains", task, default=[])
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

            # Race-safe upsert, not db.add()+flush(): two concurrent requests can both pass the
            # cache_key lookup above as a miss (classic check-then-insert TOCTOU - real under
            # legitimate load, e.g. two students opening the same fresh topic at once, not just a
            # dev-mode StrictMode double-effect artifact that's how this was first caught) and
            # both reach this INSERT. ON CONFLICT DO NOTHING makes the loser's write a no-op
            # instead of an unhandled IntegrityError; it then reads back the WINNER's row and
            # reports its own attempt as a genuine cache hit rather than crashing the request.
            artifact_id = uuid.uuid4()
            insert_stmt = (
                pg_insert(GeneratedArtifact)
                .values(
                    id=artifact_id, scope=scope, artifact_type=artifact_type, topic_id=topic_id, user_id=user_id,
                    cache_key=cache_key, content=parsed, source_hash=source_hash, prompt_version=prompt_version,
                    model=cfg.model, tokens=result.input_tokens + result.output_tokens,
                )
                .on_conflict_do_nothing(index_elements=["cache_key"])
                .returning(GeneratedArtifact.id)
            )
            won_id = (await db.execute(insert_stmt)).scalar_one_or_none()

            if won_id is not None:
                await _log_invocation(
                    db, task=task, provider=model_key, model=cfg.model, cache_hit=False, success=True,
                    ref_artifact=won_id, latency_ms=latency_ms,
                    input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                )
                return GenerateResult(content=parsed, cache_hit=False, artifact_id=won_id)

            existing = (
                await db.execute(select(GeneratedArtifact).where(GeneratedArtifact.cache_key == cache_key))
            ).scalar_one()
            await _log_invocation(
                db, task=task, provider="cache", model=existing.model or "unknown",
                cache_hit=True, success=True, ref_artifact=existing.id,
            )
            return GenerateResult(content=existing.content, cache_hit=True, artifact_id=existing.id)

        logger.warning("ai gateway failing over from {} for task={}: {}", model_key, task, last_error)

    raise GatewayError(f"All providers in chain for task '{task}' failed")
