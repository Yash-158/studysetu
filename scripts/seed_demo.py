"""StudySetu demo seeder (idempotent, <10s).
M1 scope: institution GLS-demo (slug gls-demo) + 3 users (admin, teacher Anvi, student Yash
21BCE001), each `invited` with a fixed demo activation code so e2e/auth_roles.spec.ts and manual
runbooks can activate them deterministically.
M2 scope: pool CSE-3A + 8 more students (21BCE002-21BCE009), all fixed-code invited; Yash plus
the 8 new students land in CSE-3A so the pool has a full, real cohort for M3's subject-attach demo."""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from sqlalchemy import select  # noqa: E402

from app.core.db import Institution, Pool, PoolMember, SessionLocal, User  # noqa: E402
from app.core.security import hash_secret  # noqa: E402

INSTITUTION_SLUG = "gls-demo"
POOL_NAME = "CSE-3A"
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

        await db.commit()
    print(f"Seed complete. Institution slug: {INSTITUTION_SLUG}")


if __name__ == "__main__":
    asyncio.run(seed())
