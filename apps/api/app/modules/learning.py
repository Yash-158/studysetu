"""modules/learning: the diagnostic engine (FEATURE_EXPLANATION S3, ROADMAP M4) - stratified 5-item
draw + weak-prereq slot, neutral-ack probe, end-of-probe review with stored reasoning - PLUS
(M5, FEATURE_EXPLANATION F8/F9/S4/S16) the session planner + player: walks direct prerequisite
edges for historically-weak topics, injects revision segments, assembles the S16 card recipe from
cached segment_shared/topic_shared artifacts (generate-once via ai.generate("segment", ...),
prompts/segment.md), and serves practice with INSTANT reasoning (unlike the diagnostic's neutral
ack - S3's deferred-feedback rule is a diagnostic-only property).

RULES.md #9: all draw/selection is deterministic (random.choice over an already-approved pool) -
no LLM ever picks or grades. RULES.md #5: every draw pool is filtered to status='approved' only.

Two deliberate, tracked scope cuts (see docs/MEMORY.md for the full write-up, not just this
comment - both are real reductions from FEATURE_EXPLANATION, not implementation shortcuts):
(1) segment content is NOT tiered by probe performance level ("struggling" vs "solid" copy per
S4/S16) - one fixed "core" segment per topic and one fixed "revision" segment per weak prereq,
regardless of how the student scored. (2) the prereq walk is ONE HOP only (direct topic_edges),
not a recursive ancestor walk - matches the diagnostic's own existing weak-prereq slot exactly,
sufficient for DIP's current graph depth (Transforms -> Frequency Filtering, one edge)."""
from __future__ import annotations

import hashlib
import json
import random
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai
from app.ai.gateway import GatewayError
from app.core.config import settings
from app.core.db import (
    Attempt,
    Chapter,
    ChapterBlock,
    DiagnosticSession,
    Item,
    ItemOption,
    LearningSession,
    Material,
    Misconception,
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


def _ai_unavailable() -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={"code": "ai_unavailable", "message": "Generation is temporarily unavailable", "hint": "Please try again shortly"},
    )


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


# ---------------------------------------------------------------------------
# M5: session planner + player (FEATURE_EXPLANATION F8/F9, S4, S16)
# ---------------------------------------------------------------------------

async def _grounding_material_text(db: AsyncSession, topic: Topic) -> str:
    """Same grounding source + cap as modules/assessment.py's bank generation - topic- or
    subject-level readable material only."""
    materials = (
        await db.execute(
            select(Material).where(
                Material.readability == "readable",
                ((Material.owner_type == "topic") & (Material.owner_id == topic.id))
                | ((Material.owner_type == "subject") & (Material.owner_id == topic.subject_id)),
            )
        )
    ).scalars().all()
    return "\n\n".join((m.extracted_text or "") for m in materials)[:6000]


# "core" section headings must read naturally (prompts/segment.md's own instruction) - this is a
# mechanical backstop, not a substitute for the prompt: a heading that's (after stripping leading
# numbering/punctuation) exactly one of these generic process labels triggers the gateway's
# same-provider parse retry, same as any other malformed-shape failure.
_CORE_FORBIDDEN_HEADINGS = {
    "definition", "definitions", "example", "examples", "explanation", "plain explanation",
    "plain language explanation", "plain-language explanation", "layman explanation",
    "layman's explanation", "technical explanation", "worked example", "worked examples",
}


def _normalize_heading(heading: str) -> str:
    return re.sub(r"^[\d.\-:)\s]+", "", heading.strip().lower()).rstrip(":").strip()


def _validate_segment_shape(kind: str):
    def _validate(parsed: dict) -> None:
        if kind == "core":
            sections = parsed.get("sections")
            if not isinstance(sections, list) or not (3 <= len(sections) <= 5):
                raise ValueError("core segment needs 3-5 'sections'")
            for section in sections:
                if not isinstance(section, dict):
                    raise ValueError("each core section must be an object")
                heading, body = section.get("heading"), section.get("body")
                if not isinstance(heading, str) or not heading.strip():
                    raise ValueError("each core section needs a non-empty 'heading'")
                if not isinstance(body, str) or not body.strip():
                    raise ValueError("each core section needs a non-empty 'body'")
                if _normalize_heading(heading) in _CORE_FORBIDDEN_HEADINGS:
                    raise ValueError(f"core section heading reads like a process label, not a natural heading: {heading!r}")
            we = parsed.get("worked_example")
            if not isinstance(we, dict) or not isinstance(we.get("steps"), list) or not we["steps"]:
                raise ValueError("core segment missing 'worked_example.steps'")
        elif kind == "revision":
            if not isinstance(parsed.get("explanation"), str) or not parsed["explanation"].strip():
                raise ValueError("revision segment missing 'explanation'")
        elif kind in ("contrast", "cheatsheet"):
            if not isinstance(parsed.get("text"), str) or not parsed["text"].strip():
                raise ValueError(f"{kind} segment missing 'text'")
        elif kind == "summary":
            bullets = parsed.get("bullets")
            if not isinstance(bullets, list) or not bullets:
                raise ValueError("summary segment missing 'bullets'")
        else:
            raise ValueError(f"unknown segment kind '{kind}'")
    return _validate


async def _generate_segment(
    db: AsyncSession, topic: Topic, kind: str, *, scope: str, artifact_type: str, misconception: dict | None = None
) -> dict:
    """generate-once-serve-forever (RULES #4/#13, S13 tier-1/tier-2): cache_key is a function of
    (topic_id, artifact_type, params={kind[, misconception_code]}, source_hash, prompt_version) -
    two students hitting the identical (topic, kind[, misconception]) combo are a real cache hit,
    not a coincidence - this is exactly what the M5 GATE's second-weak-student clause proves."""
    material_text = await _grounding_material_text(db, topic)
    source_hash = hashlib.sha256(f"{topic.title}|{topic.description}|{material_text}".encode()).hexdigest()
    params: dict = {"kind": kind}
    if misconception is not None:
        params["misconception_code"] = misconception["code"]

    def render_user_prompt() -> str:
        payload = {"topic_title": topic.title, "topic_description": topic.description, "material_text": material_text, "kind": kind}
        if misconception is not None:
            payload["misconception_title"] = misconception["title"]
        return json.dumps(payload)

    try:
        result = await ai.generate(
            "segment", db=db, scope=scope, artifact_type=artifact_type, topic_id=topic.id,
            params=params, source_hash=source_hash, render_user_prompt=render_user_prompt,
            validate=_validate_segment_shape(kind),
        )
    except GatewayError as exc:
        await db.commit()  # every attempt already logged an ai_invocations row - keep that trail
        raise _ai_unavailable() from exc
    return result.content


async def _weak_prereqs(db: AsyncSession, student: User, topic_id: uuid.UUID) -> list[Topic]:
    """One-hop prereq walk (see module docstring: a tracked scope cut, not a bug) - reuses the
    exact 'historically weak' definition as the diagnostic's own weak-prereq slot."""
    prereq_ids = (await db.execute(select(TopicEdge.src_topic_id).where(TopicEdge.dst_topic_id == topic_id))).scalars().all()
    weak: list[Topic] = []
    for prereq_id in prereq_ids:
        if await mastery_module.is_weak(db, user_id=student.id, topic_id=prereq_id):
            topic = (await db.execute(select(Topic).where(Topic.id == prereq_id))).scalar_one_or_none()
            if topic is not None:
                weak.append(topic)
    return weak


def _bridge_text(diagnostic: DiagnosticSession, weak_prereqs: list[Topic]) -> str:
    """Deterministic template, not an LLM call - S13 explicitly allows the per-student composition
    layer to be 'a thin layer... or zero'; a whole cache tier for one templated sentence is
    overhead a session-opening line doesn't need."""
    total = len(diagnostic.item_ids)
    score = diagnostic.score if diagnostic.score is not None else total
    if weak_prereqs:
        names = " and ".join(t.title for t in weak_prereqs)
        return f"You scored {score}/{total} on the probe. Before we go on, a quick refresher on {names} - you found this tricky before."
    return f"You scored {score}/{total} on the probe. Let's build on what you already know."


async def _find_fired_misconception(db: AsyncSession, diagnostic: DiagnosticSession) -> dict | None:
    """The first (in item-draw order) wrong diagnostic answer's tagged misconception - "the
    misconception YOUR probe answers revealed" (S16 contrast card). None if the probe was clean."""
    attempts = (
        await db.execute(
            select(Attempt).where(Attempt.container_id == diagnostic.id, Attempt.context == "diagnostic", Attempt.is_correct.is_(False))
        )
    ).scalars().all()
    if not attempts:
        return None
    order = {item_id: i for i, item_id in enumerate(diagnostic.item_ids)}
    for attempt in sorted(attempts, key=lambda a: order.get(a.item_id, 0)):
        if attempt.option_id is None:
            continue
        option = (await db.execute(select(ItemOption).where(ItemOption.id == attempt.option_id))).scalar_one_or_none()
        if option and option.misconception_id:
            misconception = (await db.execute(select(Misconception).where(Misconception.id == option.misconception_id))).scalar_one_or_none()
            if misconception:
                return {"code": misconception.code, "title": misconception.title}
    return None


async def _safe_options_for(db: AsyncSession, item_id: uuid.UUID) -> list[dict]:
    options = (await db.execute(select(ItemOption).where(ItemOption.item_id == item_id))).scalars().all()
    return [_safe_option_out(o) for o in sorted(options, key=lambda o: o.position)]


async def _practice_card(db: AsyncSession, item: Item) -> dict:
    return {
        "type": "practice", "item_id": str(item.id), "topic_id": str(item.topic_id),
        "stem": item.stem, "options": await _safe_options_for(db, item.id),
    }


async def _draw_practice_items(db: AsyncSession, topic_id: uuid.UUID, exclude_ids: set[uuid.UUID]) -> list[Item]:
    cfg = settings.get("database", "session_recipe", default={})
    counts = {-1: cfg.get("practice_easy", 1), 0: cfg.get("practice_medium", 1), 1: cfg.get("practice_hard", 1)}
    approved = await _approved_items_by_topic(db, topic_id)
    fresh = [i for i in approved if i.id not in exclude_ids]

    by_difficulty: dict[int, list[Item]] = {-1: [], 0: [], 1: []}
    for item in fresh:
        by_difficulty.setdefault(item.difficulty, []).append(item)
    selected: list[Item] = []
    for difficulty, count in counts.items():
        pool = by_difficulty.get(difficulty, [])
        random.shuffle(pool)
        selected.extend(pool[:count])

    total_needed = sum(counts.values())
    # ponytail: graceful degradation, matching the diagnostic draw's own precedent - a thin bank
    # (or one the diagnostic already drew most of) backfills from whatever's left, including
    # diagnostic-reused items, rather than blocking the session outright.
    if len(selected) < total_needed:
        backfill = [i for i in approved if i not in selected]
        random.shuffle(backfill)
        selected.extend(backfill[: total_needed - len(selected)])
    random.shuffle(selected)
    return selected


async def _build_plan(db: AsyncSession, student: User, topic: Topic, diagnostic: DiagnosticSession) -> tuple[list[dict], list[dict]]:
    """Assembles the S16 card recipe. Returns (cards, injected_prereqs) - the latter drives one
    revision_injected timeline event per injected prereq, emitted by the caller after the plan (and
    thus the artifact rows it references) are safely stored."""
    weak_prereqs = await _weak_prereqs(db, student, topic.id)
    cards: list[dict] = [{"type": "bridge", "text": _bridge_text(diagnostic, weak_prereqs)}]
    injected: list[dict] = []

    revision_count = settings.get("database", "session_recipe", "revision_items", default=2)
    for prereq in weak_prereqs:
        prereq_bank = await _approved_items_by_topic(db, prereq.id)
        if not prereq_bank:
            continue  # nothing to revise with yet - skip gracefully rather than 500
        content = await _generate_segment(db, prereq, "revision", scope="segment_shared", artifact_type="segment")
        random.shuffle(prereq_bank)
        practice_items = []
        for item in prereq_bank[:revision_count]:
            practice_items.append({
                "item_id": str(item.id), "topic_id": str(item.topic_id),
                "stem": item.stem, "options": await _safe_options_for(db, item.id),
            })
        cards.append({
            "type": "revision", "topic_id": str(prereq.id), "topic_title": prereq.title,
            "explanation": content["explanation"], "practice_items": practice_items,
        })
        injected.append({"topic_id": prereq.id, "topic_title": prereq.title})

    core_content = await _generate_segment(db, topic, "core", scope="segment_shared", artifact_type="segment")
    cards.append({"type": "explanation", "topic_id": str(topic.id), "sections": core_content["sections"]})
    cards.append({"type": "worked_example", "steps": core_content["worked_example"]["steps"]})

    practice_items = await _draw_practice_items(db, topic.id, set(diagnostic.item_ids))
    if not practice_items:
        raise _bad_request("Not enough approved items in this topic's bank yet for practice", "Ask your teacher to approve more items")

    easy_first = [i for i in practice_items if i.difficulty == -1][:1] or practice_items[:1]
    rest = [i for i in practice_items if i not in easy_first]
    cards.append(await _practice_card(db, easy_first[0]))

    misconception = await _find_fired_misconception(db, diagnostic)
    if misconception is not None:
        contrast_content = await _generate_segment(
            db, topic, "contrast", scope="segment_shared", artifact_type="segment", misconception=misconception
        )
        cards.append({"type": "contrast", "misconception_title": misconception["title"], "text": contrast_content["text"]})

    for item in rest:
        cards.append(await _practice_card(db, item))

    summary_content = await _generate_segment(db, topic, "summary", scope="topic_shared", artifact_type="summary")
    cards.append({"type": "summary", "bullets": summary_content["bullets"]})

    cheatsheet_content = await _generate_segment(db, topic, "cheatsheet", scope="topic_shared", artifact_type="cheatsheet")
    cards.append({"type": "cheatsheet", "text": cheatsheet_content["text"]})

    return cards, injected


async def _session_out(db: AsyncSession, session: LearningSession) -> dict:
    """resume_index: derived from attempts, never a separately-tracked cursor (same
    derive-don't-track style as the diagnostic's own completed-count check). A session with ZERO
    attempts so far always opens at card 0 (bridge -> lesson -> worked example, in full, before any
    practice) - only once at least one practice/revision item has been answered does resume_index
    become "the first practice/revision card with an unanswered item, or just past the LAST
    practice-bearing card if every practice item is already answered" (so trailing read-only cards
    like summary/cheatsheet still show on resume, rather than being skipped past).
    ponytail: non-practice "seen" state isn't tracked at all - re-showing a bridge/explanation/
    summary card on resume is harmless (it's stored/cached, free, no data loss); only practice
    progress (real graded state) must never be lost or re-asked, and that IS tracked, via attempts."""
    cards = session.plan.get("cards", [])
    practice_card_indices = [i for i, c in enumerate(cards) if c["type"] in ("practice", "revision")]

    answered_item_ids: set[uuid.UUID] = set()
    if practice_card_indices:
        answered_item_ids = set(
            (
                await db.execute(
                    select(Attempt.item_id).where(Attempt.container_id == session.id, Attempt.context.in_(["practice", "revision"]))
                )
            ).scalars().all()
        )

    # A genuinely fresh session (nothing answered yet) must always open at card 0 - the bridge,
    # then the real lesson content (explanation/worked_example), THEN the first practice/revision
    # card. Without this guard, the loop below finds the first practice-bearing card with an
    # unanswered item, which is ALWAYS true on a brand-new session (nothing is answered), so it
    # silently skipped straight past the bridge/explanation/worked_example on every student's very
    # first view whenever no revision was injected - the real root cause behind "the session only
    # ever shows a cheat sheet" (found live while verifying Phase 4's new lesson content, not
    # something Phase 4 introduced - this bug predates it, back to M5's original session player).
    resume_index = 0
    if answered_item_ids:
        resume_index = (practice_card_indices[-1] + 1) if practice_card_indices else 0
        for i in practice_card_indices:
            card = cards[i]
            if card["type"] == "practice":
                if uuid.UUID(card["item_id"]) not in answered_item_ids:
                    resume_index = i
                    break
            else:
                unanswered = [p for p in card.get("practice_items", []) if uuid.UUID(p["item_id"]) not in answered_item_ids]
                if unanswered:
                    resume_index = i
                    break

    return {
        "session_id": str(session.id), "topic_id": str(session.topic_id), "status": session.status,
        "cards": cards, "resume_index": min(resume_index, len(cards) - 1) if cards else 0,
    }


@router.post("/topics/{topic_id}/session/start")
async def start_session(
    topic_id: uuid.UUID, db: AsyncSession = Depends(get_db), student: User = Depends(require_role("student"))
) -> dict:
    topic = await _get_diagnosable_topic(db, topic_id, student)

    diagnostic = (
        await db.execute(
            select(DiagnosticSession)
            .where(
                DiagnosticSession.user_id == student.id, DiagnosticSession.topic_id == topic.id,
                DiagnosticSession.completed_at.isnot(None),
            )
            .order_by(DiagnosticSession.completed_at.desc())
        )
    ).scalars().first()
    if diagnostic is None:
        raise _bad_request("Complete the diagnostic before starting a session", "Take the 5-question probe first")

    # Lookup-before-generate at the session level too (RULES #4's spirit; also the GATE's
    # plan-is-stable-across-reloads clause): an existing session for this exact diagnostic is
    # returned as-is, never re-planned or reshuffled.
    existing = (
        await db.execute(
            select(LearningSession).where(LearningSession.diagnostic_id == diagnostic.id, LearningSession.user_id == student.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return await _session_out(db, existing)

    cards, injected = await _build_plan(db, student, topic, diagnostic)
    now = datetime.now(timezone.utc)
    session = LearningSession(
        id=uuid.uuid4(), user_id=student.id, topic_id=topic.id, diagnostic_id=diagnostic.id,
        plan={"cards": cards}, status="in_progress", started_at=now,
    )
    db.add(session)
    await db.flush()

    await record_event(db, user_id=student.id, event_type="session_started", topic_id=topic.id, payload={"session_id": str(session.id)})
    for prereq in injected:
        await record_event(
            db, user_id=student.id, event_type="revision_injected", topic_id=prereq["topic_id"],
            payload={"session_id": str(session.id), "reason": "prereq", "for_topic_id": str(topic.id)},
        )
    await db.commit()
    return await _session_out(db, session)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db), student: User = Depends(require_role("student"))
) -> dict:
    session = (
        await db.execute(select(LearningSession).where(LearningSession.id == session_id, LearningSession.user_id == student.id))
    ).scalar_one_or_none()
    if session is None:
        raise _not_found()
    return await _session_out(db, session)


class PracticeAnswerRequest(BaseModel):
    item_id: uuid.UUID
    option_id: uuid.UUID


@router.post("/sessions/{session_id}/practice/answer")
async def answer_practice(
    session_id: uuid.UUID, body: PracticeAnswerRequest, db: AsyncSession = Depends(get_db),
    student: User = Depends(require_role("student")),
) -> dict:
    """Practice feedback is INSTANT (S3: the deferred-ack rule is diagnostic-only) - correctness +
    stored reasoning return immediately, unlike modules/learning.py's diagnostic answer endpoint."""
    session = (
        await db.execute(select(LearningSession).where(LearningSession.id == session_id, LearningSession.user_id == student.id))
    ).scalar_one_or_none()
    if session is None:
        raise _not_found()
    if session.status == "completed":
        raise _bad_request("This session is already complete")

    already_answered = (
        await db.execute(
            select(Attempt.id).where(
                Attempt.container_id == session.id, Attempt.item_id == body.item_id, Attempt.context.in_(["practice", "revision"])
            )
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

    context = "revision" if item.topic_id != session.topic_id else "practice"
    db.add(Attempt(
        id=uuid.uuid4(), user_id=student.id, item_id=item.id, option_id=option.id,
        is_correct=option.is_correct, context=context, container_id=session.id,
    ))
    await mastery_module.update_mastery(db, user_id=student.id, topic_id=item.topic_id, correct=option.is_correct, context=context)

    correct_option = (
        await db.execute(select(ItemOption).where(ItemOption.item_id == item.id, ItemOption.is_correct.is_(True)))
    ).scalar_one_or_none()
    await record_event(
        db, user_id=student.id, event_type="practice_answer_submitted", topic_id=item.topic_id,
        payload={"session_id": str(session.id), "item_id": str(item.id), "is_correct": option.is_correct, "context": context},
    )
    await db.commit()

    return {
        "is_correct": option.is_correct,
        "correct_option_id": str(correct_option.id) if correct_option else None,
        "explanation": item.explanation,
    }


@router.post("/sessions/{session_id}/complete")
async def complete_session(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db), student: User = Depends(require_role("student"))
) -> dict:
    session = (
        await db.execute(select(LearningSession).where(LearningSession.id == session_id, LearningSession.user_id == student.id))
    ).scalar_one_or_none()
    if session is None:
        raise _not_found()
    if session.status != "completed":
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)
        session.updated_at = session.completed_at
        await record_event(db, user_id=student.id, event_type="session_completed", topic_id=session.topic_id, payload={"session_id": str(session.id)})
    await db.commit()
    return {"session_id": str(session.id), "status": session.status}
