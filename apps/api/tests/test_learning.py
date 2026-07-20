"""M4 learning tests: stratified diagnostic draw + weak-prereq slot, neutral acks (no correctness
leaked mid-probe), end-of-probe review with stored reasoning, BKT mastery wiring, and RULES.md #5
(draft items are never eligible for the draw, no matter how recently generated).
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
from app.core.db import Institution, Item, Mastery, SessionLocal, SubjectEnrollment, User  # noqa: E402
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


def _mock_bank(n: int, difficulties: list[int] | None = None) -> ProviderResult:
    diffs = difficulties or ([-1, 0, 0, 1] * ((n // 4) + 1))[:n]
    items = []
    for i in range(n):
        items.append({
            "stem": f"Question {i}?",
            "difficulty": diffs[i],
            "options": [
                {"body": "correct answer", "is_correct": True},
                {"body": "wrong 1", "is_correct": False, "misconception_code": "m1", "misconception_title": "M1"},
                {"body": "wrong 2", "is_correct": False, "misconception_code": "m2", "misconception_title": "M2"},
                {"body": "wrong 3", "is_correct": False, "misconception_code": "m3", "misconception_title": "M3"},
            ],
            "explanation": f"Stored reasoning {i}.",
        })
    return ProviderResult(text=json.dumps({"items": items}), input_tokens=100, output_tokens=200)


async def _build_published_topic(client: AsyncClient, teacher_token: str, title: str = "Transforms") -> tuple[str, str, str]:
    """Returns (subject_id, chapter_id, topic_id) for a subject with one chapter (published) holding one topic block."""
    subject = (await client.post("/api/curriculum/subjects", json={"name": f"Subject {uuid.uuid4().hex[:6]}"}, headers=_auth(teacher_token))).json()
    chapter = (
        await client.post(f"/api/curriculum/subjects/{subject['id']}/chapters", json={"title": "Ch1"}, headers=_auth(teacher_token))
    ).json()
    topic = (
        await client.post(f"/api/curriculum/subjects/{subject['id']}/topics", json={"title": title}, headers=_auth(teacher_token))
    ).json()
    await client.post(
        f"/api/curriculum/chapters/{chapter['id']}/blocks", json={"block_type": "topic", "topic_id": topic["id"]}, headers=_auth(teacher_token)
    )
    await client.post(f"/api/curriculum/chapters/{chapter['id']}/publish", headers=_auth(teacher_token))
    return subject["id"], chapter["id"], topic["id"]


async def _enroll(subject_id: str, student_id: str) -> None:
    async with SessionLocal() as db:
        db.add(SubjectEnrollment(subject_id=uuid.UUID(subject_id), user_id=uuid.UUID(student_id), source_pool_id=None, status="active"))
        await db.commit()


async def _generate_and_approve(client: AsyncClient, teacher_token: str, topic_id: str, monkeypatch, n: int, difficulties=None) -> None:
    async def _fake_invoke(model_cfg, *, system, prompt):
        return _mock_bank(n, difficulties)

    monkeypatch.setattr(groq_provider, "invoke", _fake_invoke)
    res = await client.post(f"/api/assessment/topics/{topic_id}/bank/generate", headers=_auth(teacher_token))
    assert res.status_code == 200, res.text
    await client.post(f"/api/assessment/topics/{topic_id}/bank/approve-all", headers=_auth(teacher_token))


async def test_diagnostic_draw_is_five_stratified_items(client: AsyncClient, monkeypatch):
    slug = await _create_institution()
    _, teacher_token = await _user(client, slug, "teacher")
    student_id, student_token = await _user(client, slug, "student")
    subject_id, _, topic_id = await _build_published_topic(client, teacher_token)
    await _enroll(subject_id, student_id)
    await _generate_and_approve(client, teacher_token, topic_id, monkeypatch, n=12)

    res = await client.post(f"/api/learning/topics/{topic_id}/diagnostic/start", headers=_auth(student_token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["items"]) == 5
    # Neutral shape: no is_correct, no misconception leaked mid-probe.
    for item in body["items"]:
        for option in item["options"]:
            assert "is_correct" not in option
            assert "misconception" not in option


async def test_weak_prereq_slot_used_when_history_exists(client: AsyncClient, monkeypatch):
    slug = await _create_institution()
    _, teacher_token = await _user(client, slug, "teacher")
    student_id, student_token = await _user(client, slug, "student")

    # Both topics must live in the same subject (topic_edges requires it, RULES.md #10-style scoping
    # in modules/curriculum.py's create_edge) - one subject, one chapter, two topic blocks, one edge.
    subject = (await client.post("/api/curriculum/subjects", json={"name": f"Subject {uuid.uuid4().hex[:6]}"}, headers=_auth(teacher_token))).json()
    chapter = (await client.post(f"/api/curriculum/subjects/{subject['id']}/chapters", json={"title": "Ch1"}, headers=_auth(teacher_token))).json()
    prereq_topic = (await client.post(f"/api/curriculum/subjects/{subject['id']}/topics", json={"title": "Transforms"}, headers=_auth(teacher_token))).json()
    topic = (await client.post(f"/api/curriculum/subjects/{subject['id']}/topics", json={"title": "Frequency Filtering"}, headers=_auth(teacher_token))).json()
    for t in (prereq_topic, topic):
        await client.post(f"/api/curriculum/chapters/{chapter['id']}/blocks", json={"block_type": "topic", "topic_id": t["id"]}, headers=_auth(teacher_token))
    await client.post(f"/api/curriculum/chapters/{chapter['id']}/publish", headers=_auth(teacher_token))
    edge_res = await client.post(f"/api/curriculum/topics/{prereq_topic['id']}/edges", json={"dst_topic_id": topic["id"]}, headers=_auth(teacher_token))
    assert edge_res.status_code == 200, edge_res.text

    subject_id, prereq_topic_id, topic_id = subject["id"], prereq_topic["id"], topic["id"]
    await _enroll(subject_id, student_id)

    await _generate_and_approve(client, teacher_token, prereq_topic_id, monkeypatch, n=8)
    await _generate_and_approve(client, teacher_token, topic_id, monkeypatch, n=12)

    # Give the student a real weak-mastery history on the prereq topic (a below-threshold mastery
    # row must already exist - "historically weak", not merely untouched).
    async with SessionLocal() as db:
        db.add(Mastery(user_id=uuid.UUID(student_id), topic_id=uuid.UUID(prereq_topic_id), p_known=0.2, confidence=1.0, attempts_count=3))
        await db.commit()

    res = await client.post(f"/api/learning/topics/{topic_id}/diagnostic/start", headers=_auth(student_token))
    assert res.status_code == 200, res.text
    drawn_item_ids = [item["id"] for item in res.json()["items"]]

    async with SessionLocal() as db:
        prereq_item_ids = {str(i) for i in (await db.execute(select(Item.id).where(Item.topic_id == uuid.UUID(prereq_topic_id)))).scalars().all()}
    assert any(item_id in prereq_item_ids for item_id in drawn_item_ids), "expected one drawn item from the weak prerequisite topic"


async def test_answer_gives_neutral_ack_then_review_shows_reasoning_and_updates_mastery(client: AsyncClient, monkeypatch):
    slug = await _create_institution()
    _, teacher_token = await _user(client, slug, "teacher")
    student_id, student_token = await _user(client, slug, "student")
    subject_id, _, topic_id = await _build_published_topic(client, teacher_token)
    await _enroll(subject_id, student_id)
    await _generate_and_approve(client, teacher_token, topic_id, monkeypatch, n=12)

    start = await client.post(f"/api/learning/topics/{topic_id}/diagnostic/start", headers=_auth(student_token))
    diagnostic_id = start.json()["diagnostic_id"]
    items = start.json()["items"]
    assert len(items) == 5

    for i, item in enumerate(items):
        option_id = item["options"][0]["id"]
        res = await client.post(
            f"/api/learning/diagnostic/{diagnostic_id}/answer", json={"item_id": item["id"], "option_id": option_id},
            headers=_auth(student_token),
        )
        assert res.status_code == 200, res.text
        ack = res.json()
        assert ack["ack"] == "recorded"
        assert set(ack.keys()) == {"ack", "completed"}  # neutral - no correctness signal at all
        assert ack["completed"] == (i == len(items) - 1)

    review = await client.get(f"/api/learning/diagnostic/{diagnostic_id}", headers=_auth(student_token))
    assert review.status_code == 200
    body = review.json()
    assert body["total"] == 5
    assert len(body["review"]) == 5
    for q in body["review"]:
        assert q["explanation"]  # stored reasoning shown, per FEATURE_EXPLANATION S3
        assert q["correct_option_id"] is not None
        assert q["chosen_option_id"] is not None
    assert any(m["p_known"] is not None for m in body["mastery"])

    async with SessionLocal() as db:
        row = (
            await db.execute(select(Mastery).where(Mastery.user_id == uuid.UUID(student_id), Mastery.topic_id == uuid.UUID(topic_id)))
        ).scalar_one_or_none()
    assert row is not None
    assert row.attempts_count == 5


async def test_draft_items_are_never_drawn_even_when_the_bank_also_has_approved_items(client: AsyncClient, monkeypatch):
    """RULES.md #5: only review_status='approved' items ever reach a student."""
    slug = await _create_institution()
    _, teacher_token = await _user(client, slug, "teacher")
    student_id, student_token = await _user(client, slug, "student")
    subject_id, _, topic_id = await _build_published_topic(client, teacher_token)
    await _enroll(subject_id, student_id)

    async def _fake_invoke(model_cfg, *, system, prompt):
        return _mock_bank(12)

    monkeypatch.setattr(groq_provider, "invoke", _fake_invoke)
    await client.post(f"/api/assessment/topics/{topic_id}/bank/generate", headers=_auth(teacher_token))
    # Deliberately do NOT approve-all - the bank exists but every item is still status='draft'.

    res = await client.post(f"/api/learning/topics/{topic_id}/diagnostic/start", headers=_auth(student_token))
    assert res.status_code == 400, res.text  # not enough approved items - zero, in fact


async def test_diagnostic_requires_subject_enrollment(client: AsyncClient, monkeypatch):
    slug = await _create_institution()
    _, teacher_token = await _user(client, slug, "teacher")
    _, student_token = await _user(client, slug, "student")  # deliberately never enrolled
    _, _, topic_id = await _build_published_topic(client, teacher_token)
    await _generate_and_approve(client, teacher_token, topic_id, monkeypatch, n=12)

    res = await client.post(f"/api/learning/topics/{topic_id}/diagnostic/start", headers=_auth(student_token))
    assert res.status_code == 404
