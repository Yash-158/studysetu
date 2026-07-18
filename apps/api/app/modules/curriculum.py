"""modules/curriculum: scope in docs/FEATURE_EXPLANATION.md S2/S4/S10 + docs/ROADMAP.md M3.
Owns its router, service functions, repository queries. Config via app.core.config.settings ONLY.
Emits a timeline event for every user-visible action (RULES: events over state).

Teacher access-scoping: every subject/chapter/topic/block/edge/material route is gated by a
subject_staff row for the CALLER (never by client-supplied subject id trust); missing access 404s
rather than leaking existence (same convention as modules/pools.py).
Student access-scoping: student read routes require an active subject_enrollments row AND the
subject/chapter/assessment actually being published - drafts are invisible, not merely disabled.

Publish model (FEATURE_EXPLANATION S2): chapters are the ONLY publish lever - there is no separate
subject-level publish action. Publishing a chapter cascades: (a) the subject flips draft->published
on its first published chapter (a subject with zero published chapters is entirely invisible to
students; there is nothing to gate independently above chapter granularity), (b) any assessment
placeholder blocks inside that chapter flip draft->published too, since M3 assessments are
title-only shells with no separate review step (that arrives in M7).

Enrollment (S10, snapshot+delta): attaching a pool COPIES its current membership into
subject_enrollments; later pool edits never auto-propagate. The "new pool members" banner
(GET .../pool-deltas) is computed by diffing live pool_members against subject_enrollments rows
that trace back to that pool (any status - archived counts as "already handled", so a teacher's
deliberate removal is never silently resurrected by a sync); the sync action is the only thing
that ever adds the delta.

Readability (S2 materials): readability is a pure function of whether extracted_text ended up
populated, regardless of why. note: teacher-typed, always readable if non-empty (no scan-detection
heuristic applies to typed text - reusing extracted_text as its body is documented and safe, see
DATABASE.md). pdf: extraction attempted; below storage.materials.min_extractable_chars characters
is treated as a scanned/unreadable page -> stored_only. link/image: no local text -> stored_only.
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger
from pydantic import BaseModel
from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import (
    Assessment,
    Chapter,
    ChapterBlock,
    Material,
    Pool,
    PoolMember,
    Subject,
    SubjectEnrollment,
    SubjectStaff,
    Topic,
    TopicEdge,
    Upload,
    User,
    get_db,
    record_event,
)
from app.core.security import require_role
from app.storage.local import LocalStorageProvider

router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])

_MATERIAL_KINDS = {"pdf", "note", "link", "image"}
_OWNER_TYPES = {"subject", "chapter", "topic"}

_storage = LocalStorageProvider()


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "not_found", "message": "Not found", "hint": "Check the id"})


def _bad_request(message: str, hint: str = "") -> HTTPException:
    return HTTPException(status_code=400, detail={"code": "bad_request", "message": message, "hint": hint})


# --- ownership / access helpers -------------------------------------------------------------

async def _get_owned_subject(db: AsyncSession, subject_id: uuid.UUID, user: User) -> Subject:
    subject = (
        await db.execute(
            select(Subject)
            .join(SubjectStaff, SubjectStaff.subject_id == Subject.id)
            .where(Subject.id == subject_id, SubjectStaff.user_id == user.id)
        )
    ).scalar_one_or_none()
    if subject is None:
        raise _not_found()
    return subject


async def _get_owned_chapter(db: AsyncSession, chapter_id: uuid.UUID, user: User) -> tuple[Chapter, Subject]:
    chapter = (await db.execute(select(Chapter).where(Chapter.id == chapter_id))).scalar_one_or_none()
    if chapter is None:
        raise _not_found()
    subject = await _get_owned_subject(db, chapter.subject_id, user)
    return chapter, subject


async def _get_owned_topic(db: AsyncSession, topic_id: uuid.UUID, user: User) -> tuple[Topic, Subject]:
    topic = (await db.execute(select(Topic).where(Topic.id == topic_id))).scalar_one_or_none()
    if topic is None or topic.subject_id is None:
        raise _not_found()
    subject = await _get_owned_subject(db, topic.subject_id, user)
    return topic, subject


async def _subject_id_for_owner(db: AsyncSession, owner_type: str, owner_id: uuid.UUID) -> uuid.UUID | None:
    if owner_type == "subject":
        return (await db.execute(select(Subject.id).where(Subject.id == owner_id))).scalar_one_or_none()
    if owner_type == "chapter":
        return (await db.execute(select(Chapter.subject_id).where(Chapter.id == owner_id))).scalar_one_or_none()
    if owner_type == "topic":
        return (await db.execute(select(Topic.subject_id).where(Topic.id == owner_id))).scalar_one_or_none()
    return None


async def _get_enrolled_subject(db: AsyncSession, subject_id: uuid.UUID, student: User) -> Subject:
    subject = (
        await db.execute(
            select(Subject)
            .join(SubjectEnrollment, SubjectEnrollment.subject_id == Subject.id)
            .where(
                Subject.id == subject_id,
                Subject.status == "published",
                SubjectEnrollment.user_id == student.id,
                SubjectEnrollment.status == "active",
            )
        )
    ).scalar_one_or_none()
    if subject is None:
        raise _not_found()
    return subject


# --- output shapers ---------------------------------------------------------------------------

def _subject_out(subject: Subject) -> dict:
    return {"id": str(subject.id), "name": subject.name, "code": subject.code, "term": subject.term, "status": subject.status}


def _chapter_out(chapter: Chapter) -> dict:
    return {"id": str(chapter.id), "title": chapter.title, "position": chapter.position, "status": chapter.status}


def _topic_out(topic: Topic) -> dict:
    return {"id": str(topic.id), "title": topic.title, "description": topic.description}


def _material_out(material: Material) -> dict:
    return {
        "id": str(material.id),
        "owner_type": material.owner_type,
        "owner_id": str(material.owner_id),
        "kind": material.kind,
        "title": material.title,
        "url": material.url,
        "readability": material.readability,
        "created_at": material.created_at.isoformat(),
    }


def _edge_out(edge: TopicEdge) -> dict:
    return {"src_topic_id": str(edge.src_topic_id), "dst_topic_id": str(edge.dst_topic_id), "origin": edge.origin}


# --- request models ----------------------------------------------------------------------------

class CreateSubjectRequest(BaseModel):
    name: str
    code: str | None = None
    term: str | None = None


class CreateChapterRequest(BaseModel):
    title: str


class ReorderRequest(BaseModel):
    ids: list[uuid.UUID]


class CreateTopicRequest(BaseModel):
    title: str
    description: str = ""


class AddBlockRequest(BaseModel):
    block_type: Literal["topic", "assessment"]
    topic_id: uuid.UUID | None = None
    assessment_title: str | None = None


class CreateEdgeRequest(BaseModel):
    dst_topic_id: uuid.UUID


# --- subjects ------------------------------------------------------------------------------------

@router.get("/subjects")
async def list_subjects(db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))) -> list[dict]:
    subjects = (
        await db.execute(
            select(Subject)
            .join(SubjectStaff, SubjectStaff.subject_id == Subject.id)
            .where(SubjectStaff.user_id == teacher.id)
            .order_by(Subject.created_at)
        )
    ).scalars().all()
    return [_subject_out(s) for s in subjects]


@router.post("/subjects")
async def create_subject(
    body: CreateSubjectRequest, db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))
) -> dict:
    subject = Subject(
        id=uuid.uuid4(), institution_id=teacher.institution_id, created_by=teacher.id,
        name=body.name, code=body.code, term=body.term, status="draft",
    )
    db.add(subject)
    await db.flush()
    db.add(SubjectStaff(subject_id=subject.id, user_id=teacher.id))
    await record_event(db, user_id=teacher.id, event_type="subject_created", subject_id=subject.id, payload={"name": subject.name})
    await db.commit()
    return _subject_out(subject)


@router.get("/subjects/{subject_id}")
async def get_subject(
    subject_id: uuid.UUID, db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))
) -> dict:
    subject = await _get_owned_subject(db, subject_id, teacher)

    chapters = (await db.execute(select(Chapter).where(Chapter.subject_id == subject.id).order_by(Chapter.position))).scalars().all()
    chapter_ids = [c.id for c in chapters]
    blocks = (
        await db.execute(
            select(ChapterBlock).where(ChapterBlock.chapter_id.in_(chapter_ids)).order_by(ChapterBlock.chapter_id, ChapterBlock.position)
        )
    ).scalars().all() if chapter_ids else []

    topics = (await db.execute(select(Topic).where(Topic.subject_id == subject.id).order_by(Topic.created_at))).scalars().all()
    topics_by_id = {t.id: t for t in topics}

    assessment_ids = [b.assessment_id for b in blocks if b.assessment_id]
    assessments = (
        await db.execute(select(Assessment).where(Assessment.id.in_(assessment_ids)))
    ).scalars().all() if assessment_ids else []
    assessments_by_id = {a.id: a for a in assessments}

    edges = (
        await db.execute(select(TopicEdge).join(Topic, Topic.id == TopicEdge.src_topic_id).where(Topic.subject_id == subject.id))
    ).scalars().all()

    materials = (
        await db.execute(
            select(Material).where(
                ((Material.owner_type == "subject") & (Material.owner_id == subject.id))
                | ((Material.owner_type == "chapter") & (Material.owner_id.in_(chapter_ids)))
                | ((Material.owner_type == "topic") & (Material.owner_id.in_(list(topics_by_id.keys()))))
            )
        )
    ).scalars().all()

    blocks_by_chapter: dict[uuid.UUID, list[dict]] = {c.id: [] for c in chapters}
    for b in blocks:
        entry = {"id": str(b.id), "position": b.position, "block_type": b.block_type}
        if b.block_type == "topic" and b.topic_id in topics_by_id:
            entry["topic"] = _topic_out(topics_by_id[b.topic_id])
        elif b.block_type == "assessment" and b.assessment_id in assessments_by_id:
            a = assessments_by_id[b.assessment_id]
            entry["assessment"] = {"id": str(a.id), "title": a.title, "status": a.status}
        blocks_by_chapter[b.chapter_id].append(entry)

    return {
        **_subject_out(subject),
        "chapters": [{**_chapter_out(c), "blocks": blocks_by_chapter[c.id]} for c in chapters],
        "topics": [_topic_out(t) for t in topics],
        "edges": [_edge_out(e) for e in edges],
        "materials": [_material_out(m) for m in materials],
    }


# --- chapters --------------------------------------------------------------------------------

@router.post("/subjects/{subject_id}/chapters")
async def create_chapter(
    subject_id: uuid.UUID, body: CreateChapterRequest, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_role("teacher")),
) -> dict:
    subject = await _get_owned_subject(db, subject_id, teacher)
    next_pos = (await db.execute(select(func.max(Chapter.position)).where(Chapter.subject_id == subject.id))).scalar()
    chapter = Chapter(id=uuid.uuid4(), subject_id=subject.id, title=body.title, position=(next_pos + 1) if next_pos is not None else 0, status="draft")
    db.add(chapter)
    await db.flush()
    await record_event(db, user_id=teacher.id, event_type="chapter_created", subject_id=subject.id, payload={"chapter_id": str(chapter.id), "title": chapter.title})
    await db.commit()
    return _chapter_out(chapter)


@router.put("/subjects/{subject_id}/chapters/reorder")
async def reorder_chapters(
    subject_id: uuid.UUID, body: ReorderRequest, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_role("teacher")),
) -> dict:
    subject = await _get_owned_subject(db, subject_id, teacher)
    chapters = (await db.execute(select(Chapter).where(Chapter.subject_id == subject.id))).scalars().all()
    chapters_by_id = {c.id: c for c in chapters}
    if set(body.ids) != set(chapters_by_id.keys()):
        raise _bad_request("Reorder must include exactly the subject's current chapters")

    for index, chapter_id in enumerate(body.ids):
        chapters_by_id[chapter_id].position = index
    # Positions are DEFERRABLE INITIALLY DEFERRED (db/migrations/0003) - the uniqueness check runs
    # at commit, not per-UPDATE, so this transient reassignment never trips a duplicate-position error.
    await record_event(db, user_id=teacher.id, event_type="chapters_reordered", subject_id=subject.id, payload={"order": [str(i) for i in body.ids]})
    await db.commit()
    return {"reordered": len(body.ids)}


@router.post("/chapters/{chapter_id}/publish")
async def publish_chapter(
    chapter_id: uuid.UUID, db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))
) -> dict:
    chapter, subject = await _get_owned_chapter(db, chapter_id, teacher)
    chapter.status = "published"
    if subject.status == "draft":
        subject.status = "published"

    assessment_ids = (
        await db.execute(select(ChapterBlock.assessment_id).where(ChapterBlock.chapter_id == chapter.id, ChapterBlock.block_type == "assessment"))
    ).scalars().all()
    if assessment_ids:
        assessments = (await db.execute(select(Assessment).where(Assessment.id.in_(assessment_ids)))).scalars().all()
        for a in assessments:
            a.status = "published"

    await record_event(db, user_id=teacher.id, event_type="chapter_published", subject_id=subject.id, payload={"chapter_id": str(chapter.id)})
    await db.commit()
    return {**_chapter_out(chapter), "subject_status": subject.status}


# --- topics ------------------------------------------------------------------------------------

@router.post("/subjects/{subject_id}/topics")
async def create_topic(
    subject_id: uuid.UUID, body: CreateTopicRequest, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_role("teacher")),
) -> dict:
    subject = await _get_owned_subject(db, subject_id, teacher)
    topic = Topic(id=uuid.uuid4(), kind="subject", subject_id=subject.id, title=body.title, description=body.description)
    db.add(topic)
    await db.flush()
    await record_event(db, user_id=teacher.id, event_type="topic_created", subject_id=subject.id, topic_id=topic.id, payload={"title": topic.title})
    await db.commit()
    return _topic_out(topic)


# --- chapter blocks (ordered flow) --------------------------------------------------------------

@router.post("/chapters/{chapter_id}/blocks")
async def add_block(
    chapter_id: uuid.UUID, body: AddBlockRequest, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_role("teacher")),
) -> dict:
    chapter, subject = await _get_owned_chapter(db, chapter_id, teacher)
    next_pos = (await db.execute(select(func.max(ChapterBlock.position)).where(ChapterBlock.chapter_id == chapter.id))).scalar()
    position = (next_pos + 1) if next_pos is not None else 0

    if body.block_type == "topic":
        if body.topic_id is None:
            raise _bad_request("topic_id is required for a topic block")
        topic = (await db.execute(select(Topic).where(Topic.id == body.topic_id, Topic.subject_id == subject.id))).scalar_one_or_none()
        if topic is None:
            raise _bad_request("topic_id must belong to this subject")
        block = ChapterBlock(id=uuid.uuid4(), chapter_id=chapter.id, position=position, block_type="topic", topic_id=topic.id)
    else:
        assessment = Assessment(
            id=uuid.uuid4(), subject_id=subject.id, created_by=teacher.id,
            title=body.assessment_title or "Assessment", gating="recommended", feedback="end", status="draft",
        )
        db.add(assessment)
        await db.flush()
        block = ChapterBlock(id=uuid.uuid4(), chapter_id=chapter.id, position=position, block_type="assessment", assessment_id=assessment.id)

    db.add(block)
    await db.flush()
    await record_event(db, user_id=teacher.id, event_type="block_added", subject_id=subject.id, payload={"chapter_id": str(chapter.id), "block_id": str(block.id), "block_type": block.block_type})
    await db.commit()
    return {"id": str(block.id), "position": block.position, "block_type": block.block_type}


@router.put("/chapters/{chapter_id}/blocks/reorder")
async def reorder_blocks(
    chapter_id: uuid.UUID, body: ReorderRequest, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_role("teacher")),
) -> dict:
    chapter, subject = await _get_owned_chapter(db, chapter_id, teacher)
    blocks = (await db.execute(select(ChapterBlock).where(ChapterBlock.chapter_id == chapter.id))).scalars().all()
    blocks_by_id = {b.id: b for b in blocks}
    if set(body.ids) != set(blocks_by_id.keys()):
        raise _bad_request("Reorder must include exactly this chapter's current blocks")

    for index, block_id in enumerate(body.ids):
        blocks_by_id[block_id].position = index
    await record_event(db, user_id=teacher.id, event_type="blocks_reordered", subject_id=subject.id, payload={"chapter_id": str(chapter.id), "order": [str(i) for i in body.ids]})
    await db.commit()
    return {"reordered": len(body.ids)}


@router.delete("/chapters/{chapter_id}/blocks/{block_id}")
async def delete_block(
    chapter_id: uuid.UUID, block_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_role("teacher")),
) -> dict:
    chapter, subject = await _get_owned_chapter(db, chapter_id, teacher)
    block = (await db.execute(select(ChapterBlock).where(ChapterBlock.id == block_id, ChapterBlock.chapter_id == chapter.id))).scalar_one_or_none()
    if block is None:
        raise _not_found()

    if block.block_type == "assessment" and block.assessment_id:
        assessment = (await db.execute(select(Assessment).where(Assessment.id == block.assessment_id))).scalar_one_or_none()
        if assessment is not None:
            await db.delete(assessment)  # ON DELETE CASCADE (0004) removes the chapter_blocks row too
    else:
        await db.delete(block)

    await record_event(db, user_id=teacher.id, event_type="block_removed", subject_id=subject.id, payload={"chapter_id": str(chapter.id), "block_id": str(block_id)})
    await db.commit()
    return {"removed": True}


# --- topic edges (teacher-linked prerequisites) --------------------------------------------------

@router.get("/subjects/{subject_id}/edges")
async def list_edges(
    subject_id: uuid.UUID, db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))
) -> list[dict]:
    subject = await _get_owned_subject(db, subject_id, teacher)
    edges = (
        await db.execute(select(TopicEdge).join(Topic, Topic.id == TopicEdge.src_topic_id).where(Topic.subject_id == subject.id))
    ).scalars().all()
    return [_edge_out(e) for e in edges]


@router.post("/topics/{topic_id}/edges")
async def create_edge(
    topic_id: uuid.UUID, body: CreateEdgeRequest, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_role("teacher")),
) -> dict:
    topic, subject = await _get_owned_topic(db, topic_id, teacher)
    if body.dst_topic_id == topic.id:
        raise _bad_request("A topic cannot be its own prerequisite")
    dst = (await db.execute(select(Topic).where(Topic.id == body.dst_topic_id, Topic.subject_id == subject.id))).scalar_one_or_none()
    if dst is None:
        raise _bad_request("dst_topic_id must belong to this subject")

    await db.execute(
        pg_insert(TopicEdge)
        .values(src_topic_id=topic.id, dst_topic_id=dst.id, origin="teacher")
        .on_conflict_do_nothing()
    )
    await record_event(db, user_id=teacher.id, event_type="topic_edge_created", subject_id=subject.id, topic_id=topic.id, payload={"dst_topic_id": str(dst.id)})
    await db.commit()
    return {"src_topic_id": str(topic.id), "dst_topic_id": str(dst.id)}


@router.delete("/topics/{topic_id}/edges/{dst_topic_id}")
async def delete_edge(
    topic_id: uuid.UUID, dst_topic_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_role("teacher")),
) -> dict:
    topic, subject = await _get_owned_topic(db, topic_id, teacher)
    edge = (
        await db.execute(select(TopicEdge).where(TopicEdge.src_topic_id == topic.id, TopicEdge.dst_topic_id == dst_topic_id))
    ).scalar_one_or_none()
    if edge is None:
        raise _not_found()
    await db.delete(edge)
    await record_event(db, user_id=teacher.id, event_type="topic_edge_removed", subject_id=subject.id, topic_id=topic.id, payload={"dst_topic_id": str(dst_topic_id)})
    await db.commit()
    return {"removed": True}


# --- materials (StorageProvider + text-PDF extraction) --------------------------------------------

def _extract_pdf_text(data: bytes) -> str | None:
    # Broad catch is deliberate: any malformed/encrypted/corrupt PDF degrades to stored_only rather
    # than 500ing the whole upload - pypdf raises a wide variety of exception types for bad input.
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:
        logger.warning("material pdf extraction failed: {}", exc)
        return None


@router.post("/materials")
async def create_material(
    owner_type: str = Form(...),
    owner_id: uuid.UUID = Form(...),
    kind: str = Form(...),
    title: str = Form(...),
    url: str | None = Form(None),
    body: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_role("teacher")),
) -> dict:
    if owner_type not in _OWNER_TYPES:
        raise _bad_request("Invalid owner_type", f"must be one of: {', '.join(sorted(_OWNER_TYPES))}")
    if kind not in _MATERIAL_KINDS:
        raise _bad_request("Invalid kind", f"must be one of: {', '.join(sorted(_MATERIAL_KINDS))}")

    subject_id = await _subject_id_for_owner(db, owner_type, owner_id)
    if subject_id is None:
        raise _not_found()
    await _get_owned_subject(db, subject_id, teacher)  # staff-access check; 404s if not staff

    material = Material(
        id=uuid.uuid4(), owner_type=owner_type, owner_id=owner_id, kind=kind, title=title,
        url=None, upload_id=None, extracted_text=None, readability="stored_only", created_by=teacher.id,
    )

    if kind == "note":
        text = (body or "").strip()
        material.extracted_text = text or None
        material.readability = "readable" if text else "stored_only"
    elif kind == "link":
        if not url:
            raise _bad_request("url is required for kind=link")
        material.url = url
        material.readability = "stored_only"
    else:  # pdf | image
        if file is None:
            raise _bad_request(f"file is required for kind={kind}")
        data = await file.read()
        max_mb = settings.get("storage", "max_upload_mb", default=10)
        if len(data) > max_mb * 1024 * 1024:
            raise _bad_request("File too large", f"Max {max_mb}MB")

        storage_key = await _storage.save(data, file.filename or "upload", purpose="material")
        upload = Upload(
            id=uuid.uuid4(), user_id=teacher.id, purpose="material", ref_id=material.id,
            provider="local", storage_key=storage_key, mime=file.content_type or "application/octet-stream",
            size_bytes=len(data), expires_at=None,
        )
        db.add(upload)
        await db.flush()  # uploads row must exist before materials.upload_id's FK can reference it
        material.upload_id = upload.id

        if kind == "pdf":
            extracted = _extract_pdf_text(data)
            threshold = settings.get("storage", "materials", "min_extractable_chars", default=40)
            if extracted and len(extracted.strip()) >= threshold:
                material.extracted_text = extracted.strip()
                material.readability = "readable"
            else:
                material.readability = "stored_only"

    db.add(material)
    await db.flush()
    await record_event(
        db, user_id=teacher.id, event_type="material_uploaded", subject_id=subject_id,
        payload={"material_id": str(material.id), "kind": kind, "readability": material.readability},
    )
    await db.commit()
    return _material_out(material)


# --- pool attach: snapshot+delta enrollment (S10) ------------------------------------------------

@router.get("/pools")
async def list_attachable_pools(db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))) -> list[dict]:
    """Teacher-readable pool discovery for the attach picker (FEATURE_EXPLANATION S11: "Teacher:
    ...attaches pools"). Deliberately separate from modules/pools.py's institution-admin-gated CRUD
    surface (unchanged, out of M3's scope) - this is read-only id+name, institution-scoped."""
    pools = (
        await db.execute(select(Pool).where(Pool.institution_id == teacher.institution_id).order_by(Pool.created_at))
    ).scalars().all()
    return [{"id": str(p.id), "name": p.name} for p in pools]


@router.post("/subjects/{subject_id}/pools/{pool_id}/attach")
async def attach_pool(
    subject_id: uuid.UUID, pool_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_role("teacher")),
) -> dict:
    subject = await _get_owned_subject(db, subject_id, teacher)
    pool = (await db.execute(select(Pool).where(Pool.id == pool_id, Pool.institution_id == subject.institution_id))).scalar_one_or_none()
    if pool is None:
        raise _not_found()

    member_ids = (await db.execute(select(PoolMember.user_id).where(PoolMember.pool_id == pool.id))).scalars().all()
    added = 0
    for user_id in member_ids:
        result = await db.execute(
            pg_insert(SubjectEnrollment)
            .values(subject_id=subject.id, user_id=user_id, source_pool_id=pool.id, status="active")
            .on_conflict_do_nothing()
        )
        if result.rowcount:
            added += 1
            await record_event(db, user_id=user_id, event_type="subject_enrolled", subject_id=subject.id, payload={"source_pool_id": str(pool.id)})

    await record_event(db, user_id=teacher.id, event_type="pool_attached", subject_id=subject.id, payload={"pool_id": str(pool.id), "added": added})
    await db.commit()
    return {"attached": added}


@router.get("/subjects/{subject_id}/pool-deltas")
async def pool_deltas(
    subject_id: uuid.UUID, db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))
) -> list[dict]:
    subject = await _get_owned_subject(db, subject_id, teacher)
    pool_ids = (
        await db.execute(
            select(SubjectEnrollment.source_pool_id)
            .where(SubjectEnrollment.subject_id == subject.id, SubjectEnrollment.source_pool_id.is_not(None))
            .distinct()
        )
    ).scalars().all()

    out = []
    for pool_id in pool_ids:
        pool = (await db.execute(select(Pool).where(Pool.id == pool_id))).scalar_one_or_none()
        if pool is None:
            continue
        member_ids = set((await db.execute(select(PoolMember.user_id).where(PoolMember.pool_id == pool_id))).scalars().all())
        # any status counts as "already handled" - a teacher's deliberate removal must never be
        # resurrected by a later pool sync (FEATURE_EXPLANATION S10's named failure mode).
        enrolled_ids = set(
            (await db.execute(select(SubjectEnrollment.user_id).where(SubjectEnrollment.subject_id == subject.id))).scalars().all()
        )
        new_ids = member_ids - enrolled_ids
        if new_ids:
            new_members = (await db.execute(select(User).where(User.id.in_(new_ids)))).scalars().all()
            out.append({
                "pool_id": str(pool.id),
                "pool_name": pool.name,
                "new_member_count": len(new_ids),
                "new_members": [{"id": str(u.id), "display_name": u.display_name} for u in new_members],
            })
    return out


@router.post("/subjects/{subject_id}/pools/{pool_id}/sync")
async def sync_pool(
    subject_id: uuid.UUID, pool_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_role("teacher")),
) -> dict:
    subject = await _get_owned_subject(db, subject_id, teacher)
    pool = (await db.execute(select(Pool).where(Pool.id == pool_id, Pool.institution_id == subject.institution_id))).scalar_one_or_none()
    if pool is None:
        raise _not_found()

    member_ids = set((await db.execute(select(PoolMember.user_id).where(PoolMember.pool_id == pool.id))).scalars().all())
    enrolled_ids = set(
        (await db.execute(select(SubjectEnrollment.user_id).where(SubjectEnrollment.subject_id == subject.id))).scalars().all()
    )
    new_ids = member_ids - enrolled_ids

    for user_id in new_ids:
        db.add(SubjectEnrollment(subject_id=subject.id, user_id=user_id, source_pool_id=pool.id, status="active"))
        await record_event(db, user_id=user_id, event_type="subject_enrolled", subject_id=subject.id, payload={"source_pool_id": str(pool.id), "via": "banner_sync"})

    await record_event(db, user_id=teacher.id, event_type="pool_synced", subject_id=subject.id, payload={"pool_id": str(pool.id), "added": len(new_ids)})
    await db.commit()
    return {"added": len(new_ids)}


@router.get("/subjects/{subject_id}/enrollments")
async def list_enrollments(
    subject_id: uuid.UUID, db: AsyncSession = Depends(get_db), teacher: User = Depends(require_role("teacher"))
) -> list[dict]:
    subject = await _get_owned_subject(db, subject_id, teacher)
    rows = (
        await db.execute(
            select(User, SubjectEnrollment)
            .join(SubjectEnrollment, SubjectEnrollment.user_id == User.id)
            .where(SubjectEnrollment.subject_id == subject.id, SubjectEnrollment.status == "active")
        )
    ).all()
    return [
        {"id": str(u.id), "display_name": u.display_name, "roll_number": u.roll_number, "source_pool_id": str(e.source_pool_id) if e.source_pool_id else None}
        for u, e in rows
    ]


@router.delete("/subjects/{subject_id}/enrollments/{user_id}")
async def remove_enrollment(
    subject_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_role("teacher")),
) -> dict:
    subject = await _get_owned_subject(db, subject_id, teacher)
    enrollment = (
        await db.execute(select(SubjectEnrollment).where(SubjectEnrollment.subject_id == subject.id, SubjectEnrollment.user_id == user_id))
    ).scalar_one_or_none()
    if enrollment is None:
        raise _not_found()
    enrollment.status = "archived"
    enrollment.archived_at = datetime.now(timezone.utc)
    await record_event(db, user_id=user_id, event_type="subject_enrollment_archived", subject_id=subject.id, payload={"removed_by": str(teacher.id)})
    await db.commit()
    return {"archived": True}


# --- student read surface: published structure ONLY -----------------------------------------------

@router.get("/student/subjects")
async def list_student_subjects(db: AsyncSession = Depends(get_db), student: User = Depends(require_role("student"))) -> list[dict]:
    subjects = (
        await db.execute(
            select(Subject)
            .join(SubjectEnrollment, SubjectEnrollment.subject_id == Subject.id)
            .where(SubjectEnrollment.user_id == student.id, SubjectEnrollment.status == "active", Subject.status == "published")
            .order_by(Subject.created_at)
        )
    ).scalars().all()
    return [_subject_out(s) for s in subjects]


@router.get("/student/subjects/{subject_id}")
async def get_student_subject(
    subject_id: uuid.UUID, db: AsyncSession = Depends(get_db), student: User = Depends(require_role("student"))
) -> dict:
    subject = await _get_enrolled_subject(db, subject_id, student)

    chapters = (
        await db.execute(select(Chapter).where(Chapter.subject_id == subject.id, Chapter.status == "published").order_by(Chapter.position))
    ).scalars().all()
    chapter_ids = [c.id for c in chapters]
    blocks = (
        await db.execute(
            select(ChapterBlock).where(ChapterBlock.chapter_id.in_(chapter_ids)).order_by(ChapterBlock.chapter_id, ChapterBlock.position)
        )
    ).scalars().all() if chapter_ids else []

    topic_ids = {b.topic_id for b in blocks if b.topic_id}
    topics_by_id = {}
    if topic_ids:
        rows = (await db.execute(select(Topic).where(Topic.id.in_(topic_ids)))).scalars().all()
        topics_by_id = {t.id: t for t in rows}

    assessment_ids = {b.assessment_id for b in blocks if b.assessment_id}
    assessments_by_id = {}
    if assessment_ids:
        rows = (await db.execute(select(Assessment).where(Assessment.id.in_(assessment_ids), Assessment.status == "published"))).scalars().all()
        assessments_by_id = {a.id: a for a in rows}

    edges = (
        await db.execute(
            select(TopicEdge).where(TopicEdge.src_topic_id.in_(topics_by_id.keys()), TopicEdge.dst_topic_id.in_(topics_by_id.keys()))
        )
    ).scalars().all() if topics_by_id else []

    materials = (
        await db.execute(
            select(Material).where(
                ((Material.owner_type == "subject") & (Material.owner_id == subject.id))
                | ((Material.owner_type == "chapter") & (Material.owner_id.in_(chapter_ids)))
                | ((Material.owner_type == "topic") & (Material.owner_id.in_(list(topics_by_id.keys()))))
            )
        )
    ).scalars().all()

    blocks_by_chapter: dict[uuid.UUID, list[dict]] = {c.id: [] for c in chapters}
    for b in blocks:
        if b.block_type == "topic" and b.topic_id in topics_by_id:
            blocks_by_chapter[b.chapter_id].append({"id": str(b.id), "position": b.position, "block_type": "topic", "topic": _topic_out(topics_by_id[b.topic_id])})
        elif b.block_type == "assessment" and b.assessment_id in assessments_by_id:
            a = assessments_by_id[b.assessment_id]
            blocks_by_chapter[b.chapter_id].append({"id": str(b.id), "position": b.position, "block_type": "assessment", "assessment": {"id": str(a.id), "title": a.title}})

    return {
        **_subject_out(subject),
        "chapters": [{**_chapter_out(c), "blocks": blocks_by_chapter[c.id]} for c in chapters],
        "edges": [_edge_out(e) for e in edges],
        "materials": [_material_out(m) for m in materials],
    }
