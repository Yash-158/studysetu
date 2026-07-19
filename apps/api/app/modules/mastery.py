"""modules/mastery: BKT mastery per (student, topic) + confidence decay (FEATURE_EXPLANATION S4).
Config via app.core.config.settings ONLY (database.yaml bkt/decay blocks). RULES.md #9: this
module never imports app.ai - deterministic math only, no LLM ever assigns mastery.

update_mastery() does not commit - callers (modules/learning.py) commit once, atomically with the
attempt row and diagnostic-session state it was computed alongside."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import Mastery, MasteryHistory, User, get_db, record_event
from app.core.security import require_role

router = APIRouter(prefix="/api/mastery", tags=["mastery"])


def _bkt_params() -> tuple[float, float, float, float]:
    p_init = settings.get("database", "bkt", "p_init", default=0.3)
    p_learn = settings.get("database", "bkt", "p_learn", default=0.15)
    p_guess = settings.get("database", "bkt", "p_guess", default=0.2)
    p_slip = settings.get("database", "bkt", "p_slip", default=0.1)
    return p_init, p_learn, p_guess, p_slip


def bkt_update(p_known: float, correct: bool) -> float:
    """Standard 2-state BKT posterior update, then the learning-transition step."""
    _, p_learn, p_guess, p_slip = _bkt_params()
    if correct:
        numerator = p_known * (1 - p_slip)
        denominator = numerator + (1 - p_known) * p_guess
    else:
        numerator = p_known * p_slip
        denominator = numerator + (1 - p_known) * (1 - p_guess)
    posterior = (numerator / denominator) if denominator > 0 else p_known
    updated = posterior + (1 - posterior) * p_learn
    return min(1.0, max(0.0, updated))


def _decayed_confidence(confidence: float, last_activity_at: datetime | None, now: datetime) -> float:
    if last_activity_at is None:
        return confidence
    halflife_days = settings.get("database", "decay", "confidence_halflife_days", default=42)
    elapsed_days = max(0.0, (now - last_activity_at).total_seconds() / 86400)
    return confidence * (0.5 ** (elapsed_days / halflife_days))


async def get_mastery(db: AsyncSession, *, user_id: uuid.UUID, topic_id: uuid.UUID) -> Mastery | None:
    return (
        await db.execute(select(Mastery).where(Mastery.user_id == user_id, Mastery.topic_id == topic_id))
    ).scalar_one_or_none()


async def is_weak(db: AsyncSession, *, user_id: uuid.UUID, topic_id: uuid.UUID) -> bool:
    """'Historically weak' (FEATURE_EXPLANATION S3/S4): a mastery row must already exist (real
    history, not an untouched topic defaulting to p_init) and its decayed p_known must sit below
    the mastery threshold."""
    row = await get_mastery(db, user_id=user_id, topic_id=topic_id)
    if row is None:
        return False
    threshold = settings.get("database", "bkt", "mastery_threshold", default=0.5)
    return row.p_known < threshold


async def update_mastery(db: AsyncSession, *, user_id: uuid.UUID, topic_id: uuid.UUID, correct: bool, context: str) -> Mastery:
    now = datetime.now(timezone.utc)
    p_init, *_ = _bkt_params()
    row = await get_mastery(db, user_id=user_id, topic_id=topic_id)
    if row is None:
        row = Mastery(user_id=user_id, topic_id=topic_id, p_known=p_init, confidence=1.0, attempts_count=0, last_activity_at=None)
        db.add(row)

    before = row.p_known
    row.p_known = bkt_update(row.p_known, correct)
    # A fresh attempt is fresh evidence - confidence resets on new activity, then decays again
    # with the next stretch of inactivity (S4: "stops being nagged after one clean refresher").
    row.confidence = 1.0
    row.attempts_count += 1
    row.last_activity_at = now
    row.updated_at = now
    await db.flush()

    db.add(MasteryHistory(id=uuid.uuid4(), user_id=user_id, topic_id=topic_id, p_known=row.p_known, recorded_at=now))
    await record_event(
        db, user_id=user_id, event_type="mastery_changed", topic_id=topic_id,
        payload={"from": before, "to": row.p_known, "context": context},
    )
    return row


def _mastery_out(row: Mastery, now: datetime) -> dict:
    return {
        "topic_id": str(row.topic_id),
        "p_known": row.p_known,
        "confidence": _decayed_confidence(row.confidence, row.last_activity_at, now),
        "attempts_count": row.attempts_count,
        "last_activity_at": row.last_activity_at.isoformat() if row.last_activity_at else None,
    }


@router.get("/topics/{topic_id}")
async def get_my_mastery(
    topic_id: uuid.UUID, db: AsyncSession = Depends(get_db), student: User = Depends(require_role("student"))
) -> dict:
    row = await get_mastery(db, user_id=student.id, topic_id=topic_id)
    p_init, *_ = _bkt_params()
    if row is None:
        return {"topic_id": str(topic_id), "p_known": p_init, "confidence": 1.0, "attempts_count": 0, "last_activity_at": None}
    return _mastery_out(row, datetime.now(timezone.utc))
