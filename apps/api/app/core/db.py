"""Async SQLAlchemy engine/session factory. Pool sizes from config/database.yaml.
Models: institutions/users (M1) + pools/pool_members (M2). Later milestones add their own tables
here as needed."""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, BigInteger, Boolean, DateTime, FetchedValue, ForeignKey, Integer, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import JSONB, REAL, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings

user_role_enum = PgEnum("admin", "teacher", "student", name="user_role", create_type=False)
account_status_enum = PgEnum("invited", "active", "disabled", name="account_status", create_type=False)
publish_status_enum = PgEnum("draft", "published", "archived", name="publish_status", create_type=False)
enrollment_status_enum = PgEnum("active", "archived", name="enrollment_status", create_type=False)
topic_kind_enum = PgEnum("subject", "explore", name="topic_kind", create_type=False)
block_type_enum = PgEnum("topic", "assessment", name="block_type", create_type=False)
edge_origin_enum = PgEnum("implicit", "teacher", "ai_suggested", name="edge_origin", create_type=False)
material_kind_enum = PgEnum("pdf", "note", "link", "image", name="material_kind", create_type=False)
material_owner_enum = PgEnum("subject", "chapter", "topic", name="material_owner", create_type=False)
readability_enum = PgEnum("readable", "stored_only", name="readability", create_type=False)
gating_mode_enum = PgEnum("open", "recommended", "locked", name="gating_mode", create_type=False)
feedback_mode_enum = PgEnum("instant", "end", "after_deadline", name="feedback_mode", create_type=False)
upload_purpose_enum = PgEnum("material", "submission", "doubt_photo", name="upload_purpose", create_type=False)
item_origin_enum = PgEnum("ai", "teacher", name="item_origin", create_type=False)
review_status_enum = PgEnum("draft", "approved", "flagged", "retired", name="review_status", create_type=False)
attempt_context_enum = PgEnum("diagnostic", "practice", "assessment", "revision", "explore", name="attempt_context", create_type=False)
session_status_enum = PgEnum("planned", "in_progress", "completed", "abandoned", name="session_status", create_type=False)
artifact_scope_enum = PgEnum("topic_shared", "segment_shared", "student_unique", "explore_global", name="artifact_scope", create_type=False)
artifact_type_enum = PgEnum(
    "item_bank", "segment", "summary", "cheatsheet", "flashcards", "session_plan",
    "doubt_reply", "assignment_feedback", "mentor_card", name="artifact_type", create_type=False,
)


class Base(DeclarativeBase):
    pass


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String)
    is_personal: Mapped[bool] = mapped_column(Boolean)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id"))
    role: Mapped[str] = mapped_column(user_role_enum)
    display_name: Mapped[str] = mapped_column(String)
    roll_number: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    password_hash: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(account_status_enum)
    activation_code_hash: Mapped[str | None] = mapped_column(String)
    locale: Mapped[str] = mapped_column(String)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Pool(Base):
    __tablename__ = "pools"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id"))
    name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class PoolMember(Base):
    __tablename__ = "pool_members"

    pool_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pools.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String)
    code: Mapped[str | None] = mapped_column(String)
    term: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(publish_status_enum, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SubjectStaff(Base):
    __tablename__ = "subject_staff"

    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)


class SubjectEnrollment(Base):
    __tablename__ = "subject_enrollments"

    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    source_pool_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pools.id"))
    status: Mapped[str] = mapped_column(enrollment_status_enum, default="active")
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"))
    title: Mapped[str] = mapped_column(String)
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(publish_status_enum, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    kind: Mapped[str] = mapped_column(topic_kind_enum, default="subject")
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"))
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String, default="")
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChapterBlock(Base):
    __tablename__ = "chapter_blocks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    chapter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id"))
    position: Mapped[int] = mapped_column(Integer)
    block_type: Mapped[str] = mapped_column(block_type_enum)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id"))
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("assessments.id"))


class TopicEdge(Base):
    __tablename__ = "topic_edges"

    src_topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id"), primary_key=True)
    dst_topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id"), primary_key=True)
    origin: Mapped[str] = mapped_column(edge_origin_enum, default="teacher")
    weight: Mapped[float] = mapped_column(default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    owner_type: Mapped[str] = mapped_column(material_owner_enum)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(material_kind_enum)
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str | None] = mapped_column(String)
    upload_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("uploads.id"))
    extracted_text: Mapped[str | None] = mapped_column(String)
    readability: Mapped[str] = mapped_column(readability_enum, default="stored_only")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Assessment(Base):
    """Minimal placeholder shell for chapter_blocks (M3 scope: title + defaults only).
    Taking/grading/gating UI is M7 territory - this table's fuller use starts then."""
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String)
    gating: Mapped[str] = mapped_column(gating_mode_enum, default="recommended")
    feedback: Mapped[str] = mapped_column(feedback_mode_enum, default="end")
    status: Mapped[str] = mapped_column(publish_status_enum, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    purpose: Mapped[str] = mapped_column(upload_purpose_enum)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    provider: Mapped[str] = mapped_column(String, default="local")
    storage_key: Mapped[str] = mapped_column(String)
    mime: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Misconception(Base):
    __tablename__ = "misconceptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id"))
    origin: Mapped[str] = mapped_column(item_origin_enum, default="ai")
    status: Mapped[str] = mapped_column(review_status_enum, default="draft")
    stem: Mapped[str] = mapped_column(String)
    difficulty: Mapped[int] = mapped_column(SmallInteger)  # -1 easy, 0 medium, 1 hard
    explanation: Mapped[str] = mapped_column(String, default="")
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ItemOption(Base):
    __tablename__ = "item_options"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    position: Mapped[int] = mapped_column(SmallInteger)
    body: Mapped[str] = mapped_column(String)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    misconception_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("misconceptions.id"))


class DiagnosticSession(Base):
    __tablename__ = "diagnostic_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id"))
    item_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)))
    score: Mapped[int | None] = mapped_column(SmallInteger)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    option_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("item_options.id"))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    context: Mapped[str] = mapped_column(attempt_context_enum)
    container_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Mastery(Base):
    __tablename__ = "mastery"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id"), primary_key=True)
    p_known: Mapped[float] = mapped_column(REAL, default=0.3)
    confidence: Mapped[float] = mapped_column(REAL, default=1.0)
    attempts_count: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class MasteryHistory(Base):
    __tablename__ = "mastery_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id"))
    p_known: Mapped[float] = mapped_column(REAL)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class LearningSession(Base):
    __tablename__ = "learning_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id"))
    diagnostic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("diagnostic_sessions.id"))
    plan: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(session_status_enum, default="in_progress")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Event(Base):
    """Read-mostly mapping onto the append-only timeline ledger (RULES #3) - writes go through
    record_event()'s raw INSERT below, never through this class, so ingest_id/server_ts defaults
    stay exactly what the migration specifies. ingest_id (a real bigint IDENTITY column) is the
    reliable insertion-order tiebreaker: occurred_at/server_ts both use now(), which Postgres holds
    stable for the whole transaction - several events emitted in one request (e.g. session_started
    + multiple revision_injected rows) can share an identical timestamp, so anything that needs
    true emission order (the M5 GATE's causal-chain proof) must order by ingest_id, not time."""
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    # FetchedValue(), not a plain mapped_column - this is a GENERATED ALWAYS AS IDENTITY column
    # (Postgres rejects any explicit INSERT value, even NULL); FetchedValue() tells the ORM the
    # database supplies it and to never include it in an INSERT statement's column list.
    ingest_id: Mapped[int] = mapped_column(BigInteger, server_default=FetchedValue())
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"))
    topic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id"))
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    payload: Mapped[dict] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    server_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class GeneratedArtifact(Base):
    __tablename__ = "generated_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    scope: Mapped[str] = mapped_column(artifact_scope_enum)
    artifact_type: Mapped[str] = mapped_column(artifact_type_enum)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    cache_key: Mapped[str] = mapped_column(String)
    content: Mapped[dict] = mapped_column(JSONB)
    source_hash: Mapped[str | None] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(String, default="v1")
    model: Mapped[str | None] = mapped_column(String)
    tokens: Mapped[int | None] = mapped_column(Integer)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class AiInvocation(Base):
    """ingest_id (0008): a real monotonic tiebreaker for emission order - created_at alone ties
    within a transaction (Postgres holds now() stable for its whole duration), which is exactly
    what made tests/test_m4_audit.py's provider-order assertions flaky (see docs/DATABASE.md 0008)."""
    __tablename__ = "ai_invocations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    ingest_id: Mapped[int] = mapped_column(BigInteger, server_default=FetchedValue())
    task: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    ref_artifact: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("generated_artifacts.id"))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class DemoCache(Base):
    __tablename__ = "demo_cache"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    task: Mapped[str] = mapped_column(String)
    input_hash: Mapped[str] = mapped_column(String)
    response: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


# Lazy: apps like the healthcheck-only test suite import this module without a DATABASE_URL set;
# building the engine eagerly at import time would crash them for no reason.
_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _engine, _session_factory
    if _session_factory is None:
        pool_min = settings.get("database", "pool", "min_size", default=2)
        pool_max = settings.get("database", "pool", "max_size", default=10)
        _engine = create_async_engine(
            settings.database_url,
            pool_size=pool_min,
            max_overflow=max(0, pool_max - pool_min),
            echo=settings.get("database", "echo_sql", default=False),
        )
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _session_factory


def SessionLocal() -> AsyncSession:
    return _get_session_factory()()


async def get_db():
    async with SessionLocal() as session:
        yield session


async def record_event(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    event_type: str,
    payload: dict | None = None,
    subject_id: uuid.UUID | None = None,
    topic_id: uuid.UUID | None = None,
) -> None:
    """Append-only timeline row (RULES #3: every user-visible action emits one)."""
    await db.execute(
        text(
            "INSERT INTO events (user_id, event_type, subject_id, topic_id, payload) "
            "VALUES (:user_id, :event_type, :subject_id, :topic_id, CAST(:payload AS jsonb))"
        ),
        {
            "user_id": user_id,
            "event_type": event_type,
            "subject_id": subject_id,
            "topic_id": topic_id,
            "payload": json.dumps(payload or {}),
        },
    )
