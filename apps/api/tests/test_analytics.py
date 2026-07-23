"""M6 analytics tests: misconception clustering (GROUP BY, threshold from analytics.yaml),
enrollment-archive respected in every aggregate, teacher-scoping 404s, the "ungraded" review-queue
signal, the "stuck" idle-session/diagnostic signal, and the flag-artifact action (F14).

Attempt/ItemOption/Misconception fixtures are built directly via the ORM rather than through a
real diagnostic round-trip - this module's own GROUP BY/threshold/scoping logic is what's under
test here, not the diagnostic draw (already covered by tests/test_learning.py) or bank generation
(tests/test_assessment.py) - same directness as tests/test_mastery.py's golden-vector approach.

Requires a real Postgres (DATABASE_URL) with migrations applied - same pattern as test_curriculum.py."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="requires DATABASE_URL (postgres)"),
]

import app.core.db as db_module  # noqa: E402
from app.core.db import (  # noqa: E402
    Attempt,
    DiagnosticSession,
    Event,
    GeneratedArtifact,
    Institution,
    Item,
    ItemOption,
    Misconception,
    SessionLocal,
    Subject,
    SubjectEnrollment,
    SubjectStaff,
    Topic,
    User,
)
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


async def _login(client: AsyncClient, slug: str, role: str, display_name: str) -> tuple[str, uuid.UUID]:
    identifier = f"{role}-{uuid.uuid4().hex[:6]}@test.local"
    user_id = uuid.uuid4()
    async with SessionLocal() as db:
        institution = (await db.execute(select(Institution).where(Institution.slug == slug))).scalar_one()
        db.add(User(
            id=user_id, institution_id=institution.id, role=role, display_name=display_name,
            roll_number=None, email=identifier, password_hash=hash_secret("userpass-1"),
            status="active", activation_code_hash=None, locale="en",
        ))
        await db.commit()
    res = await client.post("/api/auth/login", json={"institution_slug": slug, "identifier": identifier, "password": "userpass-1"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"], user_id


async def _subject_with_topic(slug: str, teacher_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    subject_id, topic_id = uuid.uuid4(), uuid.uuid4()
    async with SessionLocal() as db:
        institution = (await db.execute(select(Institution).where(Institution.slug == slug))).scalar_one()
        db.add(Subject(id=subject_id, institution_id=institution.id, created_by=teacher_id, name="DIP", code=None, term=None, status="published"))
        db.add(SubjectStaff(subject_id=subject_id, user_id=teacher_id))
        db.add(Topic(id=topic_id, kind="subject", subject_id=subject_id, title="Transforms", description=""))
        await db.commit()
    return subject_id, topic_id


async def _enroll(subject_id: uuid.UUID, user_id: uuid.UUID, status: str = "active") -> None:
    async with SessionLocal() as db:
        db.add(SubjectEnrollment(subject_id=subject_id, user_id=user_id, status=status))
        await db.commit()


async def _item_with_misconception(topic_id: uuid.UUID, code: str, title: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Returns (item_id, wrong_option_id) for one approved item whose sole wrong option under
    test carries the given (possibly shared) misconception code."""
    item_id, wrong_option_id = uuid.uuid4(), uuid.uuid4()
    async with SessionLocal() as db:
        misconception = (await db.execute(select(Misconception).where(Misconception.code == code))).scalar_one_or_none()
        if misconception is None:
            misconception = Misconception(id=uuid.uuid4(), code=code, title=title)
            db.add(misconception)
            await db.flush()
        db.add(Item(id=item_id, topic_id=topic_id, origin="ai", status="approved", stem="Q?", difficulty=0, explanation="because"))
        db.add(ItemOption(id=uuid.uuid4(), item_id=item_id, position=0, body="correct", is_correct=True))
        db.add(ItemOption(id=wrong_option_id, item_id=item_id, position=1, body="wrong", is_correct=False, misconception_id=misconception.id))
        await db.commit()
    return item_id, wrong_option_id


async def _wrong_attempt(user_id: uuid.UUID, item_id: uuid.UUID, option_id: uuid.UUID) -> None:
    async with SessionLocal() as db:
        db.add(Attempt(id=uuid.uuid4(), user_id=user_id, item_id=item_id, option_id=option_id, is_correct=False, context="diagnostic"))
        await db.commit()


async def test_misconception_cluster_appears_at_threshold_and_respects_archive(client: AsyncClient):
    slug = await _create_institution()
    teacher_token, teacher_id = await _login(client, slug, "teacher", "Teacher")
    subject_id, topic_id = await _subject_with_topic(slug, teacher_id)
    item_id, wrong_option_id = await _item_with_misconception(topic_id, "distributes_first_term_only", "Assumes distribution over only the first term")

    students = []
    for i in range(5):
        _, student_id = await _login(client, slug, "student", f"Student {i}")
        await _enroll(subject_id, student_id)
        await _wrong_attempt(student_id, item_id, wrong_option_id)
        students.append(student_id)

    res = await client.get("/api/analytics/today", headers=_auth(teacher_token))
    assert res.status_code == 200, res.text
    clusters = res.json()["clusters"]
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster["student_count"] == 5
    assert cluster["misconception_title"] == "Assumes distribution over only the first term"
    assert cluster["topic_id"] == str(topic_id)
    assert {s["id"] for s in cluster["students"]} == {str(s) for s in students}

    # Drill cluster -> student -> the exact wrong attempt.
    detail = (
        await client.get(
            f"/api/analytics/students/{students[0]}", params={"subject_id": str(subject_id)}, headers=_auth(teacher_token)
        )
    ).json()
    assert len(detail["wrong_attempts"]) == 1
    assert detail["wrong_attempts"][0]["misconception_title"] == "Assumes distribution over only the first term"
    assert detail["wrong_attempts"][0]["chosen_option_body"] == "wrong"

    # Archiving one contributor drops the cluster below threshold (Verify line: enrollment archive status respected).
    async with SessionLocal() as db:
        row = (
            await db.execute(
                select(SubjectEnrollment).where(SubjectEnrollment.subject_id == subject_id, SubjectEnrollment.user_id == students[0])
            )
        ).scalar_one()
        row.status = "archived"
        await db.commit()

    res2 = await client.get("/api/analytics/today", headers=_auth(teacher_token))
    assert res2.json()["clusters"] == []


async def test_cluster_below_threshold_does_not_appear(client: AsyncClient):
    slug = await _create_institution()
    teacher_token, teacher_id = await _login(client, slug, "teacher", "Teacher")
    subject_id, topic_id = await _subject_with_topic(slug, teacher_id)
    item_id, wrong_option_id = await _item_with_misconception(topic_id, "sign_error", "Sign error")

    for i in range(3):  # below the default threshold of 5
        _, student_id = await _login(client, slug, "student", f"Student {i}")
        await _enroll(subject_id, student_id)
        await _wrong_attempt(student_id, item_id, wrong_option_id)

    res = await client.get("/api/analytics/today", headers=_auth(teacher_token))
    assert res.json()["clusters"] == []


async def test_ungraded_signal_counts_draft_items(client: AsyncClient):
    slug = await _create_institution()
    teacher_token, teacher_id = await _login(client, slug, "teacher", "Teacher")
    subject_id, topic_id = await _subject_with_topic(slug, teacher_id)
    async with SessionLocal() as db:
        for _ in range(4):
            db.add(Item(id=uuid.uuid4(), topic_id=topic_id, origin="ai", status="draft", stem="Q?", difficulty=0, explanation=""))
        await db.commit()

    res = await client.get("/api/analytics/today", headers=_auth(teacher_token))
    ungraded = res.json()["ungraded"]
    assert len(ungraded) == 1
    assert ungraded[0]["topic_id"] == str(topic_id)
    assert ungraded[0]["draft_count"] == 4


async def test_stuck_signal_lists_idle_diagnostic(client: AsyncClient):
    slug = await _create_institution()
    teacher_token, teacher_id = await _login(client, slug, "teacher", "Teacher")
    subject_id, topic_id = await _subject_with_topic(slug, teacher_id)
    _, student_id = await _login(client, slug, "student", "Stalled Student")
    await _enroll(subject_id, student_id)

    stale = datetime.now(timezone.utc) - timedelta(minutes=30)
    async with SessionLocal() as db:
        db.add(DiagnosticSession(
            id=uuid.uuid4(), user_id=student_id, topic_id=topic_id, item_ids=[], score=None,
            completed_at=None, created_at=stale,
        ))
        await db.commit()

    res = await client.get("/api/analytics/today", headers=_auth(teacher_token))
    stuck = res.json()["stuck"]
    assert len(stuck) == 1
    assert stuck[0]["student_id"] == str(student_id)
    assert stuck[0]["kind"] == "diagnostic"
    assert stuck[0]["stalled_minutes"] >= 29


async def test_teacher_cannot_view_a_student_in_a_subject_they_dont_own(client: AsyncClient):
    slug_a = await _create_institution()
    slug_b = await _create_institution()
    _, teacher_a_id = await _login(client, slug_a, "teacher", "Teacher A")
    token_b, teacher_b_id = await _login(client, slug_b, "teacher", "Teacher B")
    subject_id, _ = await _subject_with_topic(slug_a, teacher_a_id)
    _, student_id = await _login(client, slug_a, "student", "Student")
    await _enroll(subject_id, student_id)

    res = await client.get(
        f"/api/analytics/students/{student_id}", params={"subject_id": str(subject_id)}, headers=_auth(token_b)
    )
    assert res.status_code == 404


async def test_flag_artifact_marks_flagged_and_emits_event(client: AsyncClient):
    slug = await _create_institution()
    teacher_token, teacher_id = await _login(client, slug, "teacher", "Teacher")
    subject_id, topic_id = await _subject_with_topic(slug, teacher_id)
    artifact_id = uuid.uuid4()
    async with SessionLocal() as db:
        db.add(GeneratedArtifact(
            id=artifact_id, scope="topic_shared", artifact_type="item_bank", topic_id=topic_id, user_id=None,
            cache_key=f"test-key-{uuid.uuid4().hex}", content={}, source_hash=None, prompt_version="v1", model="groq/test",
        ))
        await db.commit()

    res = await client.post(f"/api/analytics/artifacts/{artifact_id}/flag", headers=_auth(teacher_token))
    assert res.status_code == 200, res.text
    assert res.json()["flagged"] is True

    async with SessionLocal() as db:
        artifact = (await db.execute(select(GeneratedArtifact).where(GeneratedArtifact.id == artifact_id))).scalar_one()
        assert artifact.flagged is True
        events = (
            await db.execute(select(Event).where(Event.event_type == "artifact_flagged", Event.topic_id == topic_id))
        ).scalars().all()
        assert len(events) == 1
        assert events[0].user_id == teacher_id
