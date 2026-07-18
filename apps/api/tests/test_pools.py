"""M2 pools tests: create/list/member add+remove, and the RULES #10 cross-institution isolation
guarantee for pool reads (admin A reading admin B's pool by id must 404, not leak data).
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


async def _create_student(slug: str, roll_number: str) -> str:
    async with SessionLocal() as db:
        institution = (await db.execute(select(Institution).where(Institution.slug == slug))).scalar_one()
        user_id = uuid.uuid4()
        db.add(
            User(
                id=user_id, institution_id=institution.id, role="student", display_name=roll_number,
                roll_number=roll_number, email=None, password_hash=None, status="invited",
                activation_code_hash=hash_secret("12345678"), locale="en",
            )
        )
        await db.commit()
    return str(user_id)


async def _login(client: AsyncClient, slug: str, identifier: str, password: str) -> str:
    res = await client.post(
        "/api/auth/login", json={"institution_slug": slug, "identifier": identifier, "password": password}
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_create_pool_and_add_remove_members(client: AsyncClient):
    slug = await _create_institution()
    admin_id = await _create_admin(slug)
    token = await _login(client, slug, admin_id, "adminpass-1")
    student_id = await _create_student(slug, "P001")

    created = await client.post("/api/pools", json={"name": "CSE-3A"}, headers=_auth(token))
    assert created.status_code == 200, created.text
    pool_id = created.json()["id"]
    assert created.json()["member_count"] == 0

    added = await client.post(
        f"/api/pools/{pool_id}/members", json={"user_ids": [student_id]}, headers=_auth(token)
    )
    assert added.status_code == 200, added.text
    assert added.json()["added"] == 1

    detail = await client.get(f"/api/pools/{pool_id}", headers=_auth(token))
    assert detail.status_code == 200
    assert len(detail.json()["members"]) == 1
    assert detail.json()["members"][0]["roll_number"] == "P001"

    removed = await client.delete(f"/api/pools/{pool_id}/members/{student_id}", headers=_auth(token))
    assert removed.status_code == 200
    detail_after = await client.get(f"/api/pools/{pool_id}", headers=_auth(token))
    assert len(detail_after.json()["members"]) == 0


async def test_cannot_add_foreign_institution_user_to_pool(client: AsyncClient):
    slug_a = await _create_institution("Institution A")
    slug_b = await _create_institution("Institution B")
    admin_a = await _create_admin(slug_a)
    token_a = await _login(client, slug_a, admin_a, "adminpass-1")
    foreign_student_id = await _create_student(slug_b, "B001")

    pool = await client.post("/api/pools", json={"name": "A-Pool"}, headers=_auth(token_a))
    pool_id = pool.json()["id"]

    res = await client.post(
        f"/api/pools/{pool_id}/members", json={"user_ids": [foreign_student_id]}, headers=_auth(token_a)
    )
    assert res.status_code == 400


# --- RULES #10: institution-scoping for pool reads. ---
async def test_admin_a_cannot_read_institution_b_pool_by_id(client: AsyncClient):
    slug_a = await _create_institution("Institution A")
    slug_b = await _create_institution("Institution B")
    admin_a = await _create_admin(slug_a)
    admin_b = await _create_admin(slug_b)
    token_a = await _login(client, slug_a, admin_a, "adminpass-1")
    token_b = await _login(client, slug_b, admin_b, "adminpass-1")

    pool_b = await client.post("/api/pools", json={"name": "B-Pool"}, headers=_auth(token_b))
    pool_b_id = pool_b.json()["id"]

    res = await client.get(f"/api/pools/{pool_b_id}", headers=_auth(token_a))
    assert res.status_code == 404

    listing = await client.get("/api/pools", headers=_auth(token_a))
    assert listing.status_code == 200
    assert all(p["name"] != "B-Pool" for p in listing.json())
