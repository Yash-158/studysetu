"""StudySetu demo seeder (idempotent, <10s).
M1 scope: institution GLS-demo (slug gls-demo) + 3 users (admin, teacher Anvi, student Yash
21BCE001), each `invited` with a fixed demo activation code so e2e/auth_roles.spec.ts and manual
runbooks can activate them deterministically.
M2 scope: pool CSE-3A + 8 more students (21BCE002-21BCE009), all fixed-code invited; Yash plus
the 8 new students land in CSE-3A so the pool has a full, real cohort for M3's subject-attach demo.
M3 scope: Anvi builds+publishes Digital Image Processing (DIP): 2 chapters, 5 topics, one
Transforms->Frequency Filtering prerequisite edge, one assessment placeholder block, one real PDF
material (written through StorageProvider + pypdf-extracted, not faked), CSE-3A pool attached so
Yash + the 8 students land in subject_enrollments - matching the ROADMAP M3 GATE exactly."""
import asyncio
import io
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from sqlalchemy import select  # noqa: E402

from app.core.db import (  # noqa: E402
    Assessment,
    Chapter,
    ChapterBlock,
    Institution,
    Material,
    Pool,
    PoolMember,
    SessionLocal,
    Subject,
    SubjectEnrollment,
    SubjectStaff,
    Topic,
    TopicEdge,
    Upload,
    User,
)
from app.core.security import hash_secret  # noqa: E402
from app.storage.local import LocalStorageProvider  # noqa: E402

INSTITUTION_SLUG = "gls-demo"
POOL_NAME = "CSE-3A"
SUBJECT_CODE = "DIP"
DEMO_USERS = [
    {
        "role": "admin",
        "display_name": "Admin",
        "email": "admin@gls-demo.test",
        "roll_number": None,
        "activation_code": "11111111",
    },
    {
        "role": "teacher",
        "display_name": "Anvi",
        "email": "anvi@gls-demo.test",
        "roll_number": None,
        "activation_code": "22222222",
    },
    {
        "role": "student",
        "display_name": "Yash",
        "email": "yash@gls-demo.test",
        "roll_number": "21BCE001",
        "activation_code": "33333333",
    },
]
# M2: 8 more CSE-3A students, roll numbers 21BCE002-009, fixed activation codes 40000002-40000009.
POOL_STUDENTS = [
    {
        "role": "student",
        "display_name": f"Student {n}",
        "email": f"student{n}@gls-demo.test",
        "roll_number": f"21BCE{n:03d}",
        "activation_code": f"4000000{n - 1}",
    }
    for n in range(2, 10)
]

_storage = LocalStorageProvider()


def _build_pdf(text: bytes) -> bytes:
    """Hand-built minimal single-page PDF (valid xref/trailer, no extra PDF-writer dependency) -
    same technique as tests/test_curriculum.py, kept separate since seed scripts don't import tests."""
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


DIP_SYLLABUS_TEXT = (
    "Digital Image Processing syllabus: sampling, quantization, transforms, "
    "histograms, and frequency domain filtering."
)


async def _seed_dip_subject(db, institution: Institution) -> None:
    existing = (
        await db.execute(select(Subject).where(Subject.institution_id == institution.id, Subject.code == SUBJECT_CODE))
    ).scalar_one_or_none()
    if existing is not None:
        print(f"subject exists: Digital Image Processing ({SUBJECT_CODE})")
        return

    anvi = (
        await db.execute(select(User).where(User.institution_id == institution.id, User.email == "anvi@gls-demo.test"))
    ).scalar_one()
    pool = (await db.execute(select(Pool).where(Pool.institution_id == institution.id, Pool.name == POOL_NAME))).scalar_one()

    subject = Subject(
        id=uuid.uuid4(), institution_id=institution.id, created_by=anvi.id,
        name="Digital Image Processing", code=SUBJECT_CODE, term="Sem 5", status="draft",
    )
    db.add(subject)
    await db.flush()
    db.add(SubjectStaff(subject_id=subject.id, user_id=anvi.id))

    ch1 = Chapter(id=uuid.uuid4(), subject_id=subject.id, title="Foundations", position=0, status="draft")
    ch2 = Chapter(id=uuid.uuid4(), subject_id=subject.id, title="Frequency Domain", position=1, status="draft")
    db.add(ch1)
    db.add(ch2)
    await db.flush()

    topic_titles = ["Sampling", "Quantization", "Transforms", "Histograms", "Frequency Filtering"]
    topics = {title: Topic(id=uuid.uuid4(), kind="subject", subject_id=subject.id, title=title, description="") for title in topic_titles}
    for t in topics.values():
        db.add(t)
    await db.flush()

    for i, title in enumerate(["Sampling", "Quantization", "Transforms"]):
        db.add(ChapterBlock(id=uuid.uuid4(), chapter_id=ch1.id, position=i, block_type="topic", topic_id=topics[title].id))
    for i, title in enumerate(["Histograms", "Frequency Filtering"]):
        db.add(ChapterBlock(id=uuid.uuid4(), chapter_id=ch2.id, position=i, block_type="topic", topic_id=topics[title].id))

    assessment = Assessment(
        id=uuid.uuid4(), subject_id=subject.id, created_by=anvi.id, title="Unit Check 1",
        gating="recommended", feedback="end", status="draft",
    )
    db.add(assessment)
    await db.flush()
    db.add(ChapterBlock(id=uuid.uuid4(), chapter_id=ch2.id, position=2, block_type="assessment", assessment_id=assessment.id))

    db.add(TopicEdge(src_topic_id=topics["Transforms"].id, dst_topic_id=topics["Frequency Filtering"].id, origin="teacher"))

    pdf_bytes = _build_pdf(DIP_SYLLABUS_TEXT.encode())
    storage_key = await _storage.save(pdf_bytes, "dip-syllabus.pdf", purpose="material")
    material = Material(
        id=uuid.uuid4(), owner_type="subject", owner_id=subject.id, kind="pdf", title="DIP Syllabus",
        url=None, upload_id=None, extracted_text=DIP_SYLLABUS_TEXT, readability="readable", created_by=anvi.id,
    )
    db.add(material)
    await db.flush()
    upload = Upload(
        id=uuid.uuid4(), user_id=anvi.id, purpose="material", ref_id=material.id, provider="local",
        storage_key=storage_key, mime="application/pdf", size_bytes=len(pdf_bytes), expires_at=None,
    )
    db.add(upload)
    await db.flush()
    material.upload_id = upload.id

    # Publish both chapters (mirrors modules/curriculum.py's publish cascade: subject draft->published
    # on first published chapter, assessment blocks inside publish alongside their chapter).
    ch1.status = "published"
    ch2.status = "published"
    assessment.status = "published"
    subject.status = "published"

    # Pool attach = snapshot (S10): copy CSE-3A's current membership into subject_enrollments.
    member_ids = (await db.execute(select(PoolMember.user_id).where(PoolMember.pool_id == pool.id))).scalars().all()
    for user_id in member_ids:
        db.add(SubjectEnrollment(subject_id=subject.id, user_id=user_id, source_pool_id=pool.id, status="active"))

    print(
        f"created subject: Digital Image Processing ({SUBJECT_CODE}) - published, 2 chapters, "
        f"5 topics, 1 prereq edge, 1 assessment block, 1 PDF material, {POOL_NAME} attached ({len(member_ids)} students)"
    )


async def seed() -> None:
    async with SessionLocal() as db:
        institution = (
            await db.execute(select(Institution).where(Institution.slug == INSTITUTION_SLUG))
        ).scalar_one_or_none()
        if institution is None:
            institution = Institution(id=uuid.uuid4(), name="GLS Demo", slug=INSTITUTION_SLUG, is_personal=False)
            db.add(institution)
            await db.flush()
            print(f"created institution: {INSTITUTION_SLUG}")
        else:
            print(f"institution exists: {INSTITUTION_SLUG}")

        pool_students_rolls = {spec["roll_number"] for spec in POOL_STUDENTS} | {"21BCE001"}

        for spec in DEMO_USERS + POOL_STUDENTS:
            existing = (
                await db.execute(
                    select(User).where(User.institution_id == institution.id, User.email == spec["email"])
                )
            ).scalar_one_or_none()
            if existing is not None:
                print(f"  skip (exists): {spec['role']} {spec['email']}")
                continue
            db.add(
                User(
                    id=uuid.uuid4(),
                    institution_id=institution.id,
                    role=spec["role"],
                    display_name=spec["display_name"],
                    roll_number=spec["roll_number"],
                    email=spec["email"],
                    password_hash=None,
                    status="invited",
                    activation_code_hash=hash_secret(spec["activation_code"]),
                    locale="en",
                )
            )
            print(f"  created: {spec['role']} {spec['email']} (activation code: {spec['activation_code']})")

        await db.flush()

        pool = (
            await db.execute(
                select(Pool).where(Pool.institution_id == institution.id, Pool.name == POOL_NAME)
            )
        ).scalar_one_or_none()
        if pool is None:
            pool = Pool(id=uuid.uuid4(), institution_id=institution.id, name=POOL_NAME)
            db.add(pool)
            await db.flush()
            print(f"created pool: {POOL_NAME}")
        else:
            print(f"pool exists: {POOL_NAME}")

        pool_students = (
            await db.execute(
                select(User).where(User.institution_id == institution.id, User.roll_number.in_(pool_students_rolls))
            )
        ).scalars().all()
        existing_members = {
            m
            for (m,) in (
                await db.execute(select(PoolMember.user_id).where(PoolMember.pool_id == pool.id))
            ).all()
        }
        for student in pool_students:
            if student.id in existing_members:
                continue
            db.add(PoolMember(pool_id=pool.id, user_id=student.id))
            print(f"  added to {POOL_NAME}: {student.roll_number}")

        await db.flush()

        await _seed_dip_subject(db, institution)

        await db.commit()
    print(f"Seed complete. Institution slug: {INSTITUTION_SLUG}")


if __name__ == "__main__":
    asyncio.run(seed())
