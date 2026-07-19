"""modules/learning: the diagnostic engine (FEATURE_EXPLANATION S3, ROADMAP M4) - stratified 5-item
draw + weak-prereq slot, neutral-ack probe, end-of-probe review with stored reasoning. Owns its
router, service functions, repository queries. Config via app.core.config.settings ONLY.
RULES.md #9: draw/selection is deterministic (random.choice over an already-approved pool) -
no LLM involved. RULES.md #5: the draw pool is filtered to status='approved' only, always -
draft items are never eligible, regardless of how recently they were generated.

Session planner (F8, prereq revision injection into a full session) is explicitly M5 scope
(ROADMAP Avoid list) - this module stops at the end-of-probe review screen."""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import (
    Attempt,
    Chapter,
    ChapterBlock,
    DiagnosticSession,
    Item,
    ItemOption,
    SubjectEnrollment,
    Topic,
    TopicEdge,
    User,
    get_db,
    record_event,
)
from app.core.security import require_role
from app.modules import mastery as mastery_module

router = APIRouter(prefix="/api/learning", tags=["learning"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "not_found", "message": "Not found", "hint": "Check the id"})


def _bad_request(message: str, hint: str = "") -> HTTPException:
    return HTTPException(status_code=400, detail={"code": "bad_request", "message": message, "hint": hint})


async def _get_diagnosable_topic(db: AsyncSession, topic_id: uuid.UUID, student: User) -> Topic:
    """Enrolled + the topic must appear in a published chapter (drafts stay hidden - same
    invariant as modules/curriculum.py's student read surface)."""
    topic = (
        await db.execute(
            select(Topic)
            .join(ChapterBlock, ChapterBlock.topic_id == Topic.id)
            .join(Chapter, Chapter.id == ChapterBlock.chapter_id)
            .join(SubjectEnrollment, SubjectEnrollment.subject_id == Topic.subject_id)
            .where(
                Topic.id == topic_id, Topic.kind == "subject", Chapter.status == "published",
                SubjectEnrollment.user_id == student.id, SubjectEnrollment.status == "active",
            )
        )
    ).scalars().first()
    if topic is None:
        raise _not_found()
    return topic


async def _approved_items_by_topic(db: AsyncSession, topic_id: uuid.UUID) -> list[Item]:
    return (
        await db.execute(select(Item).where(Item.topic_id == topic_id, Item.status == "approved", Item.deleted_at.is_(None)))
    ).scalars().all()


async def _find_weak_prereq_item(db: AsyncSession, student: User, topic_id: uuid.UUID) -> Item | None:
    prereq_ids = (await db.execute(select(TopicEdge.src_topic_id).where(TopicEdge.dst_topic_id == topic_id))).scalars().all()
    random.shuffle(prereq_ids)
    for prereq_id in prereq_ids:
        if not await mastery_module.is_weak(db, user_id=student.id, topic_id=prereq_id):
            continue
        prereq_items = await _approved_items_by_topic(db, prereq_id)
        if prereq_items:
            return random.choice(prereq_items)
    return None


async def _draw_diagnostic_items(db: AsyncSession, student: User, topic: Topic) -> list[Item]:
    cfg = settings.get("database", "diagnostic", default={})
    probe_size = cfg.get("probe_size", 5)
    counts = {-1: cfg.get("easy", 1), 0: cfg.get("medium", 2), 1: cfg.get("hard", 1)}

    approved = await _approved_items_by_topic(db, topic.id)
    by_difficulty: dict[int, list[Item]] = {-1: [], 0: [], 1: []}
    for item in approved:
        by_difficulty.setdefault(item.difficulty, []).append(item)

    selected: list[Item] = []
    for difficulty, count in counts.items():
        pool = by_difficulty.get(difficulty, [])
        random.shuffle(pool)
        selected.extend(pool[:count])

    weak_item = await _find_weak_prereq_item(db, student, topic.id)
    if weak_item is not None:
        selected.append(weak_item)
    else:
        remaining = [i for i in approved if i not in selected]
        fallback_pool = [i for i in remaining if i.difficulty == 0] or remaining
        if fallback_pool:
            selected.append(random.choice(fallback_pool))

    # ponytail: graceful degradation, not a hard requirement - a thin/unbalanced bank still fills
    # the probe from whatever approved items remain rather than 500ing; upgrade to a hard minimum-
    # bank-size check at generation time if this ever proves confusing in practice.
    if len(selected) < probe_size:
        backfill = [i for i in approved if i not in selected]
        random.shuffle(backfill)
        selected.extend(backfill[: probe_size - len(selected)])

    if len(selected) < probe_size:
        raise _bad_request("Not enough approved items in this topic's bank yet", "Ask your teacher to approve more items")

    selected = selected[:probe_size]
    random.shuffle(selected)
    return selected


def _safe_option_out(option: ItemOption) -> dict:
    """Diagnostic-in-progress shape: no is_correct, no misconception - integrity of measurement
    (FEATURE_EXPLANATION S3: feedback deferred to end-of-probe)."""
    return {"id": str(option.id), "position": option.position, "body": option.body}


async def _items_with_options(db: AsyncSession, item_ids: list[uuid.UUID]) -> tuple[list[Item], dict[uuid.UUID, list[ItemOption]]]:
    items = (await db.execute(select(Item).where(Item.id.in_(item_ids)))).scalars().all()
    options = (await db.execute(select(ItemOption).where(ItemOption.item_id.in_(item_ids)))).scalars().all()
    options_by_item: dict[uuid.UUID, list[ItemOption]] = {i: [] for i in item_ids}
    for o in options:
        options_by_item[o.item_id].append(o)
    for item_id in options_by_item:
        options_by_item[item_id].sort(key=lambda o: o.position)
    return items, options_by_item


@router.post("/topics/{topic_id}/diagnostic/start")
async def start_diagnostic(
    topic_id: uuid.UUID, db: AsyncSession = Depends(get_db), student: User = Depends(require_role("student"))
) -> dict:
    topic = await _get_diagnosable_topic(db, topic_id, student)
    selected = await _draw_diagnostic_items(db, student, topic)
    item_ids = [i.id for i in selected]

    session = DiagnosticSession(id=uuid.uuid4(), user_id=student.id, topic_id=topic.id, item_ids=item_ids)
    db.add(session)
    await db.flush()

    _, options_by_item = await _items_with_options(db, item_ids)
    await record_event(db, user_id=student.id, event_type="diagnostic_started", topic_id=topic.id, payload={"diagnostic_id": str(session.id)})
    await db.commit()

    items_by_id = {i.id: i for i in selected}
    return {
        "diagnostic_id": str(session.id),
        "topic_id": str(topic.id),
        "items": [
            {"id": str(item_id), "stem": items_by_id[item_id].stem, "options": [_safe_option_out(o) for o in options_by_item[item_id]]}
            for item_id in item_ids
        ],
    }


class AnswerRequest(BaseModel):
    item_id: uuid.UUID
    option_id: uuid.UUID


@router.post("/diagnostic/{diagnostic_id}/answer")
async def answer_diagnostic(
    diagnostic_id: uuid.UUID, body: AnswerRequest, db: AsyncSession = Depends(get_db),
    student: User = Depends(require_role("student")),
) -> dict:
    session = (
        await db.execute(select(DiagnosticSession).where(DiagnosticSession.id == diagnostic_id, DiagnosticSession.user_id == student.id))
    ).scalar_one_or_none()
    if session is None:
        raise _not_found()
    if session.completed_at is not None:
        raise _bad_request("This diagnostic is already complete")
    if body.item_id not in session.item_ids:
        raise _bad_request("That item is not part of this diagnostic")

    already_answered = (
        await db.execute(
            select(Attempt.id).where(Attempt.container_id == session.id, Attempt.item_id == body.item_id, Attempt.context == "diagnostic")
        )
    ).scalar_one_or_none()
    if already_answered is not None:
        raise _bad_request("This item was already answered")

    option = (
        await db.execute(select(ItemOption).where(ItemOption.id == body.option_id, ItemOption.item_id == body.item_id))
    ).scalar_one_or_none()
    if option is None:
        raise _bad_request("option_id does not belong to item_id")
    item = (await db.execute(select(Item).where(Item.id == body.item_id))).scalar_one()

    db.add(Attempt(
        id=uuid.uuid4(), user_id=student.id, item_id=item.id, option_id=option.id,
        is_correct=option.is_correct, context="diagnostic", container_id=session.id,
    ))
    await mastery_module.update_mastery(db, user_id=student.id, topic_id=item.topic_id, correct=option.is_correct, context="diagnostic")
    await record_event(
        db, user_id=student.id, event_type="diagnostic_answer_submitted", topic_id=item.topic_id,
        payload={"diagnostic_id": str(session.id), "item_id": str(item.id), "is_correct": option.is_correct},
    )

    answered_count = (
        await db.execute(
            select(func.count(Attempt.id)).where(Attempt.container_id == session.id, Attempt.context == "diagnostic")
        )
    ).scalar_one()
    completed = answered_count >= len(session.item_ids)
    if completed:
        correct_count = (
            await db.execute(
                select(func.count(Attempt.id)).where(Attempt.container_id == session.id, Attempt.context == "diagnostic", Attempt.is_correct.is_(True))
            )
        ).scalar_one()
        session.score = correct_count
        session.completed_at = datetime.now(timezone.utc)
        await record_event(db, user_id=student.id, event_type="diagnostic_completed", topic_id=session.topic_id, payload={"diagnostic_id": str(session.id), "score": correct_count})

    await db.commit()
    return {"ack": "recorded", "completed": completed}


@router.get("/diagnostic/{diagnostic_id}")
async def get_diagnostic_review(
    diagnostic_id: uuid.UUID, db: AsyncSession = Depends(get_db), student: User = Depends(require_role("student"))
) -> dict:
    session = (
        await db.execute(select(DiagnosticSession).where(DiagnosticSession.id == diagnostic_id, DiagnosticSession.user_id == student.id))
    ).scalar_one_or_none()
    if session is None:
        raise _not_found()
    if session.completed_at is None:
        raise _bad_request("This diagnostic is not complete yet")

    items, options_by_item = await _items_with_options(db, session.item_ids)
    items_by_id = {i.id: i for i in items}
    attempts = (
        await db.execute(select(Attempt).where(Attempt.container_id == session.id, Attempt.context == "diagnostic"))
    ).scalars().all()
    attempt_by_item = {a.item_id: a for a in attempts}

    topics_touched = {i.topic_id for i in items}
    mastery_rows = []
    for topic_id in topics_touched:
        topic = (await db.execute(select(Topic).where(Topic.id == topic_id))).scalar_one()
        row = await mastery_module.get_mastery(db, user_id=student.id, topic_id=topic_id)
        mastery_rows.append({"topic_id": str(topic_id), "topic_title": topic.title, "p_known": row.p_known if row else None})

    review = []
    for item_id in session.item_ids:
        item = items_by_id[item_id]
        attempt = attempt_by_item.get(item_id)
        options = options_by_item[item_id]
        correct_option = next((o for o in options if o.is_correct), None)
        review.append({
            "item_id": str(item.id),
            "stem": item.stem,
            "options": [{"id": str(o.id), "body": o.body, "is_correct": o.is_correct} for o in options],
            "chosen_option_id": str(attempt.option_id) if attempt else None,
            "correct_option_id": str(correct_option.id) if correct_option else None,
            "is_correct": attempt.is_correct if attempt else None,
            "explanation": item.explanation,
        })

    return {
        "diagnostic_id": str(session.id),
        "topic_id": str(session.topic_id),
        "score": session.score,
        "total": len(session.item_ids),
        "review": review,
        "mastery": mastery_rows,
    }
