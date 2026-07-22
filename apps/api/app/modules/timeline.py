"""modules/timeline: the event-sourced student timeline (FEATURE_EXPLANATION F13, S7/S8) -
literally `SELECT * FROM events WHERE user_id=? ORDER BY occurred_at`, rendered (DATABASE.md's own
description of the timeline screen). Owns its router, service functions, repository queries.
Config via app.core.config.settings ONLY (no tunable knobs needed yet).

Student-only in M5 (this milestone's Avoid list excludes teacher analytics) - the symmetrical
teacher-facing per-student timeline view (F13: "symmetrical for teacher and student") is
explicitly M6 (Explorer drill-down) scope, not built here."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Event, Subject, Topic, User, get_db
from app.core.security import require_role

router = APIRouter(prefix="/api/timeline", tags=["timeline"])


@router.get("/me")
async def get_my_timeline(
    db: AsyncSession = Depends(get_db), student: User = Depends(require_role("student"))
) -> dict:
    # occurred_at DESC alone is not a reliable causal-chain order: Postgres holds now() stable for
    # an entire transaction, so several events emitted in one request (e.g. session_started plus
    # multiple revision_injected rows) can share an identical timestamp - ingest_id DESC is the
    # necessary tiebreaker for true emission order (see core/db.py's Event docstring).
    events = (
        await db.execute(
            select(Event).where(Event.user_id == student.id).order_by(Event.occurred_at.desc(), Event.ingest_id.desc())
        )
    ).scalars().all()

    topic_ids = {e.topic_id for e in events if e.topic_id}
    subject_ids = {e.subject_id for e in events if e.subject_id}
    topics_by_id: dict = {}
    if topic_ids:
        rows = (await db.execute(select(Topic).where(Topic.id.in_(topic_ids)))).scalars().all()
        topics_by_id = {t.id: t.title for t in rows}
    subjects_by_id: dict = {}
    if subject_ids:
        rows = (await db.execute(select(Subject).where(Subject.id.in_(subject_ids)))).scalars().all()
        subjects_by_id = {s.id: s.name for s in rows}

    return {
        "events": [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "topic_id": str(e.topic_id) if e.topic_id else None,
                "topic_title": topics_by_id.get(e.topic_id),
                "subject_id": str(e.subject_id) if e.subject_id else None,
                "subject_title": subjects_by_id.get(e.subject_id),
                "payload": e.payload,
                "occurred_at": e.occurred_at.isoformat(),
            }
            for e in events
        ]
    }
