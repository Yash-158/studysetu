"""modules/assessment: per-topic AI item bank generation + teacher review queue (FEATURE_EXPLANATION
S3/S13, ROADMAP M4). Owns its router, service functions, repository queries. Config via
app.core.config.settings ONLY. Emits a timeline event for every user-visible action.

Teacher access-scoping matches modules/curriculum.py: a topic route is gated by a subject_staff
row for the CALLER; missing access 404s rather than leaking existence.

Bank generation is idempotent at the items level (RULES.md #4 lookup-before-generate; S13
"regeneration is always an explicit teacher action, never an implicit side effect"): the AI facade
is always called (so ai_invocations logs truthfully on every request, proving the cache), but item
rows are only inserted the first time a topic has none - a second call for the same topic is a
pure generated_artifacts cache hit with zero duplicate items.

RULES.md #5: only review_status='approved' items are ever exposed to a student-facing route -
this module never has a student route; modules/learning.py's diagnostic draw is the sole student
consumer and filters on status='approved' there.
"""
from __future__ import annotations

import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai
from app.ai.gateway import GatewayError
from app.core.config import settings
from app.core.db import Item, ItemOption, Material, Misconception, Subject, SubjectStaff, Topic, User, get_db, record_event
from app.core.security import require_role

router = APIRouter(prefix="/api/assessment", tags=["assessment"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "not_found", "message": "Not found", "hint": "Check the id"})


def _ai_unavailable() -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={"code": "ai_unavailable", "message": "Generation is temporarily unavailable", "hint": "Please try again shortly"},
    )


async def _get_owned_topic(db: AsyncSession, topic_id: uuid.UUID, teacher: User) -> tuple[Topic, Subject]:
    topic = (await db.execute(select(Topic).where(Topic.id == topic_id))).scalar_one_or_none()
    if topic is None or topic.subject_id is None:
        raise _not_found()
    subject = (
        await db.execute(
            select(Subject)
            .join(SubjectStaff, SubjectStaff.subject_id == Subject.id)
            .where(Subject.id == topic.subject_id, SubjectStaff.user_id == teacher.id)
        )
    ).scalar_one_or_none()
    if subject is None:
        raise _not_found()
    return topic, subject


def _option_out(option: ItemOption, misconceptions_by_id: dict[uuid.UUID, Misconception]) -> dict:
    m = misconceptions_by_id.get(option.misconception_id) if option.misconception_id else None
    return {
        "id": str(option.id), "position": option.position, "body": option.body, "is_correct": option.is_correct,
        "misconception": {"code": m.code, "title": m.title} if m else None,
    }


def _item_out(item: Item, options: list[ItemOption], misconceptions_by_id: dict[uuid.UUID, Misconception]) -> dict:
    return {
        "id": str(item.id), "topic_id": str(item.topic_id), "status": item.status, "stem": item.stem,
        "difficulty": item.difficulty, "explanation": item.explanation,
        "options": [_option_out(o, misconceptions_by_id) for o in sorted(options, key=lambda o: o.position)],
    }


async def _bank_with_options(db: AsyncSession, topic_id: uuid.UUID) -> list[dict]:
    items = (
        await db.execute(select(Item).where(Item.topic_id == topic_id, Item.deleted_at.is_(None)).order_by(Item.created_at))
    ).scalars().all()
    if not items:
        return []
    item_ids = [i.id for i in items]
    options = (await db.execute(select(ItemOption).where(ItemOption.item_id.in_(item_ids)))).scalars().all()
    misconception_ids = {o.misconception_id for o in options if o.misconception_id}
    misconceptions_by_id = {}
    if misconception_ids:
        rows = (await db.execute(select(Misconception).where(Misconception.id.in_(misconception_ids)))).scalars().all()
        misconceptions_by_id = {m.id: m for m in rows}
    options_by_item: dict[uuid.UUID, list[ItemOption]] = {i.id: [] for i in items}
    for o in options:
        options_by_item[o.item_id].append(o)
    return [_item_out(i, options_by_item[i.id], misconceptions_by_id) for i in items]


def _validate_bank_shape(parsed: dict) -> None:
    items = parsed.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("response missing a non-empty 'items' list")
    for item in items:
        if not isinstance(item.get("stem"), str) or not item["stem"].strip():
            raise ValueError("item missing 'stem'")
        if item.get("difficulty") not in (-1, 0, 1):
            raise ValueError("item 'difficulty' must be -1, 0, or 1")
        options = item.get("options")
        if not isinstance(options, list) or len(options) != 4:
            raise ValueError("item must have exactly 4 options")
        correct = [o for o in options if o.get("is_correct")]
        if len(correct) != 1:
            raise ValueError("item must have exactly one is_correct option")
        for o in options:
            if not o.get("is_correct") and not (o.get("misconception_code") and o.get("misconception_title")):
                raise ValueError("every incorrect option needs misconception_code + misconception_title")
        if not isinstance(item.get("explanation"), str) or not item["explanation"].strip():
            raise ValueError("item missing 'explanation'")


async def _get_or_create_misconception(db: AsyncSession, code: str, title: str, cache: dict[str, Misconception]) -> Misconception:
    if code in cache:
        return cache[code]
    existing = (await db.execute(select(Misconception).where(Misconception.code == code))).scalar_one_or_none()
    if existing is None:
        existing = Misconception(id=uuid.uuid4(), code=code, title=title)
        db.add(existing)
        await db.flush()
    cache[code] = existing
    return existing


@router.post("/topics/{topic_id}/bank/generate")
async def generate_bank(
    topic_id: uuid.UUID, db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))
) -> dict:
    topic, subject = await _get_owned_topic(db, topic_id, teacher)

    existing_items = (
        await db.execute(select(Item.id).where(Item.topic_id == topic.id, Item.deleted_at.is_(None)))
    ).scalars().all()

    # Grounding text (S2/S13): only readable material, topic- or subject-level (chapter-level
    # grounding is a real cut, not required by the M4 GATE - a topic's owning chapter isn't a
    # single well-defined lookup without walking chapter_blocks, and subject+topic material
    # already covers the seeded/GATE scenarios).
    materials = (
        await db.execute(
            select(Material).where(
                Material.readability == "readable",
                ((Material.owner_type == "topic") & (Material.owner_id == topic.id))
                | ((Material.owner_type == "subject") & (Material.owner_id == subject.id)),
            )
        )
    ).scalars().all()
    material_text = "\n\n".join((m.extracted_text or "") for m in materials)[:6000]
    source_hash = hashlib.sha256(f"{topic.title}|{topic.description}|{material_text}".encode()).hexdigest()

    min_items = settings.get("ai", "item_bank", "min_items", default=12)
    max_items = settings.get("ai", "item_bank", "max_items", default=15)

    def render_user_prompt() -> str:
        return json.dumps({
            "topic_title": topic.title, "topic_description": topic.description,
            "material_text": material_text, "min_items": min_items, "max_items": max_items,
        })

    try:
        result = await ai.generate(
            "item_bank", db=db, scope="topic_shared", artifact_type="item_bank", topic_id=topic.id,
            params={"min_items": min_items, "max_items": max_items}, source_hash=source_hash,
            render_user_prompt=render_user_prompt, validate=_validate_bank_shape,
        )
    except GatewayError as exc:
        # Every provider attempt already logged an ai_invocations row inside ai.generate() - commit
        # those (don't discard the failover audit trail) even though the overall call failed.
        await db.commit()
        raise _ai_unavailable() from exc

    generated = False
    if not existing_items:
        generated = True
        misconception_cache: dict[str, Misconception] = {}
        for item_payload in result.content["items"]:
            item = Item(
                id=uuid.uuid4(), topic_id=topic.id, origin="ai", status="draft",
                stem=item_payload["stem"], difficulty=item_payload["difficulty"],
                explanation=item_payload["explanation"],
            )
            db.add(item)
            await db.flush()
            for position, option_payload in enumerate(item_payload["options"]):
                misconception_id = None
                if not option_payload.get("is_correct"):
                    m = await _get_or_create_misconception(
                        db, option_payload["misconception_code"], option_payload["misconception_title"], misconception_cache
                    )
                    misconception_id = m.id
                db.add(ItemOption(
                    id=uuid.uuid4(), item_id=item.id, position=position, body=option_payload["body"],
                    is_correct=bool(option_payload.get("is_correct")), misconception_id=misconception_id,
                ))

    await record_event(
        db, user_id=teacher.id, event_type="bank_generated", subject_id=subject.id, topic_id=topic.id,
        payload={"generated": generated, "cache_hit": result.cache_hit},
    )
    await db.commit()
    return {"generated": generated, "cache_hit": result.cache_hit, "items": await _bank_with_options(db, topic.id)}


@router.get("/topics/{topic_id}/bank")
async def get_bank(
    topic_id: uuid.UUID, db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))
) -> list[dict]:
    await _get_owned_topic(db, topic_id, teacher)
    return await _bank_with_options(db, topic_id)


@router.post("/items/{item_id}/approve")
async def approve_item(
    item_id: uuid.UUID, db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))
) -> dict:
    item = (await db.execute(select(Item).where(Item.id == item_id, Item.deleted_at.is_(None)))).scalar_one_or_none()
    if item is None:
        raise _not_found()
    _, subject = await _get_owned_topic(db, item.topic_id, teacher)
    item.status = "approved"
    await record_event(db, user_id=teacher.id, event_type="item_approved", subject_id=subject.id, topic_id=item.topic_id, payload={"item_id": str(item.id)})
    await db.commit()
    return {"id": str(item.id), "status": item.status}


@router.post("/topics/{topic_id}/bank/approve-all")
async def approve_all(
    topic_id: uuid.UUID, db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))
) -> dict:
    topic, subject = await _get_owned_topic(db, topic_id, teacher)
    draft_items = (
        await db.execute(select(Item).where(Item.topic_id == topic.id, Item.status == "draft", Item.deleted_at.is_(None)))
    ).scalars().all()
    for item in draft_items:
        item.status = "approved"
    await record_event(
        db, user_id=teacher.id, event_type="bank_approved", subject_id=subject.id, topic_id=topic.id,
        payload={"approved": len(draft_items)},
    )
    await db.commit()
    return {"approved": len(draft_items)}
