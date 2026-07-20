"""M4 independent audit (requested before merge, same discipline as M2's isolation tests and
M3's publish-cascade/pool-sync audit): three specific claims about ai/gateway.py and
modules/learning.py, each proven against the real, untouched implementation - not asserted from
reading the code. Where a claim could be vacuously true (the retry-vs-failover distinction, the
weak-prereq survival-under-backfill claim), the test is also run against a deliberately
reintroduced bug to confirm it goes red, then the code is restored and reconfirmed green.
Requires a real Postgres (DATABASE_URL) with migrations applied - same pattern as test_learning.py.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="requires DATABASE_URL (postgres)"),
]

import app.core.db as db_module  # noqa: E402
from app import ai  # noqa: E402
from app.ai.providers import ProviderError, ProviderResult  # noqa: E402
from app.ai.providers import gemini as gemini_provider  # noqa: E402
from app.ai.providers import groq as groq_provider  # noqa: E402
from app.core.db import AiInvocation, Institution, Item, Mastery, SessionLocal, Topic, User  # noqa: E402
from app.core.security import hash_secret  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.learning import _draw_diagnostic_items  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _fresh_engine_per_test():
    db_module._engine = None
    db_module._session_factory = None
    yield
    if db_module._engine is not None:
        await db_module._engine.dispose()
    db_module._engine = None
    db_module._session_factory = None


@pytest_asyncio.fixture()
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _ok(text: str) -> ProviderResult:
    return ProviderResult(text=text, input_tokens=10, output_tokens=5)


async def _create_institution() -> str:
    slug = f"test-{uuid.uuid4().hex[:8]}"
    async with SessionLocal() as db:
        db.add(Institution(id=uuid.uuid4(), name="Test Institution", slug=slug, is_personal=False))
        await db.commit()
    return slug


async def _user(client: AsyncClient, slug: str, role: str) -> tuple[str, str]:
    identifier = f"{role}-{uuid.uuid4().hex[:6]}@test.local"
    async with SessionLocal() as db:
        institution = (await db.execute(select(Institution).where(Institution.slug == slug))).scalar_one()
        u = User(
            id=uuid.uuid4(), institution_id=institution.id, role=role, display_name=role.title(),
            roll_number=None, email=identifier, password_hash=hash_secret("userpass-1"),
            status="active", activation_code_hash=None, locale="en",
        )
        db.add(u)
        await db.commit()
        user_id = u.id
    res = await client.post("/api/auth/login", json={"institution_slug": slug, "identifier": identifier, "password": "userpass-1"})
    assert res.status_code == 200, res.text
    return str(user_id), res.json()["access_token"]


async def _invocations_since(db, task: str, since: datetime) -> list[AiInvocation]:
    rows = (
        await db.execute(
            select(AiInvocation).where(AiInvocation.task == task, AiInvocation.created_at >= since).order_by(AiInvocation.created_at)
        )
    ).scalars().all()
    return rows


# =====================================================================================
# CLAIM 1: cache key completeness - is compute_cache_key provider-agnostic, and is that correct?
# =====================================================================================

async def test_claim1_cache_key_is_provider_agnostic_and_that_matches_S13_design_intent(monkeypatch):
    """Design intent check (docs, not opinion): db/migrations/0006_events_storage_ai.sql's own
    comment on generated_artifacts.cache_key reads:
        -- hash(type, topic, level/misconception params, source_hash, prompt_version)
    Provider/model is deliberately absent from that list. FEATURE_EXPLANATION S13 ("generate
    ONCE per topic... served to every student forever") treats the chain's providers as
    interchangeable substitutes for the SAME task, not different products - that's the entire
    reason the 4 comparable providers are listed as one ordered fallback chain per
    task rather than as separate cached artifacts. So: cache keys SHOULD be provider-agnostic,
    and a Gemini-generated bank correctly becomes THE canonical answer for that topic+params,
    served identically regardless of which provider a later caller's chain would have preferred.
    This test proves the code does exactly that - not asserts it from reading gateway.py."""
    groq_calls = {"n": 0}
    gemini_calls = {"n": 0}

    async def _groq_ok(model_cfg, *, system, prompt):
        groq_calls["n"] += 1
        return _ok('{"from": "groq", "call": 1}')

    async def _gemini_would_answer_differently(model_cfg, *, system, prompt):
        gemini_calls["n"] += 1
        return _ok('{"from": "gemini", "call": 2}')

    monkeypatch.setattr(groq_provider, "invoke", _groq_ok)
    monkeypatch.setattr(gemini_provider, "invoke", _gemini_would_answer_differently)
    source_hash = f"h-provider-agnostic-{uuid.uuid4()}"
    common = dict(
        task="item_bank", scope="topic_shared", artifact_type="item_bank", topic_id=None,
        params={}, source_hash=source_hash, render_user_prompt=lambda: "prompt",
    )

    async with SessionLocal() as db:
        r1 = await ai.generate(db=db, **common)
        await db.commit()
    assert r1.cache_hit is False
    assert r1.content == {"from": "groq", "call": 1}
    assert groq_calls["n"] == 1

    # Force a DIFFERENT provider to be the only one that COULD answer for call 2 - if the cache
    # key included provider, this would be a miss and gemini would be invoked, producing
    # different content. If the cache key is provider-agnostic (the claim), gemini is never
    # even reached.
    async def _groq_now_unreachable(model_cfg, *, system, prompt):
        raise ProviderError("groq unreachable for call 2 - only gemini COULD answer now")

    monkeypatch.setattr(groq_provider, "invoke", _groq_now_unreachable)

    async with SessionLocal() as db:
        r2 = await ai.generate(db=db, **common)
        await db.commit()

    # THE ANSWER: cache_hit=True, content is STILL call 1's claude-tagged content, gemini is
    # NEVER invoked - confirming cache keys are provider-agnostic, matching the documented design.
    assert r2.cache_hit is True, "cache should hit on identical topic/params regardless of which provider originally answered"
    assert r2.content == {"from": "groq", "call": 1}, "cached content must be served as-is, not regenerated by a different provider"
    assert gemini_calls["n"] == 0, "a provider-agnostic cache must never even reach the fallback provider on a hit"


# =====================================================================================
# CLAIM 2: retry-vs-failover distinction (malformed JSON -> same-provider retry;
# hard failure -> immediate failover, no retry). Proven, then deliberately broken to confirm
# the tests aren't vacuous, then restored.
# =====================================================================================

async def test_claim2a_malformed_json_retries_same_provider_never_reaches_next_in_chain(monkeypatch, capsys):
    calls = {"groq": 0, "gemini": 0}

    async def _groq_bad_then_good(model_cfg, *, system, prompt):
        calls["groq"] += 1
        return _ok("this is not valid json at all {{{") if calls["groq"] == 1 else _ok('{"recovered": true}')

    async def _gemini_must_never_be_called(model_cfg, *, system, prompt):
        calls["gemini"] += 1
        return _ok('{"from": "gemini"}')

    monkeypatch.setattr(groq_provider, "invoke", _groq_bad_then_good)
    monkeypatch.setattr(gemini_provider, "invoke", _gemini_must_never_be_called)
    since = datetime.now(timezone.utc)
    source_hash = f"h-claim2a-{uuid.uuid4()}"

    async with SessionLocal() as db:
        result = await ai.generate(
            "item_bank", db=db, scope="topic_shared", artifact_type="item_bank", topic_id=None,
            params={}, source_hash=source_hash, render_user_prompt=lambda: "prompt",
        )
        await db.commit()

    assert result.content == {"recovered": True}
    assert calls["groq"] == 2, "malformed JSON must trigger exactly one same-provider retry"
    assert calls["gemini"] == 0, "a parse failure must NOT fail over to the next provider"

    async with SessionLocal() as db:
        rows = await _invocations_since(db, "item_bank", since)
    print("\n[claim 2a] ai_invocations rows for malformed-JSON-then-recovered:")
    for r in rows:
        print(f"  provider={r.provider!r} success={r.success} cache_hit={r.cache_hit} error={r.error!r}")
    assert [r.provider for r in rows] == ["groq", "groq"]
    assert [r.success for r in rows] == [False, True]
    assert "parse failed" in (rows[0].error or "")


async def test_claim2b_hard_failure_fails_over_immediately_with_no_retry(monkeypatch, capsys):
    calls = {"groq": 0, "gemini": 0}

    async def _groq_hard_failure(model_cfg, *, system, prompt):
        calls["groq"] += 1
        raise ProviderError("simulated: connection timeout")

    async def _gemini_succeeds(model_cfg, *, system, prompt):
        calls["gemini"] += 1
        return _ok('{"from": "gemini"}')

    monkeypatch.setattr(groq_provider, "invoke", _groq_hard_failure)
    monkeypatch.setattr(gemini_provider, "invoke", _gemini_succeeds)
    since = datetime.now(timezone.utc)
    source_hash = f"h-claim2b-{uuid.uuid4()}"

    async with SessionLocal() as db:
        result = await ai.generate(
            "item_bank", db=db, scope="topic_shared", artifact_type="item_bank", topic_id=None,
            params={}, source_hash=source_hash, render_user_prompt=lambda: "prompt",
        )
        await db.commit()

    assert result.content == {"from": "gemini"}
    assert calls["groq"] == 1, "a hard failure must NOT be retried on the same provider"
    assert calls["gemini"] == 1

    async with SessionLocal() as db:
        rows = await _invocations_since(db, "item_bank", since)
    print("\n[claim 2b] ai_invocations rows for hard-failure-then-failover:")
    for r in rows:
        print(f"  provider={r.provider!r} success={r.success} cache_hit={r.cache_hit} error={r.error!r}")
    assert [r.provider for r in rows] == ["groq", "gemini"]
    assert [r.success for r in rows] == [False, True]
    assert "timeout" in (rows[0].error or "")


# =====================================================================================
# CLAIM 3: weak-prereq slot survives shuffle-then-slice under a thin bank + backfill, and
# is_weak() correctly requires an EXISTING mastery row (no history != weak).
# =====================================================================================

async def _build_thin_topic_with_backfill_potential(client: AsyncClient, teacher_token: str, monkeypatch) -> tuple[str, str]:
    """A topic bank sized so the stratified pass draws only 3 of the 5 config-requested slots
    (medium wants 2, only 1 exists) while leaving 2 extra easy items unselected - real backfill
    fodder, not a starved bank that would just 400."""
    subject = (await client.post("/api/curriculum/subjects", json={"name": f"Subject {uuid.uuid4().hex[:6]}"}, headers=_auth(teacher_token))).json()
    chapter = (await client.post(f"/api/curriculum/subjects/{subject['id']}/chapters", json={"title": "Ch1"}, headers=_auth(teacher_token))).json()
    topic = (await client.post(f"/api/curriculum/subjects/{subject['id']}/topics", json={"title": "Thin Topic"}, headers=_auth(teacher_token))).json()
    await client.post(f"/api/curriculum/chapters/{chapter['id']}/blocks", json={"block_type": "topic", "topic_id": topic["id"]}, headers=_auth(teacher_token))
    await client.post(f"/api/curriculum/chapters/{chapter['id']}/publish", headers=_auth(teacher_token))

    # 3 easy (only 1 drawn by stratified, 2 left for backfill), 1 medium (config wants 2, only 1
    # available), 1 hard - 5 approved items total, deliberately unbalanced.
    bank = {"items": [
        {"stem": f"E{i}", "difficulty": -1, "options": [
            {"body": "c", "is_correct": True},
            {"body": "w1", "is_correct": False, "misconception_code": "m1", "misconception_title": "M1"},
            {"body": "w2", "is_correct": False, "misconception_code": "m2", "misconception_title": "M2"},
            {"body": "w3", "is_correct": False, "misconception_code": "m3", "misconception_title": "M3"},
        ], "explanation": "e"} for i in range(3)
    ] + [
        {"stem": "M1", "difficulty": 0, "options": [
            {"body": "c", "is_correct": True},
            {"body": "w1", "is_correct": False, "misconception_code": "m1", "misconception_title": "M1"},
            {"body": "w2", "is_correct": False, "misconception_code": "m2", "misconception_title": "M2"},
            {"body": "w3", "is_correct": False, "misconception_code": "m3", "misconception_title": "M3"},
        ], "explanation": "e"},
        {"stem": "H1", "difficulty": 1, "options": [
            {"body": "c", "is_correct": True},
            {"body": "w1", "is_correct": False, "misconception_code": "m1", "misconception_title": "M1"},
            {"body": "w2", "is_correct": False, "misconception_code": "m2", "misconception_title": "M2"},
            {"body": "w3", "is_correct": False, "misconception_code": "m3", "misconception_title": "M3"},
        ], "explanation": "e"},
    ]}

    async def _fake_invoke(model_cfg, *, system, prompt):
        return _ok(json.dumps(bank))

    monkeypatch.setattr(groq_provider, "invoke", _fake_invoke)
    gen = await client.post(f"/api/assessment/topics/{topic['id']}/bank/generate", headers=_auth(teacher_token))
    assert gen.status_code == 200, gen.text
    assert len(gen.json()["items"]) == 5
    await client.post(f"/api/assessment/topics/{topic['id']}/bank/approve-all", headers=_auth(teacher_token))
    return subject["id"], topic["id"]


async def _build_prereq_topic(client: AsyncClient, teacher_token: str, subject_id: str, monkeypatch, n: int = 3) -> str:
    prereq = (await client.post(f"/api/curriculum/subjects/{subject_id}/topics", json={"title": "Prereq Topic"}, headers=_auth(teacher_token))).json()

    def _one_item(i: int) -> dict:
        return {"stem": f"P{i}", "difficulty": 0, "options": [
            {"body": "c", "is_correct": True},
            {"body": "w1", "is_correct": False, "misconception_code": "m1", "misconception_title": "M1"},
            {"body": "w2", "is_correct": False, "misconception_code": "m2", "misconception_title": "M2"},
            {"body": "w3", "is_correct": False, "misconception_code": "m3", "misconception_title": "M3"},
        ], "explanation": "e"}

    async def _fake_invoke(model_cfg, *, system, prompt):
        return _ok(json.dumps({"items": [_one_item(i) for i in range(n)]}))

    monkeypatch.setattr(groq_provider, "invoke", _fake_invoke)
    gen = await client.post(f"/api/assessment/topics/{prereq['id']}/bank/generate", headers=_auth(teacher_token))
    assert gen.status_code == 200, gen.text
    await client.post(f"/api/assessment/topics/{prereq['id']}/bank/approve-all", headers=_auth(teacher_token))
    return prereq["id"]


async def test_claim3a_weak_prereq_item_survives_backfill_across_repeated_draws(client: AsyncClient, monkeypatch):
    slug = await _create_institution()
    _, teacher_token = await _user(client, slug, "teacher")
    student_id, _ = await _user(client, slug, "student")

    subject_id, topic_id = await _build_thin_topic_with_backfill_potential(client, teacher_token, monkeypatch)
    prereq_topic_id = await _build_prereq_topic(client, teacher_token, subject_id, monkeypatch)
    await client.post(f"/api/curriculum/topics/{prereq_topic_id}/edges", json={"dst_topic_id": topic_id}, headers=_auth(teacher_token))

    async with SessionLocal() as db:
        db.add(Mastery(user_id=uuid.UUID(student_id), topic_id=uuid.UUID(prereq_topic_id), p_known=0.15, confidence=1.0, attempts_count=4))
        await db.commit()

        student = (await db.execute(select(User).where(User.id == uuid.UUID(student_id)))).scalar_one()
        topic = (await db.execute(select(Topic).where(Topic.id == uuid.UUID(topic_id)))).scalar_one()
        prereq_item_ids = {i for i in (await db.execute(select(Item.id).where(Item.topic_id == uuid.UUID(prereq_topic_id)))).scalars().all()}

        # Repeated draws (random.shuffle is in play at three points in _draw_diagnostic_items) -
        # under correct code this must be present EVERY time, not "usually."
        misses = 0
        for _ in range(20):
            selected = await _draw_diagnostic_items(db, student, topic)
            assert len(selected) == 5
            drawn_prereq = [i for i in selected if i.id in prereq_item_ids]
            if len(drawn_prereq) != 1:
                misses += 1
        assert misses == 0, f"weak-prereq item missing from the final 5 in {misses}/20 draws"


async def test_claim3b_no_mastery_history_on_prereq_does_not_trigger_the_weak_slot(client: AsyncClient, monkeypatch):
    """S3: 'when history exists' - a student who has NEVER touched the prerequisite topic must
    NOT be treated as weak on it (that would be judging on a default, not a real signal)."""
    slug = await _create_institution()
    _, teacher_token = await _user(client, slug, "teacher")
    student_id, _ = await _user(client, slug, "student")  # deliberately: zero mastery rows anywhere

    subject_id, topic_id = await _build_thin_topic_with_backfill_potential(client, teacher_token, monkeypatch)
    prereq_topic_id = await _build_prereq_topic(client, teacher_token, subject_id, monkeypatch)
    await client.post(f"/api/curriculum/topics/{prereq_topic_id}/edges", json={"dst_topic_id": topic_id}, headers=_auth(teacher_token))

    async with SessionLocal() as db:
        # Sanity: confirm no mastery row exists at all for this student/prereq pair.
        row = (
            await db.execute(select(Mastery).where(Mastery.user_id == uuid.UUID(student_id), Mastery.topic_id == uuid.UUID(prereq_topic_id)))
        ).scalar_one_or_none()
        assert row is None, "test setup error: this student must have zero mastery history on the prereq"

        student = (await db.execute(select(User).where(User.id == uuid.UUID(student_id)))).scalar_one()
        topic = (await db.execute(select(Topic).where(Topic.id == uuid.UUID(topic_id)))).scalar_one()
        prereq_item_ids = {i for i in (await db.execute(select(Item.id).where(Item.topic_id == uuid.UUID(prereq_topic_id)))).scalars().all()}

        for _ in range(10):
            selected = await _draw_diagnostic_items(db, student, topic)
            assert len(selected) == 5
            drawn_prereq = [i for i in selected if i.id in prereq_item_ids]
            assert not drawn_prereq, "weak-prereq slot fired with NO mastery history - should have fallen back to +1 medium instead"
