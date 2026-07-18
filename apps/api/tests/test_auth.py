"""M1 auth tests: activation, login, refresh, role guard, token expiry, concurrent-login anomaly.
Requires a real Postgres (DATABASE_URL) with migrations applied - see .github/workflows/ci.yml
`api` job. Skipped locally when DATABASE_URL isn't set (matches test_health.py's DB-free default)."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import select, text

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="requires DATABASE_URL (postgres)"),
]

import app.core.db as db_module  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.db import Institution, SessionLocal, User  # noqa: E402
from app.core.security import hash_secret, require_role  # noqa: E402
from app.main import app  # noqa: E402

_ALGORITHM = settings.get("auth", "jwt", "algorithm", default="HS256")


@pytest_asyncio.fixture(autouse=True)
async def _fresh_engine_per_test():
    # pytest-asyncio gives each test its own event loop; asyncpg connections are loop-bound, so a
    # module-level engine singleton reused across tests breaks. Rebuild it fresh every test.
    db_module._engine = None
    db_module._session_factory = None
    yield
    if db_module._engine is not None:
        await db_module._engine.dispose()
    db_module._engine = None
    db_module._session_factory = None


async def _create_institution() -> str:
    slug = f"test-{uuid.uuid4().hex[:8]}"
    async with SessionLocal() as db:
        db.add(Institution(id=uuid.uuid4(), name="Test Institution", slug=slug, is_personal=False))
        await db.commit()
    return slug


async def _create_user(
    slug: str,
    *,
    role: str = "student",
    status: str = "invited",
    password: str | None = None,
    activation_code: str = "12345678",
    created_at: datetime | None = None,
) -> tuple[User, str]:
    identifier = f"{role}-{uuid.uuid4().hex[:6]}@test.local"
    async with SessionLocal() as db:
        institution = (await db.execute(select(Institution).where(Institution.slug == slug))).scalar_one()
        user = User(
            id=uuid.uuid4(),
            institution_id=institution.id,
            role=role,
            display_name=role.title(),
            roll_number=None,
            email=identifier,
            password_hash=hash_secret(password) if password else None,
            status=status,
            activation_code_hash=hash_secret(activation_code) if status == "invited" else None,
            locale="en",
        )
        if created_at is not None:
            user.created_at = created_at
            user.issued_at = created_at  # activation TTL is measured from issued_at (M2)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user, identifier


async def _count_events(user_id: uuid.UUID, event_type: str) -> int:
    async with SessionLocal() as db:
        return (
            await db.execute(
                text("SELECT count(*) FROM events WHERE user_id = :uid AND event_type = :et"),
                {"uid": user_id, "et": event_type},
            )
        ).scalar_one()


@pytest_asyncio.fixture()
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_activate_success(client: AsyncClient):
    slug = await _create_institution()
    user, identifier = await _create_user(slug, activation_code="87654321")

    res = await client.post(
        "/api/auth/activate",
        json={
            "institution_slug": slug,
            "identifier": identifier,
            "activation_code": "87654321",
            "new_password": "correct-horse-1",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["user"]["role"] == "student"

    async with SessionLocal() as db:
        refreshed = (await db.execute(select(User).where(User.id == user.id))).scalar_one()
        assert refreshed.status == "active"
        assert refreshed.password_hash is not None
        assert refreshed.activation_code_hash is None
    assert await _count_events(user.id, "account_activated") == 1


async def test_activate_wrong_code_rejected(client: AsyncClient):
    slug = await _create_institution()
    _, identifier = await _create_user(slug, activation_code="87654321")

    res = await client.post(
        "/api/auth/activate",
        json={
            "institution_slug": slug,
            "identifier": identifier,
            "activation_code": "wrong-code",
            "new_password": "correct-horse-1",
        },
    )
    assert res.status_code == 400


async def test_activate_expired_code_rejected(client: AsyncClient):
    slug = await _create_institution()
    ttl_hours = settings.get("auth", "activation", "code_ttl_hours", default=72)
    stale = datetime.now(timezone.utc) - timedelta(hours=ttl_hours + 1)
    _, identifier = await _create_user(slug, activation_code="87654321", created_at=stale)

    res = await client.post(
        "/api/auth/activate",
        json={
            "institution_slug": slug,
            "identifier": identifier,
            "activation_code": "87654321",
            "new_password": "correct-horse-1",
        },
    )
    assert res.status_code == 400


async def test_login_success_and_wrong_password(client: AsyncClient):
    slug = await _create_institution()
    _, identifier = await _create_user(slug, status="active", password="right-pass-1")

    bad = await client.post(
        "/api/auth/login", json={"institution_slug": slug, "identifier": identifier, "password": "nope"}
    )
    assert bad.status_code == 401

    ok = await client.post(
        "/api/auth/login",
        json={"institution_slug": slug, "identifier": identifier, "password": "right-pass-1"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert "access_token" in body and "refresh_token" in body

    claims = jwt.decode(body["access_token"], settings.jwt_secret, algorithms=[_ALGORITHM])
    assert claims["role"] == "student"
    assert claims["type"] == "access"


async def test_refresh_and_me(client: AsyncClient):
    slug = await _create_institution()
    _, identifier = await _create_user(slug, status="active", password="right-pass-1")
    login = await client.post(
        "/api/auth/login",
        json={"institution_slug": slug, "identifier": identifier, "password": "right-pass-1"},
    )
    tokens = login.json()

    refreshed = await client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200, refreshed.text
    new_access = refreshed.json()["access_token"]

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200
    assert me.json()["email"] == identifier


async def test_me_requires_bearer(client: AsyncClient):
    res = await client.get("/api/auth/me")
    assert res.status_code == 401


async def test_access_token_expiry_rejected(client: AsyncClient):
    slug = await _create_institution()
    user, _ = await _create_user(slug, status="active", password="right-pass-1")
    expired_claims = {
        "sub": str(user.id),
        "role": user.role,
        "institution_id": str(user.institution_id),
        "type": "access",
        "iat": datetime.now(timezone.utc) - timedelta(hours=1),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    expired_token = jwt.encode(expired_claims, settings.jwt_secret, algorithm=_ALGORITHM)

    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401


async def test_refresh_token_expiry_rejected(client: AsyncClient):
    slug = await _create_institution()
    user, _ = await _create_user(slug, status="active", password="right-pass-1")
    expired_claims = {
        "sub": str(user.id),
        "role": user.role,
        "institution_id": str(user.institution_id),
        "type": "refresh",
        "iat": datetime.now(timezone.utc) - timedelta(days=40),
        "exp": datetime.now(timezone.utc) - timedelta(days=1),
    }
    expired_refresh = jwt.encode(expired_claims, settings.jwt_secret, algorithm=_ALGORITHM)

    res = await client.post("/api/auth/refresh", json={"refresh_token": expired_refresh})
    assert res.status_code == 401


async def test_require_role_guard_403_and_200():
    mini = FastAPI()

    @mini.get("/teacher-only")
    async def teacher_only(user=Depends(require_role("teacher"))):
        return {"ok": True, "role": user.role}

    transport = ASGITransport(app=mini)
    slug = await _create_institution()
    _, student_id = await _create_user(slug, role="student", status="active", password="pw-student-1")
    _, teacher_id = await _create_user(slug, role="teacher", status="active", password="pw-teacher-1")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as auth_client:
        student_login = await auth_client.post(
            "/api/auth/login", json={"institution_slug": slug, "identifier": student_id, "password": "pw-student-1"}
        )
        teacher_login = await auth_client.post(
            "/api/auth/login", json={"institution_slug": slug, "identifier": teacher_id, "password": "pw-teacher-1"}
        )

    async with AsyncClient(transport=transport, base_url="http://test") as mini_client:
        as_student = await mini_client.get(
            "/teacher-only", headers={"Authorization": f"Bearer {student_login.json()['access_token']}"}
        )
        as_teacher = await mini_client.get(
            "/teacher-only", headers={"Authorization": f"Bearer {teacher_login.json()['access_token']}"}
        )

    assert as_student.status_code == 403
    assert as_teacher.status_code == 200


async def test_concurrent_login_emits_anomaly_event(client: AsyncClient):
    slug = await _create_institution()
    user, identifier = await _create_user(slug, status="active", password="right-pass-1")

    first = await client.post(
        "/api/auth/login",
        json={"institution_slug": slug, "identifier": identifier, "password": "right-pass-1"},
    )
    assert first.status_code == 200
    second = await client.post(
        "/api/auth/login",
        json={"institution_slug": slug, "identifier": identifier, "password": "right-pass-1"},
    )
    assert second.status_code == 200
    assert await _count_events(user.id, "login_anomaly") == 1
