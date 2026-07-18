"""M2 institutions tests: self-serve signup, roster list, invite, CSV import, reissue, and the
RULES #10 cross-institution isolation guarantee (admin A must never read institution B).
Requires a real Postgres (DATABASE_URL) with migrations applied - same pattern as test_auth.py."""
from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="requires DATABASE_URL (postgres)"),
]

import app.core.db as db_module  # noqa: E402
from app.core.db import Institution, SessionLocal, User  # noqa: E402
from app.core.security import hash_secret  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _fresh_engine_per_test():
    db_module._engine = None
    db_module._session_factory = None
    yield
    if db_module._engine is not None:
        await db_module._engine.dispose()
    db_module._engine = None
    db_module._session_factory = None


@pytest_asyncio.fixture()
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _create_institution(name: str = "Test Institution") -> str:
    slug = f"test-{uuid.uuid4().hex[:8]}"
    async with SessionLocal() as db:
        db.add(Institution(id=uuid.uuid4(), name=name, slug=slug, is_personal=False))
        await db.commit()
    return slug


async def _create_admin(slug: str, *, password: str = "adminpass-1") -> str:
    identifier = f"admin-{uuid.uuid4().hex[:6]}@test.local"
    async with SessionLocal() as db:
        institution = (await db.execute(select(Institution).where(Institution.slug == slug))).scalar_one()
        db.add(
            User(
                id=uuid.uuid4(), institution_id=institution.id, role="admin", display_name="Admin",
                roll_number=None, email=identifier, password_hash=hash_secret(password),
                status="active", activation_code_hash=None, locale="en",
            )
        )
        await db.commit()
    return identifier


async def _login(client: AsyncClient, slug: str, identifier: str, password: str) -> str:
    res = await client.post(
        "/api/auth/login", json={"institution_slug": slug, "identifier": identifier, "password": password}
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_invite_user_returns_activation_code_and_can_activate_and_login(client: AsyncClient):
    slug = await _create_institution()
    admin_id = await _create_admin(slug)
    token = await _login(client, slug, admin_id, "adminpass-1")

    res = await client.post(
        "/api/institutions/users",
        json={"role": "student", "display_name": "New Student", "roll_number": "R001"},
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["user"]["status"] == "invited"
    code = body["activation_code"]
    assert len(code) == 8

    activate = await client.post(
        "/api/auth/activate",
        json={"institution_slug": slug, "identifier": "R001", "activation_code": code, "new_password": "newpass-123"},
    )
    assert activate.status_code == 200, activate.text

    login = await client.post(
        "/api/auth/login", json={"institution_slug": slug, "identifier": "R001", "password": "newpass-123"}
    )
    assert login.status_code == 200, login.text


async def test_csv_import_creates_all_rows_and_rejects_bad_batch(client: AsyncClient):
    slug = await _create_institution()
    admin_id = await _create_admin(slug)
    token = await _login(client, slug, admin_id, "adminpass-1")

    good_csv = "display_name,role,roll_number,email\n" + "\n".join(
        f"Student {i},student,CSV{i:03d}," for i in range(10)
    )
    res = await client.post("/api/institutions/users/csv", json={"csv_text": good_csv}, headers=_auth(token))
    assert res.status_code == 200, res.text
    assert len(res.json()["created"]) == 10

    roster = await client.get("/api/institutions/users", headers=_auth(token))
    assert len(roster.json()) == 11  # 10 students + the admin

    bad_csv = "display_name,role,roll_number,email\nBad Row,not-a-role,CSV999,"
    bad_res = await client.post("/api/institutions/users/csv", json={"csv_text": bad_csv}, headers=_auth(token))
    assert bad_res.status_code == 400
    roster_after = await client.get("/api/institutions/users", headers=_auth(token))
    assert len(roster_after.json()) == 11  # all-or-nothing: nothing added on the bad batch


async def test_reissue_code_invalidates_old_code(client: AsyncClient):
    slug = await _create_institution()
    admin_id = await _create_admin(slug)
    token = await _login(client, slug, admin_id, "adminpass-1")

    invite = await client.post(
        "/api/institutions/users",
        json={"role": "student", "display_name": "Reissue Me", "roll_number": "R777"},
        headers=_auth(token),
    )
    user_id = invite.json()["user"]["id"]
    old_code = invite.json()["activation_code"]

    reissue = await client.post(f"/api/institutions/users/{user_id}/reissue-code", headers=_auth(token))
    assert reissue.status_code == 200, reissue.text
    new_code = reissue.json()["activation_code"]
    assert new_code != old_code

    stale = await client.post(
        "/api/auth/activate",
        json={"institution_slug": slug, "identifier": "R777", "activation_code": old_code, "new_password": "x1234567"},
    )
    assert stale.status_code == 400

    fresh = await client.post(
        "/api/auth/activate",
        json={"institution_slug": slug, "identifier": "R777", "activation_code": new_code, "new_password": "x1234567"},
    )
    assert fresh.status_code == 200, fresh.text


async def test_self_serve_signup_creates_personal_institution_and_logs_in(client: AsyncClient):
    res = await client.post(
        "/api/institutions/self-serve",
        json={
            "institution_name": "Solo Prof",
            "display_name": "Prof Solo",
            "email": f"solo-{uuid.uuid4().hex[:6]}@test.local",
            "password": "solopass-123",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["user"]["role"] == "teacher"
    assert body["user"]["status"] == "active"
    assert "access_token" in body

    async with SessionLocal() as db:
        institution = (
            await db.execute(select(Institution).where(Institution.slug == body["institution"]["slug"]))
        ).scalar_one()
        assert institution.is_personal is True

    # the self-serve teacher can immediately act as their own institution's admin (pools, roster)
    roster = await client.get("/api/institutions/users", headers=_auth(body["access_token"]))
    assert roster.status_code == 200
    assert len(roster.json()) == 1


async def test_regular_teacher_without_personal_institution_cannot_reach_admin_routes(client: AsyncClient):
    slug = await _create_institution()
    identifier = f"teacher-{uuid.uuid4().hex[:6]}@test.local"
    async with SessionLocal() as db:
        institution = (await db.execute(select(Institution).where(Institution.slug == slug))).scalar_one()
        db.add(
            User(
                id=uuid.uuid4(), institution_id=institution.id, role="teacher", display_name="Teacher",
                roll_number=None, email=identifier, password_hash=hash_secret("teachpass-1"),
                status="active", activation_code_hash=None, locale="en",
            )
        )
        await db.commit()
    token = await _login(client, slug, identifier, "teachpass-1")

    res = await client.get("/api/institutions/users", headers=_auth(token))
    assert res.status_code == 403


# --- RULES #10: institution-scoping. This is the one property explicitly called out for direct
# verification: admin A must never be able to list, or otherwise read, institution B's data. ---
async def test_admin_a_cannot_list_institution_b_users(client: AsyncClient):
    slug_a = await _create_institution("Institution A")
    slug_b = await _create_institution("Institution B")
    admin_a = await _create_admin(slug_a)
    await _create_admin(slug_b)  # institution B's own admin + a student below

    async with SessionLocal() as db:
        institution_b = (await db.execute(select(Institution).where(Institution.slug == slug_b))).scalar_one()
        db.add(
            User(
                id=uuid.uuid4(), institution_id=institution_b.id, role="student", display_name="B Student",
                roll_number="B001", email=None, password_hash=None, status="invited",
                activation_code_hash=hash_secret("11112222"), locale="en",
            )
        )
        await db.commit()

    token_a = await _login(client, slug_a, admin_a, "adminpass-1")
    roster = await client.get("/api/institutions/users", headers=_auth(token_a))
    assert roster.status_code == 200
    names = {u["display_name"] for u in roster.json()}
    assert "B Student" not in names
    assert names == {"Admin"}  # only admin A's own institution, nothing from B
