"""ai/gateway.py: lookup-before-generate (RULES.md #4), per-provider timeout/failover/one-retry
and every-attempt logging (RULES.md #13). Provider HTTP calls are monkeypatched - these test the
gateway's own control flow, not live third-party APIs (that's what e2e/diagnostic_flow.spec.ts,
run against real configured keys, proves separately).
Requires a real Postgres (DATABASE_URL) with migrations applied - same pattern as test_pools.py."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="requires DATABASE_URL (postgres)"),
]

import app.core.db as db_module  # noqa: E402
from app import ai  # noqa: E402
from app.ai import gateway  # noqa: E402
from app.ai.providers import ProviderError, ProviderResult  # noqa: E402
from app.ai.providers import claude as claude_provider  # noqa: E402
from app.ai.providers import gemini as gemini_provider  # noqa: E402
from app.core.db import AiInvocation, SessionLocal  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _fresh_engine_per_test():
    db_module._engine = None
    db_module._session_factory = None
    yield
    if db_module._engine is not None:
        await db_module._engine.dispose()
    db_module._engine = None
    db_module._session_factory = None


def _ok(text: str = '{"ok": true}') -> ProviderResult:
    return ProviderResult(text=text, input_tokens=10, output_tokens=5)


async def _invocations_for(db, task: str, since: datetime) -> list[AiInvocation]:
    # Real, persistent Postgres with no per-test transaction rollback (same convention as
    # test_curriculum.py) - scope by created_at so a previous test's rows for the same task never
    # leak into this one's assertions.
    rows = (
        await db.execute(
            select(AiInvocation).where(AiInvocation.task == task, AiInvocation.created_at >= since).order_by(AiInvocation.created_at)
        )
    ).scalars().all()
    return rows


async def test_lookup_before_generate_then_cache_hit_on_second_call(monkeypatch):
    calls = {"n": 0}

    async def _fake_invoke(model_cfg, *, system, prompt):
        calls["n"] += 1
        return _ok('{"n": 1}')

    monkeypatch.setattr(claude_provider, "invoke", _fake_invoke)
    topic_id = None
    since = datetime.now(timezone.utc)
    source_hash = f"h-same-{uuid.uuid4()}"  # same value both calls - that's what makes call 2 a cache hit

    async with SessionLocal() as db:
        r1 = await ai.generate(
            "item_bank", db=db, scope="topic_shared", artifact_type="item_bank", topic_id=topic_id,
            params={"p": "same"}, source_hash=source_hash, render_user_prompt=lambda: "prompt text",
        )
        await db.commit()
    assert r1.cache_hit is False
    assert calls["n"] == 1

    async with SessionLocal() as db:
        r2 = await ai.generate(
            "item_bank", db=db, scope="topic_shared", artifact_type="item_bank", topic_id=topic_id,
            params={"p": "same"}, source_hash=source_hash, render_user_prompt=lambda: "prompt text",
        )
        await db.commit()
    assert r2.cache_hit is True
    assert r2.content == r1.content
    assert calls["n"] == 1  # provider not called again - generated_artifacts served it

    async with SessionLocal() as db:
        rows = await _invocations_for(db, "item_bank", since)
    assert len(rows) == 2
    assert rows[0].cache_hit is False and rows[0].success is True
    assert rows[1].cache_hit is True and rows[1].provider == "cache"


async def test_failover_logs_failed_attempt_then_succeeds_on_next_provider(monkeypatch):
    async def _claude_fails(model_cfg, *, system, prompt):
        raise ProviderError("simulated: primary key killed")

    async def _gemini_succeeds(model_cfg, *, system, prompt):
        return _ok('{"from": "gemini"}')

    monkeypatch.setattr(claude_provider, "invoke", _claude_fails)
    monkeypatch.setattr(gemini_provider, "invoke", _gemini_succeeds)
    topic_id = None
    since = datetime.now(timezone.utc)

    async with SessionLocal() as db:
        result = await ai.generate(
            "item_bank", db=db, scope="topic_shared", artifact_type="item_bank", topic_id=topic_id,
            params={}, source_hash=f"h-failover-{uuid.uuid4()}", render_user_prompt=lambda: "prompt",
        )
        await db.commit()

    assert result.content == {"from": "gemini"}
    async with SessionLocal() as db:
        rows = await _invocations_for(db, "item_bank", since)
    failed = [r for r in rows if r.provider == "claude_sonnet" and r.success is False]
    succeeded = [r for r in rows if r.provider == "gemini_flash" and r.success is True]
    assert len(failed) == 1
    assert len(succeeded) == 1
    assert "simulated" in (failed[0].error or "")


async def test_one_parse_retry_same_provider_before_failover(monkeypatch):
    calls = {"claude": 0, "gemini": 0}

    async def _claude_bad_then_good(model_cfg, *, system, prompt):
        calls["claude"] += 1
        if calls["claude"] == 1:
            return _ok("not json at all")
        return _ok('{"recovered": true}')

    async def _gemini_should_not_be_called(model_cfg, *, system, prompt):
        calls["gemini"] += 1
        return _ok('{"from": "gemini"}')

    monkeypatch.setattr(claude_provider, "invoke", _claude_bad_then_good)
    monkeypatch.setattr(gemini_provider, "invoke", _gemini_should_not_be_called)
    topic_id = None

    async with SessionLocal() as db:
        result = await ai.generate(
            "item_bank", db=db, scope="topic_shared", artifact_type="item_bank", topic_id=topic_id,
            params={}, source_hash=f"h-retry-{uuid.uuid4()}", render_user_prompt=lambda: "prompt",
        )
        await db.commit()

    assert result.content == {"recovered": True}
    assert calls["claude"] == 2
    assert calls["gemini"] == 0


async def test_all_providers_exhausted_raises_but_still_logs_every_attempt(monkeypatch):
    async def _always_fails(model_cfg, *, system, prompt):
        raise ProviderError("down")

    monkeypatch.setattr(claude_provider, "invoke", _always_fails)
    monkeypatch.setattr(gemini_provider, "invoke", _always_fails)
    topic_id = None
    since = datetime.now(timezone.utc)

    async with SessionLocal() as db:
        with pytest.raises(gateway.GatewayError):
            await ai.generate(
                "item_bank", db=db, scope="topic_shared", artifact_type="item_bank", topic_id=topic_id,
                params={}, source_hash=f"h-exhausted-{uuid.uuid4()}", render_user_prompt=lambda: "prompt",
            )
        await db.commit()

    async with SessionLocal() as db:
        rows = await _invocations_for(db, "item_bank", since)
    failed_providers = {r.provider for r in rows if r.success is False}
    assert {"claude_sonnet", "gemini_flash"} <= failed_providers
