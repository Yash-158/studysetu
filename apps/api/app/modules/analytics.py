"""modules/analytics: teacher's command center (FEATURE_EXPLANATION S7/S8, docs/ROADMAP.md M6).
Owns its router, service functions, repository queries. Config via app.core.config.settings ONLY
(config/analytics.yaml's stuck_alert_minutes + misconception_cluster_threshold).

Three altitudes per S7/S8's "drill-down on demand, decisions on top": Today (needs-attention strip
- stuck/misconception-clusters/ungraded, each with one action), Explorer (subject -> chapter ->
topic -> student drill-down + a student x topic heat grid), per-student detail (mastery + the same
event ledger modules/timeline.py renders for students themselves, symmetrical per S7/S8 + F13 -
this module does not duplicate that ledger's write path, only reads it for the teacher).

Teacher access-scoping matches modules/curriculum.py: every subject-scoped route is gated by a
subject_staff row for the CALLER; missing access 404s rather than leaking existence.

Enrollment-archive respected everywhere an aggregate is computed (RULES.md #10 privacy spirit,
this milestone's own Verify line): every cluster/heat/completion query joins subject_enrollments
and filters status='active, so an archived student's history stops counting toward class signals
the moment they're removed - same "archive not delete" model as S10, their attempts/mastery rows
are untouched and still readable from the per-student detail route directly.

"ungraded" (PROMPTS.md M6 line) is read as the pre-existing item-bank review queue (Item.status==
'draft') - M6's own Avoid list excludes assignments/submissions, which don't exist as a module yet,
so there is no other "needs grading" queue this milestone can reuse. "stuck" is read literally
against analytics.yaml's stuck_alert_minutes: a diagnostic or session a student opened but hasn't
finished within that many minutes - real-time and testable, unlike an invented mastery-decline
heuristic with no backing config knob.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import (
    Attempt,
    Chapter,
    ChapterBlock,
    DiagnosticSession,
    Event,
    GeneratedArtifact,
    Item,
    ItemOption,
    LearningSession,
    Mastery,
    Misconception,
    Subject,
    SubjectEnrollment,
    SubjectStaff,
    Topic,
    User,
    get_db,
    record_event,
)
from app.core.security import require_role

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "not_found", "message": "Not found", "hint": "Check the id"})


# --- ownership / scoping helpers -----------------------------------------------------------

async def _owned_subject_ids(db: AsyncSession, teacher: User) -> list[uuid.UUID]:
    return (await db.execute(select(SubjectStaff.subject_id).where(SubjectStaff.user_id == teacher.id))).scalars().all()


async def _get_owned_subject(db: AsyncSession, subject_id: uuid.UUID, teacher: User) -> Subject:
    subject = (
        await db.execute(
            select(Subject)
            .join(SubjectStaff, SubjectStaff.subject_id == Subject.id)
            .where(Subject.id == subject_id, SubjectStaff.user_id == teacher.id)
        )
    ).scalar_one_or_none()
    if subject is None:
        raise _not_found()
    return subject


async def _get_owned_topic(db: AsyncSession, topic_id: uuid.UUID, teacher: User) -> tuple[Topic, Subject]:
    topic = (await db.execute(select(Topic).where(Topic.id == topic_id))).scalar_one_or_none()
    if topic is None or topic.subject_id is None:
        raise _not_found()
    subject = await _get_owned_subject(db, topic.subject_id, teacher)
    return topic, subject


async def _active_enrollment_count(db: AsyncSession, subject_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(SubjectEnrollment).where(
                SubjectEnrollment.subject_id == subject_id, SubjectEnrollment.status == "active"
            )
        )
    ).scalar_one()


async def _active_enrolled_users(db: AsyncSession, subject_id: uuid.UUID) -> list[User]:
    return (
        await db.execute(
            select(User)
            .join(SubjectEnrollment, SubjectEnrollment.user_id == User.id)
            .where(SubjectEnrollment.subject_id == subject_id, SubjectEnrollment.status == "active")
        )
    ).scalars().all()


# --- misconception clustering (GROUP BY, RULES #9: deterministic, no LLM involved) ----------

async def _misconception_rows(
    db: AsyncSession, *, subject_ids: list[uuid.UUID] | None = None, topic_id: uuid.UUID | None = None
) -> list:
    stmt = (
        select(
            Misconception.id.label("misconception_id"),
            Misconception.code.label("code"),
            Misconception.title.label("title"),
            Topic.id.label("topic_id"),
            Topic.title.label("topic_title"),
            Subject.id.label("subject_id"),
            Subject.name.label("subject_name"),
            func.count(func.distinct(Attempt.user_id)).label("student_count"),
            func.array_agg(func.distinct(Attempt.user_id)).label("student_ids"),
        )
        .select_from(Attempt)
        .join(ItemOption, ItemOption.id == Attempt.option_id)
        .join(Item, Item.id == Attempt.item_id)
        .join(Topic, Topic.id == Item.topic_id)
        .join(Subject, Subject.id == Topic.subject_id)
        .join(Misconception, Misconception.id == ItemOption.misconception_id)
        .join(
            SubjectEnrollment,
            (SubjectEnrollment.user_id == Attempt.user_id) & (SubjectEnrollment.subject_id == Subject.id),
        )
        .where(Attempt.is_correct.is_(False), SubjectEnrollment.status == "active")
        .group_by(Misconception.id, Topic.id, Subject.id)
        .order_by(func.count(func.distinct(Attempt.user_id)).desc())
    )
    if subject_ids is not None:
        stmt = stmt.where(Topic.subject_id.in_(subject_ids))
    if topic_id is not None:
        stmt = stmt.where(Topic.id == topic_id)
    return (await db.execute(stmt)).all()


async def _clusters_out(db: AsyncSession, rows: list) -> list[dict]:
    all_user_ids = {uid for row in rows for uid in row.student_ids}
    names_by_id: dict[uuid.UUID, str] = {}
    if all_user_ids:
        users = (await db.execute(select(User).where(User.id.in_(all_user_ids)))).scalars().all()
        names_by_id = {u.id: u.display_name for u in users}
    return [
        {
            "misconception_id": str(row.misconception_id),
            "misconception_code": row.code,
            "misconception_title": row.title,
            "topic_id": str(row.topic_id),
            "topic_title": row.topic_title,
            "subject_id": str(row.subject_id),
            "subject_title": row.subject_name,
            "student_count": row.student_count,
            "students": [{"id": str(uid), "display_name": names_by_id.get(uid, "")} for uid in row.student_ids],
        }
        for row in rows
    ]


# --- Today ------------------------------------------------------------------------------------

async def _stuck_signals(db: AsyncSession, subject_ids: list[uuid.UUID]) -> list[dict]:
    if not subject_ids:
        return []
    stuck_minutes = settings.get("analytics", "stuck_alert_minutes", default=5)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=stuck_minutes)

    session_rows = (
        await db.execute(
            select(LearningSession, User, Topic, Subject)
            .join(User, User.id == LearningSession.user_id)
            .join(Topic, Topic.id == LearningSession.topic_id)
            .join(Subject, Subject.id == Topic.subject_id)
            .join(
                SubjectEnrollment,
                (SubjectEnrollment.user_id == User.id) & (SubjectEnrollment.subject_id == Subject.id),
            )
            .where(
                Topic.subject_id.in_(subject_ids),
                LearningSession.status == "in_progress",
                LearningSession.started_at < cutoff,
                SubjectEnrollment.status == "active",
            )
        )
    ).all()
    diagnostic_rows = (
        await db.execute(
            select(DiagnosticSession, User, Topic, Subject)
            .join(User, User.id == DiagnosticSession.user_id)
            .join(Topic, Topic.id == DiagnosticSession.topic_id)
            .join(Subject, Subject.id == Topic.subject_id)
            .join(
                SubjectEnrollment,
                (SubjectEnrollment.user_id == User.id) & (SubjectEnrollment.subject_id == Subject.id),
            )
            .where(
                Topic.subject_id.in_(subject_ids),
                DiagnosticSession.completed_at.is_(None),
                DiagnosticSession.created_at < cutoff,
                SubjectEnrollment.status == "active",
            )
        )
    ).all()

    now = datetime.now(timezone.utc)
    out: list[dict] = []
    for session, student, topic, subject in session_rows:
        out.append({
            "kind": "session", "student_id": str(student.id), "student_name": student.display_name,
            "topic_id": str(topic.id), "topic_title": topic.title, "subject_id": str(subject.id),
            "subject_title": subject.name, "stalled_minutes": int((now - session.started_at).total_seconds() // 60),
        })
    for diagnostic, student, topic, subject in diagnostic_rows:
        out.append({
            "kind": "diagnostic", "student_id": str(student.id), "student_name": student.display_name,
            "topic_id": str(topic.id), "topic_title": topic.title, "subject_id": str(subject.id),
            "subject_title": subject.name, "stalled_minutes": int((now - diagnostic.created_at).total_seconds() // 60),
        })
    out.sort(key=lambda r: r["stalled_minutes"], reverse=True)
    return out


async def _ungraded_signals(db: AsyncSession, subject_ids: list[uuid.UUID]) -> list[dict]:
    if not subject_ids:
        return []
    rows = (
        await db.execute(
            select(Topic.id, Topic.title, Subject.id, Subject.name, func.count(Item.id))
            .select_from(Item)
            .join(Topic, Topic.id == Item.topic_id)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(Topic.subject_id.in_(subject_ids), Item.status == "draft", Item.deleted_at.is_(None))
            .group_by(Topic.id, Subject.id)
            .order_by(func.count(Item.id).desc())
        )
    ).all()
    return [
        {"topic_id": str(topic_id), "topic_title": topic_title, "subject_id": str(subject_id), "subject_title": subject_name, "draft_count": count}
        for topic_id, topic_title, subject_id, subject_name, count in rows
    ]


@router.get("/today")
async def get_today(db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))) -> dict:
    subject_ids = await _owned_subject_ids(db, teacher)
    threshold = settings.get("analytics", "misconception_cluster_threshold", default=5)
    rows = await _misconception_rows(db, subject_ids=subject_ids)
    rows = [r for r in rows if r.student_count >= threshold]
    return {
        "stuck": await _stuck_signals(db, subject_ids),
        "clusters": await _clusters_out(db, rows),
        "ungraded": await _ungraded_signals(db, subject_ids),
    }


# --- Explorer drill-down ------------------------------------------------------------------------

@router.get("/explorer/subjects")
async def list_explorer_subjects(db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))) -> list[dict]:
    subject_ids = await _owned_subject_ids(db, teacher)
    if not subject_ids:
        return []
    subjects = (await db.execute(select(Subject).where(Subject.id.in_(subject_ids)))).scalars().all()
    out = []
    for subject in subjects:
        student_count = await _active_enrollment_count(db, subject.id)
        avg_mastery = (
            await db.execute(
                select(func.avg(Mastery.p_known))
                .select_from(Mastery)
                .join(Topic, Topic.id == Mastery.topic_id)
                .join(SubjectEnrollment, (SubjectEnrollment.user_id == Mastery.user_id) & (SubjectEnrollment.subject_id == Topic.subject_id))
                .where(Topic.subject_id == subject.id, SubjectEnrollment.status == "active")
            )
        ).scalar_one()
        out.append({
            "id": str(subject.id), "name": subject.name, "code": subject.code, "status": subject.status,
            "student_count": student_count, "avg_mastery": avg_mastery,
        })
    return out


@router.get("/explorer/subjects/{subject_id}")
async def get_explorer_subject(
    subject_id: uuid.UUID, db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))
) -> dict:
    subject = await _get_owned_subject(db, subject_id, teacher)
    student_count = await _active_enrollment_count(db, subject.id)

    chapters = (
        await db.execute(select(Chapter).where(Chapter.subject_id == subject.id, Chapter.deleted_at.is_(None)).order_by(Chapter.position))
    ).scalars().all()
    blocks = (
        await db.execute(
            select(ChapterBlock)
            .where(ChapterBlock.chapter_id.in_([c.id for c in chapters]), ChapterBlock.block_type == "topic")
            .order_by(ChapterBlock.position)
        )
    ).scalars().all() if chapters else []
    topic_ids = [b.topic_id for b in blocks if b.topic_id]
    topics_by_id = {}
    if topic_ids:
        rows = (await db.execute(select(Topic).where(Topic.id.in_(topic_ids)))).scalars().all()
        topics_by_id = {t.id: t for t in rows}

    misconception_rows = await _misconception_rows(db, subject_ids=[subject.id])
    top_misconceptions_by_topic: dict[uuid.UUID, list[dict]] = {}
    for row in misconception_rows:
        top_misconceptions_by_topic.setdefault(row.topic_id, []).append(
            {"misconception_id": str(row.misconception_id), "misconception_title": row.title, "student_count": row.student_count}
        )
    for topic_id in top_misconceptions_by_topic:
        top_misconceptions_by_topic[topic_id] = top_misconceptions_by_topic[topic_id][:3]

    chapter_out = []
    for chapter in chapters:
        chapter_topics = []
        for block in blocks:
            if block.chapter_id != chapter.id or block.topic_id is None:
                continue
            topic = topics_by_id.get(block.topic_id)
            if topic is None:
                continue
            avg_mastery = (
                await db.execute(
                    select(func.avg(Mastery.p_known))
                    .select_from(Mastery)
                    .join(SubjectEnrollment, (SubjectEnrollment.user_id == Mastery.user_id) & (SubjectEnrollment.subject_id == subject.id))
                    .where(Mastery.topic_id == topic.id, SubjectEnrollment.status == "active")
                )
            ).scalar_one()
            attempted_count = (
                await db.execute(
                    select(func.count(func.distinct(Mastery.user_id)))
                    .select_from(Mastery)
                    .join(SubjectEnrollment, (SubjectEnrollment.user_id == Mastery.user_id) & (SubjectEnrollment.subject_id == subject.id))
                    .where(Mastery.topic_id == topic.id, SubjectEnrollment.status == "active", Mastery.attempts_count > 0)
                )
            ).scalar_one()
            chapter_topics.append({
                "id": str(topic.id), "title": topic.title, "avg_mastery": avg_mastery,
                "completion_pct": (attempted_count / student_count) if student_count else None,
                "top_misconceptions": top_misconceptions_by_topic.get(topic.id, []),
            })
        chapter_out.append({"id": str(chapter.id), "title": chapter.title, "position": chapter.position, "topics": chapter_topics})

    return {"id": str(subject.id), "name": subject.name, "student_count": student_count, "chapters": chapter_out}


@router.get("/explorer/subjects/{subject_id}/heat")
async def get_explorer_heat(
    subject_id: uuid.UUID, db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))
) -> dict:
    subject = await _get_owned_subject(db, subject_id, teacher)
    students = await _active_enrolled_users(db, subject.id)
    topics = (
        await db.execute(select(Topic).where(Topic.subject_id == subject.id, Topic.kind == "subject", Topic.deleted_at.is_(None)))
    ).scalars().all()
    student_ids = [s.id for s in students]
    topic_ids = [t.id for t in topics]
    cells: list[dict] = []
    if student_ids and topic_ids:
        rows = (
            await db.execute(
                select(Mastery).where(Mastery.user_id.in_(student_ids), Mastery.topic_id.in_(topic_ids))
            )
        ).scalars().all()
        cells = [{"student_id": str(r.user_id), "topic_id": str(r.topic_id), "p_known": r.p_known} for r in rows]
    return {
        "students": [{"id": str(s.id), "display_name": s.display_name} for s in students],
        "topics": [{"id": str(t.id), "title": t.title} for t in topics],
        "cells": cells,
    }


@router.get("/explorer/topics/{topic_id}/students")
async def get_explorer_topic_students(
    topic_id: uuid.UUID, db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))
) -> list[dict]:
    topic, subject = await _get_owned_topic(db, topic_id, teacher)
    students = await _active_enrolled_users(db, subject.id)
    student_ids = [s.id for s in students]
    mastery_by_user = {}
    if student_ids:
        rows = (
            await db.execute(select(Mastery).where(Mastery.topic_id == topic.id, Mastery.user_id.in_(student_ids)))
        ).scalars().all()
        mastery_by_user = {m.user_id: m for m in rows}
    out = []
    for student in students:
        m = mastery_by_user.get(student.id)
        out.append({
            "student_id": str(student.id), "display_name": student.display_name,
            "p_known": m.p_known if m else None, "attempts_count": m.attempts_count if m else 0,
            "last_activity_at": m.last_activity_at.isoformat() if m and m.last_activity_at else None,
        })
    return out


# --- Per-student detail (F13/F14: symmetrical timeline, AI-artifact visibility + flag) ----------

@router.get("/students/{student_id}")
async def get_student_detail(
    student_id: uuid.UUID, subject_id: uuid.UUID, misconception_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher")),
) -> dict:
    subject = await _get_owned_subject(db, subject_id, teacher)
    enrollment = (
        await db.execute(
            select(SubjectEnrollment).where(SubjectEnrollment.subject_id == subject.id, SubjectEnrollment.user_id == student_id)
        )
    ).scalar_one_or_none()
    if enrollment is None:
        raise _not_found()
    student = (await db.execute(select(User).where(User.id == student_id))).scalar_one_or_none()
    if student is None:
        raise _not_found()

    topics = (
        await db.execute(select(Topic).where(Topic.subject_id == subject.id, Topic.kind == "subject", Topic.deleted_at.is_(None)))
    ).scalars().all()
    topic_ids = [t.id for t in topics]
    topics_by_id = {t.id: t.title for t in topics}

    mastery_rows = (
        await db.execute(select(Mastery).where(Mastery.user_id == student.id, Mastery.topic_id.in_(topic_ids)))
    ).scalars().all() if topic_ids else []

    events = (
        await db.execute(
            select(Event).where(Event.user_id == student.id).order_by(Event.occurred_at.desc(), Event.ingest_id.desc())
        )
    ).scalars().all()

    wrong_rows = []
    if topic_ids:
        wrong_stmt = (
            select(Attempt, Item, ItemOption, Misconception)
            .join(Item, Item.id == Attempt.item_id)
            .join(ItemOption, ItemOption.id == Attempt.option_id)
            .outerjoin(Misconception, Misconception.id == ItemOption.misconception_id)
            .where(Attempt.user_id == student.id, Attempt.is_correct.is_(False), Item.topic_id.in_(topic_ids))
            .order_by(Attempt.occurred_at.desc())
        )
        if misconception_id is not None:
            wrong_stmt = wrong_stmt.where(ItemOption.misconception_id == misconception_id)
        wrong_rows = (await db.execute(wrong_stmt)).all()

    artifacts = (
        await db.execute(
            select(GeneratedArtifact).where(GeneratedArtifact.topic_id.in_(topic_ids)).order_by(GeneratedArtifact.created_at.desc())
        )
    ).scalars().all() if topic_ids else []

    return {
        "student": {"id": str(student.id), "display_name": student.display_name, "roll_number": student.roll_number, "enrollment_status": enrollment.status},
        "mastery": [
            {"topic_id": str(m.topic_id), "topic_title": topics_by_id.get(m.topic_id), "p_known": m.p_known, "attempts_count": m.attempts_count}
            for m in mastery_rows
        ],
        "timeline": [
            {
                "id": str(e.id), "event_type": e.event_type, "topic_id": str(e.topic_id) if e.topic_id else None,
                "topic_title": topics_by_id.get(e.topic_id), "payload": e.payload, "occurred_at": e.occurred_at.isoformat(),
            }
            for e in events
        ],
        "wrong_attempts": [
            {
                "attempt_id": str(attempt.id), "item_stem": item.stem, "chosen_option_body": option.body,
                "misconception_title": misconception.title if misconception else None,
                "topic_id": str(item.topic_id), "topic_title": topics_by_id.get(item.topic_id),
                "occurred_at": attempt.occurred_at.isoformat(),
            }
            for attempt, item, option, misconception in wrong_rows
        ],
        "artifacts": [
            {
                "id": str(a.id), "artifact_type": a.artifact_type, "topic_id": str(a.topic_id) if a.topic_id else None,
                "topic_title": topics_by_id.get(a.topic_id), "model": a.model, "created_at": a.created_at.isoformat(),
                "flagged": a.flagged, "hidden": a.hidden,
            }
            for a in artifacts
        ],
    }


@router.post("/artifacts/{artifact_id}/flag")
async def flag_artifact(
    artifact_id: uuid.UUID, db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))
) -> dict:
    artifact = (await db.execute(select(GeneratedArtifact).where(GeneratedArtifact.id == artifact_id))).scalar_one_or_none()
    if artifact is None or artifact.topic_id is None:
        raise _not_found()
    _, subject = await _get_owned_topic(db, artifact.topic_id, teacher)
    artifact.flagged = True
    await record_event(
        db, user_id=teacher.id, event_type="artifact_flagged", subject_id=subject.id, topic_id=artifact.topic_id,
        payload={"artifact_id": str(artifact.id), "artifact_type": artifact.artifact_type},
    )
    await db.commit()
    return {"id": str(artifact.id), "flagged": artifact.flagged}
