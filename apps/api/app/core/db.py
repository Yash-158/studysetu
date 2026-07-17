"""Async SQLAlchemy engine/session factory. Pool sizes from config/database.yaml.
Models: institutions/users only (M1 scope). Later milestones add their own tables here as needed."""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings

user_role_enum = PgEnum("admin", "teacher", "student", name="user_role", create_type=False)
account_status_enum = PgEnum("invited", "active", "disabled", name="account_status", create_type=False)


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
