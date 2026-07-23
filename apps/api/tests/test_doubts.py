"""M6-remediation Phase 5 tests: topic-scoped doubt chat (modules/doubts.py, F11 minimal slice).

The core claim to prove: an ask against session A is grounded in session A's OWN topic content,
not session B's (or generic placeholder text) - not just "the endpoint returns some text". Proven
by building two topics with genuinely distinct mocked "core" segment content (a unique marker per
topic), asking against session A with a fake provider that echoes back exactly what grounding text
it was sent, and asserting topic A's marker is present while topic B's is absent from the answer -
plus a direct DB read confirming the stored Doubt row and doubt_asked event both reference the
correct topic, same evidentiary standard as every other module's test suite in this project.

Requires a real Postgres (DATABASE_URL) with migrations applied - same pattern as test_learning.py."""
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
from app.core.db import Doubt, Event, Institution, SessionLocal, SubjectEnrollment, User  # noqa: E402
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


def _mock_bank(n: int) -> ProviderResult:
    items = []
    for i in range(n):
        items.append({
            "stem": f"Question {i}?", "difficulty": [-1, 0, 0, 1][i % 4],
            "options": [
                {"body": "correct answer", "is_correct": True},
                {"body": "wrong 1", "is_correct": False, "misconception_code": "m1", "misconception_title": "M1"},
                {"body": "wrong 2", "is_correct": False, "misconception_code": "m2", "misconception_title": "M2"},
                {"body": "wrong 3", "is_correct": False, "misconception_code": "m3", "misconception_title": "M3"},
            ],
            "explanation": f"Stored reasoning {i}.",
        })
    return ProviderResult(text=json.dumps({"items": items}), input_tokens=100, output_tokens=200)


async def _build_published_topic(client: AsyncClient, teacher_token: str, title: str) -> tuple[str, str]:
    """Returns (subject_id, topic_id) for a fresh subject with one chapter (published) holding one topic block."""
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
    return subject["id"], topic["id"]


async def _enroll(subject_id: str, student_id: str) -> None:
    async with SessionLocal() as db:
        db.add(SubjectEnrollment(subject_id=uuid.UUID(subject_id), user_id=uuid.UUID(student_id), source_pool_id=None, status="active"))
        await db.commit()


async def _generate_and_approve(client: AsyncClient, teacher_token: str, topic_id: str, monkeypatch, n: int) -> None:
    async def _fake_invoke(model_cfg, *, system, prompt):
        return _mock_bank(n)

    monkeypatch.setattr(groq_provider, "invoke", _fake_invoke)
    res = await client.post(f"/api/assessment/topics/{topic_id}/bank/generate", headers=_auth(teacher_token))
    assert res.status_code == 200, res.text
    await client.post(f"/api/assessment/topics/{topic_id}/bank/approve-all", headers=_auth(teacher_token))


async def _run_and_complete_diagnostic(client: AsyncClient, student_token: str, topic_id: str) -> None:
    start = await client.post(f"/api/learning/topics/{topic_id}/diagnostic/start", headers=_auth(student_token))
    assert start.status_code == 200, start.text
    diagnostic_id = start.json()["diagnostic_id"]
    for item in start.json()["items"]:
        res = await client.post(
            f"/api/learning/diagnostic/{diagnostic_id}/answer", json={"item_id": item["id"], "option_id": item["options"][0]["id"]},
            headers=_auth(student_token),
        )
        assert res.status_code == 200, res.text


def _fake_segment_invoke_with_marker(marker: str):
    """Distinct 'core' segment content per topic, keyed by the topic_title the planner puts in its
    own prompt payload (modules/learning.py's _generate_segment render_user_prompt) - lets a test
    prove which topic's REAL content ended up in a session, not a coincidence of shared fixtures."""
    async def _invoke(model_cfg, *, system, prompt):
        payload = json.loads(prompt)
        kind = payload["kind"]
        if kind == "core":
            content = {
                "sections": [
                    {"heading": "The key idea here", "body": f"{marker} explains this topic in its own words."},
                    {"heading": "Seeing it in practice", "body": f"{marker} shows a concrete case."},
                    {"heading": "The formal picture", "body": f"{marker} states the general rule."},
                ],
                "worked_example": {"steps": [f"{marker} step one.", f"{marker} step two."]},
            }
        elif kind == "summary":
            content = {"bullets": [f"{marker} summary bullet."]}
        elif kind == "cheatsheet":
            content = {"text": f"{marker} cheatsheet."}
        else:
            raise AssertionError(f"unexpected segment kind in this test: {kind!r}")
        return ProviderResult(text=json.dumps(content), input_tokens=50, output_tokens=80)
    return _invoke


async def _start_session_with_marker(client: AsyncClient, student_token: str, topic_id: str, monkeypatch, marker: str) -> str:
    monkeypatch.setattr(groq_provider, "invoke", _fake_segment_invoke_with_marker(marker))
    res = await client.post(f"/api/learning/topics/{topic_id}/session/start", headers=_auth(student_token))
    assert res.status_code == 200, res.text
    return res.json()["session_id"]


async def test_ask_grounds_answer_in_this_sessions_own_topic_not_a_different_one(client: AsyncClient, monkeypatch):
    slug = await _create_institution()
    teacher_id, teacher_token = await _user(client, slug, "teacher")
    student_id, student_token = await _user(client, slug, "student")

    subject_a, topic_a = await _build_published_topic(client, teacher_token, title="Topic A")
    subject_b, topic_b = await _build_published_topic(client, teacher_token, title="Topic B")
    await _enroll(subject_a, student_id)
    await _enroll(subject_b, student_id)
    await _generate_and_approve(client, teacher_token, topic_a, monkeypatch, n=12)
    await _generate_and_approve(client, teacher_token, topic_b, monkeypatch, n=12)

    await _run_and_complete_diagnostic(client, student_token, topic_a)
    await _run_and_complete_diagnostic(client, student_token, topic_b)

    session_a = await _start_session_with_marker(client, student_token, topic_a, monkeypatch, "MARKER_ALPHA")
    session_b = await _start_session_with_marker(client, student_token, topic_b, monkeypatch, "MARKER_BETA")

    # The doubt-answering provider call: echo back exactly what grounding text it received, so the
    # test can inspect what modules/doubts.py actually assembled and sent, not just trust it.
    async def _fake_doubt_invoke(model_cfg, *, system, prompt):
        payload = json.loads(prompt)
        return ProviderResult(
            text=json.dumps({"answer": f"grounded-in:[{payload['lesson_content']}] question-was:[{payload['question']}]"}),
            input_tokens=30, output_tokens=40,
        )

    monkeypatch.setattr(groq_provider, "invoke", _fake_doubt_invoke)
    res = await client.post(
        f"/api/doubts/sessions/{session_a}/ask", json={"question": "why does this step work?"}, headers=_auth(student_token)
    )
    assert res.status_code == 200, res.text
    body = res.json()
    answer = body["answer"]

    # Real evidence, not an assertion that *some* text came back: session A's ask must be grounded
    # in topic A's own content and MUST NOT leak topic B's, proving the grounding is scoped to the
    # session's actual topic, not a global/shared/generic blob.
    assert "MARKER_ALPHA" in answer, f"expected topic A's own segment content in the grounded answer, got: {answer!r}"
    assert "MARKER_BETA" not in answer, f"topic B's content leaked into topic A's session ask: {answer!r}"
    assert "why does this step work?" in answer

    # Direct DB read (not just trusted from the API response) - the doubts table row and the
    # doubt_asked event both reference the CORRECT topic (topic A, not topic B or null).
    async with SessionLocal() as db:
        doubt = (await db.execute(select(Doubt).where(Doubt.id == uuid.UUID(body["doubt_id"])))).scalar_one()
        event = (
            await db.execute(select(Event).where(Event.event_type == "doubt_asked", Event.user_id == uuid.UUID(student_id)))
        ).scalar_one()

    assert str(doubt.matched_topic_id) == topic_a
    assert str(doubt.matched_topic_id) != topic_b
    assert doubt.raw_text == "why does this step work?"
    assert doubt.mode == "direct"
    assert doubt.status == "resolved"
    assert doubt.resolved_at is not None
    assert [t["role"] for t in doubt.transcript] == ["student", "ai"]
    assert doubt.transcript[1]["text"] == answer

    assert str(event.topic_id) == topic_a
    assert event.payload["doubt_id"] == body["doubt_id"]
    assert event.payload["session_id"] == session_a

    # session_b was built but never asked against - confirms the two sessions/topics are genuinely
    # independent fixtures, not a coincidence of test setup (also guards against a future change
    # accidentally making ask() ignore session_id and grab "the" session).
    assert session_b != session_a


async def test_ask_requires_the_callers_own_session(client: AsyncClient, monkeypatch):
    slug = await _create_institution()
    _, teacher_token = await _user(client, slug, "teacher")
    student_id, student_token = await _user(client, slug, "student")
    other_student_id, other_student_token = await _user(client, slug, "student")

    subject_id, topic_id = await _build_published_topic(client, teacher_token, title="Topic C")
    await _enroll(subject_id, student_id)
    await _generate_and_approve(client, teacher_token, topic_id, monkeypatch, n=12)
    await _run_and_complete_diagnostic(client, student_token, topic_id)
    session_id = await _start_session_with_marker(client, student_token, topic_id, monkeypatch, "MARKER_GAMMA")

    res = await client.post(
        f"/api/doubts/sessions/{session_id}/ask", json={"question": "is this mine?"}, headers=_auth(other_student_token)
    )
    assert res.status_code == 404, res.text


async def test_ask_rejects_empty_question(client: AsyncClient, monkeypatch):
    slug = await _create_institution()
    _, teacher_token = await _user(client, slug, "teacher")
    student_id, student_token = await _user(client, slug, "student")
    subject_id, topic_id = await _build_published_topic(client, teacher_token, title="Topic D")
    await _enroll(subject_id, student_id)
    await _generate_and_approve(client, teacher_token, topic_id, monkeypatch, n=12)
    await _run_and_complete_diagnostic(client, student_token, topic_id)
    session_id = await _start_session_with_marker(client, student_token, topic_id, monkeypatch, "MARKER_DELTA")

    res = await client.post(f"/api/doubts/sessions/{session_id}/ask", json={"question": "   "}, headers=_auth(student_token))
    assert res.status_code == 400, res.text
