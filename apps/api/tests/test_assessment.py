"""M4 assessment tests: item bank generation (idempotent items, real cache-hit on 2nd call),
teacher review queue, approve/approve-all, and topic-ownership scoping. Provider HTTP calls are
monkeypatched (see tests/test_ai_gateway.py for gateway-internals coverage) - these tests exercise
modules/assessment.py's own logic: what it does with a generation result.
Requires a real Postgres (DATABASE_URL) with migrations applied - same pattern as test_curriculum.py."""
from __future__ import annotations

import json
import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="requires DATABASE_URL (postgres)"),
]

import app.core.db as db_module  # noqa: E402
from app.ai.providers import ProviderResult  # noqa: E402
from app.ai.providers import groq as groq_provider  # noqa: E402
from app.core.db import Institution, Item, SessionLocal, User  # noqa: E402
from app.core.security import hash_secret  # noqa: E402
from app.main import app  # noqa: E402


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


async def _create_institution() -> str:
    slug = f"test-{uuid.uuid4().hex[:8]}"
    async with SessionLocal() as db:
        db.add(Institution(id=uuid.uuid4(), name="Test Institution", slug=slug, is_personal=False))
        await db.commit()
    return slug


async def _teacher(client: AsyncClient, slug: str) -> str:
    identifier = f"teacher-{uuid.uuid4().hex[:6]}@test.local"
    async with SessionLocal() as db:
        institution = (await db.execute(select(Institution).where(Institution.slug == slug))).scalar_one()
        db.add(User(
            id=uuid.uuid4(), institution_id=institution.id, role="teacher", display_name="Teacher",
            roll_number=None, email=identifier, password_hash=hash_secret("userpass-1"),
            status="active", activation_code_hash=None, locale="en",
        ))
        await db.commit()
    res = await client.post("/api/auth/login", json={"institution_slug": slug, "identifier": identifier, "password": "userpass-1"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


async def _topic(client: AsyncClient, token: str) -> tuple[str, str]:
    """Returns (subject_id, topic_id) for a fresh subject+topic owned by this teacher token."""
    subject = (await client.post("/api/curriculum/subjects", json={"name": f"Subject {uuid.uuid4().hex[:6]}"}, headers=_auth(token))).json()
    topic = (
        await client.post(f"/api/curriculum/subjects/{subject['id']}/topics", json={"title": "Transforms"}, headers=_auth(token))
    ).json()
    return subject["id"], topic["id"]


def _mock_bank(n: int = 5) -> ProviderResult:
    items = []
    for i in range(n):
        items.append({
            "stem": f"Question {i}?",
            "difficulty": [-1, 0, 0, 1][i % 4],
            "options": [
                {"body": "correct answer", "is_correct": True},
                {"body": "wrong 1", "is_correct": False, "misconception_code": "sign_error", "misconception_title": "Sign error"},
                {"body": "wrong 2", "is_correct": False, "misconception_code": "off_by_one", "misconception_title": "Off by one"},
                {"body": "wrong 3", "is_correct": False, "misconception_code": "sign_error", "misconception_title": "Sign error"},
            ],
            "explanation": f"Because reasons {i}.",
        })
    return ProviderResult(text=json.dumps({"items": items}), input_tokens=100, output_tokens=200)


async def test_generate_bank_creates_draft_items_with_valid_shape(client: AsyncClient, monkeypatch):
    async def _fake_invoke(model_cfg, *, system, prompt):
        return _mock_bank(6)

    monkeypatch.setattr(groq_provider, "invoke", _fake_invoke)
    slug = await _create_institution()
    token = await _teacher(client, slug)
    _, topic_id = await _topic(client, token)

    res = await client.post(f"/api/assessment/topics/{topic_id}/bank/generate", headers=_auth(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["generated"] is True
    assert body["cache_hit"] is False
    assert len(body["items"]) == 6
    for item in body["items"]:
        assert item["status"] == "draft"
        assert len(item["options"]) == 4
        correct = [o for o in item["options"] if o["is_correct"]]
        assert len(correct) == 1
        wrong = [o for o in item["options"] if not o["is_correct"]]
        assert all(o["misconception"]["code"] for o in wrong)


async def test_second_generate_is_cache_hit_and_does_not_duplicate_items(client: AsyncClient, monkeypatch):
    calls = {"n": 0}

    async def _fake_invoke(model_cfg, *, system, prompt):
        calls["n"] += 1
        return _mock_bank(5)

    monkeypatch.setattr(groq_provider, "invoke", _fake_invoke)
    slug = await _create_institution()
    token = await _teacher(client, slug)
    _, topic_id = await _topic(client, token)

    first = await client.post(f"/api/assessment/topics/{topic_id}/bank/generate", headers=_auth(token))
    assert first.json()["cache_hit"] is False
    assert calls["n"] == 1

    second = await client.post(f"/api/assessment/topics/{topic_id}/bank/generate", headers=_auth(token))
    assert second.status_code == 200
    assert second.json()["cache_hit"] is True
    assert second.json()["generated"] is False
    assert calls["n"] == 1  # provider not called again

    async with SessionLocal() as db:
        count = len((await db.execute(select(Item).where(Item.topic_id == uuid.UUID(topic_id)))).scalars().all())
    assert count == 5  # not 10 - no duplicate items from the second call


async def test_approve_all_flips_status_and_only_touches_drafts(client: AsyncClient, monkeypatch):
    async def _fake_invoke(model_cfg, *, system, prompt):
        return _mock_bank(4)

    monkeypatch.setattr(groq_provider, "invoke", _fake_invoke)
    slug = await _create_institution()
    token = await _teacher(client, slug)
    _, topic_id = await _topic(client, token)

    await client.post(f"/api/assessment/topics/{topic_id}/bank/generate", headers=_auth(token))
    bank = (await client.get(f"/api/assessment/topics/{topic_id}/bank", headers=_auth(token))).json()
    assert all(i["status"] == "draft" for i in bank)

    res = await client.post(f"/api/assessment/topics/{topic_id}/bank/approve-all", headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["approved"] == 4

    bank_after = (await client.get(f"/api/assessment/topics/{topic_id}/bank", headers=_auth(token))).json()
    assert all(i["status"] == "approved" for i in bank_after)

    # Re-running approve-all touches nothing new (all items already approved, none left in draft).
    res2 = await client.post(f"/api/assessment/topics/{topic_id}/bank/approve-all", headers=_auth(token))
    assert res2.json()["approved"] == 0


async def test_teacher_cannot_generate_bank_for_a_topic_they_dont_own(client: AsyncClient):
    slug_a = await _create_institution()
    slug_b = await _create_institution()
    token_a = await _teacher(client, slug_a)
    token_b = await _teacher(client, slug_b)
    _, topic_id = await _topic(client, token_a)

    res = await client.post(f"/api/assessment/topics/{topic_id}/bank/generate", headers=_auth(token_b))
    assert res.status_code == 404
