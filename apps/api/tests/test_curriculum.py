"""M3 curriculum tests: subject/chapter/topic/block CRUD, atomic reorder, topic edges, materials
upload (readable vs stored_only PDF extraction), publish cascade, pool snapshot+delta+sync, and
teacher/student/institution access-scoping.
Requires a real Postgres (DATABASE_URL) with migrations applied - same pattern as test_pools.py."""
from __future__ import annotations

import io
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
from app.core.db import Institution, Pool, PoolMember, SessionLocal, User  # noqa: E402
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


async def _create_user(slug: str, role: str, *, password: str = "userpass-1") -> str:
    identifier = f"{role}-{uuid.uuid4().hex[:6]}@test.local"
    async with SessionLocal() as db:
        institution = (await db.execute(select(Institution).where(Institution.slug == slug))).scalar_one()
        db.add(
            User(
                id=uuid.uuid4(), institution_id=institution.id, role=role, display_name=role.title(),
                roll_number=None, email=identifier, password_hash=hash_secret(password),
                status="active", activation_code_hash=None, locale="en",
            )
        )
        await db.commit()
    return identifier


async def _login(client: AsyncClient, slug: str, identifier: str, password: str = "userpass-1") -> str:
    res = await client.post("/api/auth/login", json={"institution_slug": slug, "identifier": identifier, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _teacher(client: AsyncClient, slug: str) -> tuple[str, str]:
    identifier = await _create_user(slug, "teacher")
    token = await _login(client, slug, identifier)
    return identifier, token


def _build_pdf(text: bytes) -> bytes:
    """Hand-built minimal single-page PDF (valid xref/trailer) so tests need no extra PDF-writer dep."""
    content = b"BT /F1 24 Tf 10 100 Td (" + text + b") Tj ET"
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 300 300] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, obj_body in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(str(i).encode() + b" 0 obj\n" + obj_body + b"\nendobj\n")
    xref_pos = out.tell()
    n = len(objs) + 1
    out.write(b"xref\n0 " + str(n).encode() + b"\n0000000000 65535 f \n")
    for off in offsets:
        out.write(("%010d 00000 n \n" % off).encode())
    out.write(b"trailer\n<< /Size " + str(n).encode() + b" /Root 1 0 R >>\nstartxref\n" + str(xref_pos).encode() + b"\n%%EOF")
    return out.getvalue()


BLANK_PDF = _build_pdf(b"")
TEXT_PDF = _build_pdf(b"Digital Image Processing covers transforms and frequency domain filtering in real depth")


async def test_subject_chapter_topic_block_full_build(client: AsyncClient):
    slug = await _create_institution()
    _, token = await _teacher(client, slug)

    subject = (await client.post("/api/curriculum/subjects", json={"name": "Digital Image Processing", "code": "DIP"}, headers=_auth(token))).json()
    assert subject["status"] == "draft"

    ch1 = (await client.post(f"/api/curriculum/subjects/{subject['id']}/chapters", json={"title": "Foundations"}, headers=_auth(token))).json()
    ch2 = (await client.post(f"/api/curriculum/subjects/{subject['id']}/chapters", json={"title": "Frequency Domain"}, headers=_auth(token))).json()
    assert ch1["position"] == 0 and ch2["position"] == 1

    topics = []
    for title in ["Sampling", "Quantization", "Transforms", "Histograms", "Frequency Filtering"]:
        t = (await client.post(f"/api/curriculum/subjects/{subject['id']}/topics", json={"title": title}, headers=_auth(token))).json()
        topics.append(t)

    for t in topics[:3]:
        r = await client.post(f"/api/curriculum/chapters/{ch1['id']}/blocks", json={"block_type": "topic", "topic_id": t["id"]}, headers=_auth(token))
        assert r.status_code == 200, r.text
    for t in topics[3:]:
        r = await client.post(f"/api/curriculum/chapters/{ch2['id']}/blocks", json={"block_type": "topic", "topic_id": t["id"]}, headers=_auth(token))
        assert r.status_code == 200, r.text
    block = (await client.post(f"/api/curriculum/chapters/{ch2['id']}/blocks", json={"block_type": "assessment", "assessment_title": "Unit Check 1"}, headers=_auth(token))).json()
    assert block["block_type"] == "assessment"

    edge = await client.post(
        f"/api/curriculum/topics/{topics[2]['id']}/edges", json={"dst_topic_id": topics[4]["id"]}, headers=_auth(token)
    )
    assert edge.status_code == 200, edge.text

    detail = (await client.get(f"/api/curriculum/subjects/{subject['id']}", headers=_auth(token))).json()
    assert len(detail["chapters"]) == 2
    assert len(detail["topics"]) == 5
    assert len(detail["edges"]) == 1
    assert len(detail["chapters"][1]["blocks"]) == 3  # 2 topics + 1 assessment


async def test_chapter_reorder_is_atomic_and_persists(client: AsyncClient):
    slug = await _create_institution()
    _, token = await _teacher(client, slug)
    subject = (await client.post("/api/curriculum/subjects", json={"name": "S"}, headers=_auth(token))).json()
    ch1 = (await client.post(f"/api/curriculum/subjects/{subject['id']}/chapters", json={"title": "A"}, headers=_auth(token))).json()
    ch2 = (await client.post(f"/api/curriculum/subjects/{subject['id']}/chapters", json={"title": "B"}, headers=_auth(token))).json()

    res = await client.put(
        f"/api/curriculum/subjects/{subject['id']}/chapters/reorder", json={"ids": [ch2["id"], ch1["id"]]}, headers=_auth(token)
    )
    assert res.status_code == 200, res.text

    detail = (await client.get(f"/api/curriculum/subjects/{subject['id']}", headers=_auth(token))).json()
    assert [c["title"] for c in detail["chapters"]] == ["B", "A"]

    bad = await client.put(f"/api/curriculum/subjects/{subject['id']}/chapters/reorder", json={"ids": [ch1["id"]]}, headers=_auth(token))
    assert bad.status_code == 400


async def test_pdf_material_readable_vs_stored_only(client: AsyncClient):
    slug = await _create_institution()
    _, token = await _teacher(client, slug)
    subject = (await client.post("/api/curriculum/subjects", json={"name": "S"}, headers=_auth(token))).json()

    readable = await client.post(
        "/api/curriculum/materials",
        data={"owner_type": "subject", "owner_id": subject["id"], "kind": "pdf", "title": "Syllabus"},
        files={"file": ("syllabus.pdf", TEXT_PDF, "application/pdf")},
        headers=_auth(token),
    )
    assert readable.status_code == 200, readable.text
    assert readable.json()["readability"] == "readable"

    scanned = await client.post(
        "/api/curriculum/materials",
        data={"owner_type": "subject", "owner_id": subject["id"], "kind": "pdf", "title": "Scanned notes"},
        files={"file": ("scan.pdf", BLANK_PDF, "application/pdf")},
        headers=_auth(token),
    )
    assert scanned.status_code == 200, scanned.text
    assert scanned.json()["readability"] == "stored_only"


async def test_note_material_reuses_extracted_text_and_is_always_readable(client: AsyncClient):
    slug = await _create_institution()
    _, token = await _teacher(client, slug)
    subject = (await client.post("/api/curriculum/subjects", json={"name": "S"}, headers=_auth(token))).json()

    note = await client.post(
        "/api/curriculum/materials",
        data={"owner_type": "subject", "owner_id": subject["id"], "kind": "note", "title": "Quick note", "body": "Remember: FFT is O(n log n)."},
        headers=_auth(token),
    )
    assert note.status_code == 200, note.text
    assert note.json()["readability"] == "readable"


async def test_publish_cascades_subject_and_assessment_hides_drafts_from_student(client: AsyncClient):
    slug = await _create_institution()
    _, teacher_token = await _teacher(client, slug)
    student_identifier = await _create_user(slug, "student")
    student_token = await _login(client, slug, student_identifier)

    subject = (await client.post("/api/curriculum/subjects", json={"name": "DIP"}, headers=_auth(teacher_token))).json()
    ch1 = (await client.post(f"/api/curriculum/subjects/{subject['id']}/chapters", json={"title": "Ch1"}, headers=_auth(teacher_token))).json()
    await client.post(f"/api/curriculum/subjects/{subject['id']}/chapters", json={"title": "Ch2"}, headers=_auth(teacher_token))  # stays draft
    topic = (await client.post(f"/api/curriculum/subjects/{subject['id']}/topics", json={"title": "Sampling"}, headers=_auth(teacher_token))).json()
    await client.post(f"/api/curriculum/chapters/{ch1['id']}/blocks", json={"block_type": "topic", "topic_id": topic["id"]}, headers=_auth(teacher_token))

    # enroll the student directly via a pool for realism
    async with SessionLocal() as db:
        institution = (await db.execute(select(Institution).where(Institution.slug == slug))).scalar_one()
        pool = Pool(id=uuid.uuid4(), institution_id=institution.id, name="P")
        db.add(pool)
        await db.flush()
        student_row = (await db.execute(select(User).where(User.email == student_identifier))).scalar_one()
        db.add(PoolMember(pool_id=pool.id, user_id=student_row.id))
        await db.commit()
        pool_id = str(pool.id)

    await client.post(f"/api/curriculum/subjects/{subject['id']}/pools/{pool_id}/attach", headers=_auth(teacher_token))

    # subject still draft -> student sees nothing yet
    before = await client.get("/api/curriculum/student/subjects", headers=_auth(student_token))
    assert before.json() == []

    published = await client.post(f"/api/curriculum/chapters/{ch1['id']}/publish", headers=_auth(teacher_token))
    assert published.status_code == 200
    assert published.json()["subject_status"] == "published"

    after = await client.get("/api/curriculum/student/subjects", headers=_auth(student_token))
    assert len(after.json()) == 1

    detail = (await client.get(f"/api/curriculum/student/subjects/{subject['id']}", headers=_auth(student_token))).json()
    assert [c["title"] for c in detail["chapters"]] == ["Ch1"]  # Ch2 (draft) hidden


async def test_pool_edit_does_not_change_enrollment_until_sync(client: AsyncClient):
    slug = await _create_institution()
    _, token = await _teacher(client, slug)
    subject = (await client.post("/api/curriculum/subjects", json={"name": "S"}, headers=_auth(token))).json()

    async with SessionLocal() as db:
        institution = (await db.execute(select(Institution).where(Institution.slug == slug))).scalar_one()
        pool = Pool(id=uuid.uuid4(), institution_id=institution.id, name="P")
        db.add(pool)
        await db.flush()
        pool_id = str(pool.id)
        await db.commit()

    student1 = await _create_user(slug, "student")
    async with SessionLocal() as db:
        s1 = (await db.execute(select(User).where(User.email == student1))).scalar_one()
        db.add(PoolMember(pool_id=uuid.UUID(pool_id), user_id=s1.id))
        await db.commit()

    attach = await client.post(f"/api/curriculum/subjects/{subject['id']}/pools/{pool_id}/attach", headers=_auth(token))
    assert attach.json()["attached"] == 1

    roster = (await client.get(f"/api/curriculum/subjects/{subject['id']}/enrollments", headers=_auth(token))).json()
    assert len(roster) == 1

    # pool gains a new member AFTER attach - enrollment must not move until the banner/sync fires
    student2 = await _create_user(slug, "student")
    async with SessionLocal() as db:
        s2 = (await db.execute(select(User).where(User.email == student2))).scalar_one()
        db.add(PoolMember(pool_id=uuid.UUID(pool_id), user_id=s2.id))
        await db.commit()

    roster_after_pool_edit = (await client.get(f"/api/curriculum/subjects/{subject['id']}/enrollments", headers=_auth(token))).json()
    assert len(roster_after_pool_edit) == 1  # unchanged

    deltas = (await client.get(f"/api/curriculum/subjects/{subject['id']}/pool-deltas", headers=_auth(token))).json()
    assert len(deltas) == 1
    assert deltas[0]["new_member_count"] == 1

    sync = await client.post(f"/api/curriculum/subjects/{subject['id']}/pools/{pool_id}/sync", headers=_auth(token))
    assert sync.json()["added"] == 1

    roster_after_sync = (await client.get(f"/api/curriculum/subjects/{subject['id']}/enrollments", headers=_auth(token))).json()
    assert len(roster_after_sync) == 2

    deltas_after_sync = (await client.get(f"/api/curriculum/subjects/{subject['id']}/pool-deltas", headers=_auth(token))).json()
    assert deltas_after_sync == []


async def test_removed_enrollment_is_archived_not_deleted_and_not_resurrected_by_sync(client: AsyncClient):
    slug = await _create_institution()
    _, token = await _teacher(client, slug)
    subject = (await client.post("/api/curriculum/subjects", json={"name": "S"}, headers=_auth(token))).json()

    async with SessionLocal() as db:
        institution = (await db.execute(select(Institution).where(Institution.slug == slug))).scalar_one()
        pool = Pool(id=uuid.uuid4(), institution_id=institution.id, name="P")
        db.add(pool)
        await db.flush()
        pool_id = str(pool.id)
        await db.commit()

    student = await _create_user(slug, "student")
    async with SessionLocal() as db:
        s = (await db.execute(select(User).where(User.email == student))).scalar_one()
        db.add(PoolMember(pool_id=uuid.UUID(pool_id), user_id=s.id))
        await db.commit()
        student_id = str(s.id)

    await client.post(f"/api/curriculum/subjects/{subject['id']}/pools/{pool_id}/attach", headers=_auth(token))
    removed = await client.delete(f"/api/curriculum/subjects/{subject['id']}/enrollments/{student_id}", headers=_auth(token))
    assert removed.status_code == 200

    roster = (await client.get(f"/api/curriculum/subjects/{subject['id']}/enrollments", headers=_auth(token))).json()
    assert roster == []

    # re-syncing the same pool must NOT resurrect the deliberately-removed student
    sync = await client.post(f"/api/curriculum/subjects/{subject['id']}/pools/{pool_id}/sync", headers=_auth(token))
    assert sync.json()["added"] == 0
    assert (await client.get(f"/api/curriculum/subjects/{subject['id']}/enrollments", headers=_auth(token))).json() == []


# --- access-scoping: a teacher from institution B must never reach institution A's subject -------
async def test_foreign_teacher_cannot_access_subject(client: AsyncClient):
    slug_a = await _create_institution("A")
    slug_b = await _create_institution("B")
    _, token_a = await _teacher(client, slug_a)
    _, token_b = await _teacher(client, slug_b)

    subject = (await client.post("/api/curriculum/subjects", json={"name": "A's subject"}, headers=_auth(token_a))).json()

    res = await client.get(f"/api/curriculum/subjects/{subject['id']}", headers=_auth(token_b))
    assert res.status_code == 404

    listing = await client.get("/api/curriculum/subjects", headers=_auth(token_b))
    assert listing.json() == []


async def test_teacher_pool_listing_is_institution_scoped(client: AsyncClient):
    slug_a = await _create_institution("A")
    slug_b = await _create_institution("B")
    _, token_a = await _teacher(client, slug_a)
    _, token_b = await _teacher(client, slug_b)

    async with SessionLocal() as db:
        institution_a = (await db.execute(select(Institution).where(Institution.slug == slug_a))).scalar_one()
        db.add(Pool(id=uuid.uuid4(), institution_id=institution_a.id, name="A-Pool"))
        await db.commit()

    pools_a = (await client.get("/api/curriculum/pools", headers=_auth(token_a))).json()
    assert [p["name"] for p in pools_a] == ["A-Pool"]

    pools_b = (await client.get("/api/curriculum/pools", headers=_auth(token_b))).json()
    assert pools_b == []


async def test_unenrolled_student_cannot_see_subject(client: AsyncClient):
    slug = await _create_institution()
    _, token = await _teacher(client, slug)
    student_identifier = await _create_user(slug, "student")
    student_token = await _login(client, slug, student_identifier)

    subject = (await client.post("/api/curriculum/subjects", json={"name": "S"}, headers=_auth(token))).json()
    ch = (await client.post(f"/api/curriculum/subjects/{subject['id']}/chapters", json={"title": "Ch1"}, headers=_auth(token))).json()
    await client.post(f"/api/curriculum/chapters/{ch['id']}/publish", headers=_auth(token))

    res = await client.get(f"/api/curriculum/student/subjects/{subject['id']}", headers=_auth(student_token))
    assert res.status_code == 404
