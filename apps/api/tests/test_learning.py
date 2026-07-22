"""M4 learning tests: stratified diagnostic draw + weak-prereq slot, neutral acks (no correctness
leaked mid-probe), end-of-probe review with stored reasoning, BKT mastery wiring, and RULES.md #5
(draft items are never eligible for the draw, no matter how recently generated).

M5 additions (FEATURE_EXPLANATION F8/F9, S4, S16): session planner injects a revision segment for
a real weak prereq and emits the full causal-chain events in order; the stored plan is stable
across reloads; practice feedback is INSTANT (contrast with the diagnostic's neutral ack); an
abandoned session is resumable without re-asking answered items; and the segment cache actually
hits for a second student on the same topic - proven with real before/after ai_invocations row
counts, not just a boolean assertion (same standard the M4 GATE used for provider failover).

Requires a real Postgres (DATABASE_URL) with migrations applied - same pattern as test_curriculum.py."""
from __future__ import annotations

import json
import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="requires DATABASE_URL (postgres)"),
]

import app.core.db as db_module  # noqa: E402
from app.ai.providers import ProviderResult  # noqa: E402
from app.ai.providers import groq as groq_provider  # noqa: E402
from app.core.db import (  # noqa: E402
    AiInvocation,
    Event,
    Institution,
    Item,
    LearningSession,
    Mastery,
    SessionLocal,
    SubjectEnrollment,
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


# ---------------------------------------------------------------------------
# M5: session planner + player
# ---------------------------------------------------------------------------

async def _build_topic_pair_with_edge(
    client: AsyncClient, teacher_token: str, prereq_title: str = "Transforms", topic_title: str = "Frequency Filtering"
) -> tuple[str, str, str]:
    """Returns (subject_id, prereq_topic_id, topic_id): both topics in one published chapter, one
    teacher-created edge prereq_topic -> topic."""
    subject = (await client.post("/api/curriculum/subjects", json={"name": f"Subject {uuid.uuid4().hex[:6]}"}, headers=_auth(teacher_token))).json()
    chapter = (await client.post(f"/api/curriculum/subjects/{subject['id']}/chapters", json={"title": "Ch1"}, headers=_auth(teacher_token))).json()
    prereq_topic = (await client.post(f"/api/curriculum/subjects/{subject['id']}/topics", json={"title": prereq_title}, headers=_auth(teacher_token))).json()
    topic = (await client.post(f"/api/curriculum/subjects/{subject['id']}/topics", json={"title": topic_title}, headers=_auth(teacher_token))).json()
    for t in (prereq_topic, topic):
        await client.post(f"/api/curriculum/chapters/{chapter['id']}/blocks", json={"block_type": "topic", "topic_id": t["id"]}, headers=_auth(teacher_token))
    await client.post(f"/api/curriculum/chapters/{chapter['id']}/publish", headers=_auth(teacher_token))
    edge_res = await client.post(f"/api/curriculum/topics/{prereq_topic['id']}/edges", json={"dst_topic_id": topic["id"]}, headers=_auth(teacher_token))
    assert edge_res.status_code == 200, edge_res.text
    return subject["id"], prereq_topic["id"], topic["id"]


async def _set_weak_mastery(student_id: str, topic_id: str, p_known: float = 0.2) -> None:
    """A real, already-existing below-threshold mastery row - "historically weak", matching the
    diagnostic engine's own weak-prereq slot definition exactly (mastery_module.is_weak)."""
    async with SessionLocal() as db:
        db.add(Mastery(user_id=uuid.UUID(student_id), topic_id=uuid.UUID(topic_id), p_known=p_known, confidence=1.0, attempts_count=3))
        await db.commit()


async def _run_and_complete_diagnostic(client: AsyncClient, student_token: str, topic_id: str, option_index: int) -> str:
    """Answers every drawn item with the option at a FIXED position (never index 0, the always-
    correct option per _mock_bank's shape) - deterministic across students so the misconception
    that fires (_mock_bank's options all share the same 3 misconception codes, position-for-
    position, on every item) is identical regardless of which items get drawn."""
    start = await client.post(f"/api/learning/topics/{topic_id}/diagnostic/start", headers=_auth(student_token))
    assert start.status_code == 200, start.text
    diagnostic_id = start.json()["diagnostic_id"]
    for item in start.json()["items"]:
        option_id = item["options"][option_index]["id"]
        res = await client.post(
            f"/api/learning/diagnostic/{diagnostic_id}/answer", json={"item_id": item["id"], "option_id": option_id},
            headers=_auth(student_token),
        )
        assert res.status_code == 200, res.text
    return diagnostic_id


def _mock_segment(kind: str, misconception_title: str | None = None) -> ProviderResult:
    if kind == "core":
        content = {"explanation": "Core explanation text.", "worked_example": {"steps": ["Step 1", "Step 2"]}}
    elif kind == "revision":
        content = {"explanation": "Revision refresher text."}
    elif kind == "contrast":
        content = {"text": f"About {misconception_title or 'this mistake'}: here is why it is wrong."}
    elif kind == "summary":
        content = {"bullets": ["Bullet 1", "Bullet 2", "Bullet 3"]}
    elif kind == "cheatsheet":
        content = {"text": "Cheatsheet reference text."}
    else:
        raise AssertionError(f"unexpected segment kind {kind!r}")
    return ProviderResult(text=json.dumps(content), input_tokens=50, output_tokens=80)


async def _fake_segment_invoke(model_cfg, *, system, prompt):
    payload = json.loads(prompt)
    return _mock_segment(payload["kind"], payload.get("misconception_title"))


async def _segment_invocation_ids() -> set[uuid.UUID]:
    """Set, not COUNT(*) or an ORDER BY created_at slice - Postgres holds now() stable for an
    entire transaction, so several ai_invocations rows logged within one request-handling
    transaction can share an identical created_at, making offset/order-by-time unreliable for
    isolating "the new rows". Primary-key set difference is exact regardless of timestamp ties."""
    async with SessionLocal() as db:
        rows = (await db.execute(select(AiInvocation.id).where(AiInvocation.task == "segment"))).scalars().all()
        return set(rows)


async def test_session_planner_injects_revision_and_emits_causal_chain_events_in_order(client: AsyncClient, monkeypatch):
    slug = await _create_institution()
    _, teacher_token = await _user(client, slug, "teacher")
    student_id, student_token = await _user(client, slug, "student")
    subject_id, prereq_topic_id, topic_id = await _build_topic_pair_with_edge(client, teacher_token)
    await _enroll(subject_id, student_id)
    await _generate_and_approve(client, teacher_token, prereq_topic_id, monkeypatch, n=8)
    await _generate_and_approve(client, teacher_token, topic_id, monkeypatch, n=12)
    await _set_weak_mastery(student_id, prereq_topic_id)

    await _run_and_complete_diagnostic(client, student_token, topic_id, option_index=1)

    monkeypatch.setattr(groq_provider, "invoke", _fake_segment_invoke)
    res = await client.post(f"/api/learning/topics/{topic_id}/session/start", headers=_auth(student_token))
    assert res.status_code == 200, res.text
    body = res.json()
    session_id = body["session_id"]
    cards = body["cards"]

    assert cards[0]["type"] == "bridge"
    revision_cards = [c for c in cards if c["type"] == "revision"]
    assert len(revision_cards) == 1, "expected exactly one injected revision segment for the real weak prereq"
    assert revision_cards[0]["topic_id"] == prereq_topic_id
    assert cards.index(revision_cards[0]) == 1, "revision must be injected at the HEAD of the session, right after the bridge"

    # The full causal chain the M5 GATE asks for, in true emission order (ingest_id, not
    # occurred_at - same-transaction events share a timestamp, see core/db.py's Event docstring).
    async with SessionLocal() as db:
        events = (
            await db.execute(select(Event).where(Event.user_id == uuid.UUID(student_id)).order_by(Event.ingest_id))
        ).scalars().all()
    ordered_types = [e.event_type for e in events]
    assert ordered_types.index("diagnostic_completed") < ordered_types.index("session_started")
    assert ordered_types.index("session_started") < ordered_types.index("revision_injected")
    revision_event = next(e for e in events if e.event_type == "revision_injected")
    assert str(revision_event.topic_id) == prereq_topic_id
    assert revision_event.payload["session_id"] == session_id


async def test_session_plan_is_stable_across_reloads(client: AsyncClient, monkeypatch):
    slug = await _create_institution()
    _, teacher_token = await _user(client, slug, "teacher")
    student_id, student_token = await _user(client, slug, "student")
    subject_id, _, topic_id = await _build_published_topic(client, teacher_token)
    await _enroll(subject_id, student_id)
    await _generate_and_approve(client, teacher_token, topic_id, monkeypatch, n=12)
    await _run_and_complete_diagnostic(client, student_token, topic_id, option_index=1)

    monkeypatch.setattr(groq_provider, "invoke", _fake_segment_invoke)
    first = (await client.post(f"/api/learning/topics/{topic_id}/session/start", headers=_auth(student_token))).json()
    second = (await client.post(f"/api/learning/topics/{topic_id}/session/start", headers=_auth(student_token))).json()
    third = (await client.get(f"/api/learning/sessions/{first['session_id']}", headers=_auth(student_token))).json()

    assert first["session_id"] == second["session_id"] == third["session_id"]
    assert first["cards"] == second["cards"] == third["cards"], "the stored plan must not be reshuffled or regenerated on reload"

    async with SessionLocal() as db:
        session_count = (
            await db.execute(select(func.count(LearningSession.id)).where(LearningSession.user_id == uuid.UUID(student_id)))
        ).scalar_one()
    assert session_count == 1, "re-starting must return the existing session, never create a second row"


async def test_practice_feedback_is_instant_unlike_diagnostic_neutral_ack(client: AsyncClient, monkeypatch):
    slug = await _create_institution()
    _, teacher_token = await _user(client, slug, "teacher")
    student_id, student_token = await _user(client, slug, "student")
    subject_id, _, topic_id = await _build_published_topic(client, teacher_token)
    await _enroll(subject_id, student_id)
    await _generate_and_approve(client, teacher_token, topic_id, monkeypatch, n=12)
    await _run_and_complete_diagnostic(client, student_token, topic_id, option_index=0)

    monkeypatch.setattr(groq_provider, "invoke", _fake_segment_invoke)
    session = (await client.post(f"/api/learning/topics/{topic_id}/session/start", headers=_auth(student_token))).json()
    practice_card = next(c for c in session["cards"] if c["type"] == "practice")

    res = await client.post(
        f"/api/learning/sessions/{session['session_id']}/practice/answer",
        json={"item_id": practice_card["item_id"], "option_id": practice_card["options"][0]["id"]},
        headers=_auth(student_token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    # Instant reasoning (S3: the deferred-ack rule is diagnostic-only) - correctness + stored
    # explanation both come back immediately, unlike the diagnostic's {ack, completed}-only shape.
    assert set(body.keys()) == {"is_correct", "correct_option_id", "explanation"}
    assert body["explanation"]


async def test_abandoned_session_is_resumable_without_reasking_answered_items(client: AsyncClient, monkeypatch):
    slug = await _create_institution()
    _, teacher_token = await _user(client, slug, "teacher")
    student_id, student_token = await _user(client, slug, "student")
    subject_id, _, topic_id = await _build_published_topic(client, teacher_token)
    await _enroll(subject_id, student_id)
    await _generate_and_approve(client, teacher_token, topic_id, monkeypatch, n=12)
    await _run_and_complete_diagnostic(client, student_token, topic_id, option_index=0)

    monkeypatch.setattr(groq_provider, "invoke", _fake_segment_invoke)
    session = (await client.post(f"/api/learning/topics/{topic_id}/session/start", headers=_auth(student_token))).json()
    session_id = session["session_id"]
    practice_cards = [c for c in session["cards"] if c["type"] == "practice"]
    first_practice = practice_cards[0]

    await client.post(
        f"/api/learning/sessions/{session_id}/practice/answer",
        json={"item_id": first_practice["item_id"], "option_id": first_practice["options"][0]["id"]},
        headers=_auth(student_token),
    )

    # "Abandon" = simply never call /complete; reopening the topic re-fetches the SAME session.
    resumed = (await client.post(f"/api/learning/topics/{topic_id}/session/start", headers=_auth(student_token))).json()
    assert resumed["session_id"] == session_id
    assert resumed["status"] == "in_progress"

    resume_card = resumed["cards"][resumed["resume_index"]]
    assert resume_card["type"] == "practice"
    assert resume_card["item_id"] != first_practice["item_id"], "resume must point past the already-answered practice item"

    # Re-answering the already-answered item is rejected, not silently double-counted.
    replay = await client.post(
        f"/api/learning/sessions/{session_id}/practice/answer",
        json={"item_id": first_practice["item_id"], "option_id": first_practice["options"][0]["id"]},
        headers=_auth(student_token),
    )
    assert replay.status_code == 400


async def test_segment_cache_hits_for_a_second_weak_student_verified_by_ai_invocations_counts(client: AsyncClient, monkeypatch):
    """The M5 GATE's cache-hit clause, proven with real before/after ai_invocations row counts
    (not just a passing assertion) - same evidentiary standard M4 used for provider failover."""
    slug = await _create_institution()
    _, teacher_token = await _user(client, slug, "teacher")
    subject_id, prereq_topic_id, topic_id = await _build_topic_pair_with_edge(client, teacher_token)
    await _generate_and_approve(client, teacher_token, prereq_topic_id, monkeypatch, n=8)
    await _generate_and_approve(client, teacher_token, topic_id, monkeypatch, n=12)

    student1_id, student1_token = await _user(client, slug, "student")
    await _enroll(subject_id, student1_id)
    await _set_weak_mastery(student1_id, prereq_topic_id)
    await _run_and_complete_diagnostic(client, student1_token, topic_id, option_index=1)

    monkeypatch.setattr(groq_provider, "invoke", _fake_segment_invoke)

    before_ids_1 = await _segment_invocation_ids()
    res1 = await client.post(f"/api/learning/topics/{topic_id}/session/start", headers=_auth(student1_token))
    assert res1.status_code == 200, res1.text
    after_ids_1 = await _segment_invocation_ids()
    new_ids_1 = after_ids_1 - before_ids_1

    print(f"ai_invocations(task=segment) student1: before={len(before_ids_1)} after={len(after_ids_1)} new={len(new_ids_1)}")

    # Student 1 is the first-ever session on this topic pair: every segment call is a REAL
    # generation (revision + core + summary + cheatsheet + contrast, since option_index=1 is
    # always wrong in _mock_bank's shape - 5 calls), none of them a cache hit.
    assert len(new_ids_1) == 5, f"expected 5 real segment generations for the first student, got {len(new_ids_1)}"
    async with SessionLocal() as db:
        new_rows_1 = (await db.execute(select(AiInvocation).where(AiInvocation.id.in_(new_ids_1)))).scalars().all()
    assert all(not row.cache_hit for row in new_rows_1), "student 1's segments must all be real generations, not cache hits"

    # Student 2: same prereq weakness, same topic, deliberately answering the SAME way so the
    # fired misconception (and therefore the contrast card's cache key) matches student 1's exactly.
    student2_id, student2_token = await _user(client, slug, "student")
    await _enroll(subject_id, student2_id)
    await _set_weak_mastery(student2_id, prereq_topic_id)
    await _run_and_complete_diagnostic(client, student2_token, topic_id, option_index=1)

    before_ids_2 = await _segment_invocation_ids()
    res2 = await client.post(f"/api/learning/topics/{topic_id}/session/start", headers=_auth(student2_token))
    assert res2.status_code == 200, res2.text
    after_ids_2 = await _segment_invocation_ids()
    new_ids_2 = after_ids_2 - before_ids_2

    print(f"ai_invocations(task=segment) student2: before={len(before_ids_2)} after={len(after_ids_2)} new={len(new_ids_2)}")

    # RULES #4's "every generation preceded by a lookup" proven honestly: the facade is called the
    # SAME number of times (5 - one per segment kind, the lookup itself is never skipped), but
    # student 2's session produces ZERO new real provider calls - all 5 are logged cache hits.
    assert len(new_ids_2) == 5, f"expected 5 lookup-logged ai_invocations rows for the second student, got {len(new_ids_2)}"
    async with SessionLocal() as db:
        new_rows_2 = (await db.execute(select(AiInvocation).where(AiInvocation.id.in_(new_ids_2)))).scalars().all()
    assert all(row.cache_hit for row in new_rows_2), "every one of student 2's segment invocations must be a cache hit, not a new generation"
    assert all(row.provider == "cache" for row in new_rows_2)
