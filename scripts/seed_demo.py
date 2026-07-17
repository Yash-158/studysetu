"""StudySetu demo seeder (idempotent, <10s).
M1 scope: institution GLS-demo (slug gls-demo) + 3 users (admin, teacher Anvi, student Yash
21BCE001), each `invited` with a fixed demo activation code so e2e/auth_roles.spec.ts and manual
runbooks can activate them deterministically. Pool CSE-3A, subject DIP, item banks etc. land as
their milestones do (M2/M3)."""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from sqlalchemy import select  # noqa: E402

from app.core.db import Institution, SessionLocal, User  # noqa: E402
from app.core.security import hash_secret  # noqa: E402

INSTITUTION_SLUG = "gls-demo"
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

        for spec in DEMO_USERS:
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

        await db.commit()
    print(f"Seed complete. Institution slug: {INSTITUTION_SLUG}")


if __name__ == "__main__":
    asyncio.run(seed())
