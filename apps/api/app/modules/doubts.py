"""modules/doubts: M6-remediation Phase 5 - topic-scoped doubt chat, a genuine minimal slice of
FEATURE_EXPLANATION F11, not the full M8 doubt/RAG feature. The student is already looking at a
specific topic (via an active LearningSession, M5), so there is no embedding-based topic-matching
or prereq/root-gap walk here - the topic is known deterministically from the session, the answer is
grounded in that topic's own already-generated lesson content (session.plan's 'explanation'/
'worked_example' cards), and every ask is a single question-answer pair (mode='direct', resolved
immediately) - no Socratic multi-turn dialogue. M8 extends the same `doubts` table this writes to
with embedding-based matching, a root-gap walk, and streaming Socratic mode; it does not replace it.

Owns its router, service functions, repository queries (module contract, see module docstring
convention elsewhere). Config via app.core.config.settings ONLY. Emits a timeline event for every
user-visible action (RULES.md #3)."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai
from app.ai.gateway import GatewayError
from app.core.db import Doubt, LearningSession, Topic, User, get_db, record_event
from app.core.security import require_role

router = APIRouter(prefix="/api/doubts", tags=["doubts"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "not_found", "message": "Not found", "hint": "Check the id"})


def _bad_request(message: str, hint: str = "") -> HTTPException:
    return HTTPException(status_code=400, detail={"code": "bad_request", "message": message, "hint": hint})


def _ai_unavailable() -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={"code": "ai_unavailable", "message": "Generation is temporarily unavailable", "hint": "Please try again shortly"},
    )


def _segment_grounding_text(session: LearningSession) -> str:
    """The exact lesson content the student is already looking at (the session's own 'explanation'
    and 'worked_example' cards, S16 recipe) - no separate fetch/generate needed, it's already sitting
    in the row this endpoint loads anyway. Capped defensively, matching modules/learning.py's own
    [:6000] material-text convention, though prompts/segment.md's own word limits keep this well
    under that in practice."""
    parts: list[str] = []
    for card in session.plan.get("cards", []):
        if card.get("type") == "explanation":
            for section in card.get("sections", []):
                parts.append(f"{section.get('heading', '')}: {section.get('body', '')}")
        elif card.get("type") == "worked_example":
            parts.extend(card.get("steps", []))
    return "\n".join(parts)[:6000]


def _validate_doubt_answer(parsed: dict) -> None:
    if not isinstance(parsed.get("answer"), str) or not parsed["answer"].strip():
        raise ValueError("doubt_quick response missing non-empty 'answer'")


class AskRequest(BaseModel):
    question: str


@router.post("/sessions/{session_id}/ask")
async def ask_doubt(
    session_id: uuid.UUID, body: AskRequest, db: AsyncSession = Depends(get_db),
    student: User = Depends(require_role("student")),
) -> dict:
    question = body.question.strip()
    if not question:
        raise _bad_request("Question cannot be empty")

    session = (
        await db.execute(select(LearningSession).where(LearningSession.id == session_id, LearningSession.user_id == student.id))
    ).scalar_one_or_none()
    if session is None:
        raise _not_found()
    topic = (await db.execute(select(Topic).where(Topic.id == session.topic_id))).scalar_one()

    grounding_text = _segment_grounding_text(session)
    source_hash = hashlib.sha256(grounding_text.encode()).hexdigest()

    def render_user_prompt() -> str:
        return json.dumps({
            "topic_title": topic.title,
            "topic_description": topic.description,
            "lesson_content": grounding_text,
            "question": question,
        })

    try:
        result = await ai.generate(
            "doubt_quick", db=db, scope="student_unique", artifact_type="doubt_reply",
            topic_id=topic.id, user_id=student.id, params={"question": question}, source_hash=source_hash,
            render_user_prompt=render_user_prompt, validate=_validate_doubt_answer,
        )
    except GatewayError as exc:
        await db.commit()  # every attempt already logged an ai_invocations row - keep that trail
        raise _ai_unavailable() from exc

    answer = result.content["answer"]
    now = datetime.now(timezone.utc)
    doubt = Doubt(
        id=uuid.uuid4(), user_id=student.id, subject_id=topic.subject_id, matched_topic_id=topic.id,
        raw_text=question, mode="direct", status="resolved",
        transcript=[{"role": "student", "text": question}, {"role": "ai", "text": answer}],
        resolved_at=now,
    )
    db.add(doubt)
    await db.flush()

    await record_event(
        db, user_id=student.id, event_type="doubt_asked", topic_id=topic.id,
        payload={"doubt_id": str(doubt.id), "session_id": str(session.id)},
    )
    await db.commit()

    return {"doubt_id": str(doubt.id), "answer": answer}
