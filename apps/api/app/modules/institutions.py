"""modules/institutions: scope in docs/FEATURE_EXPLANATION.md S2/S6/S11 + docs/ROADMAP.md M2.
Owns its router, service functions, repository queries. Config via app.core.config.settings ONLY.
Emits a timeline event for every user-visible action (RULES: events over state).

Institution-scoping (RULES #10): every query here is filtered by the CALLER's own
institution_id (from their JWT/current_user), never by a client-supplied institution id.
There is no route that lets one institution read another's rows.
"""
from __future__ import annotations

import csv
import io
import re
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import Institution, User, get_db, record_event
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_activation_code,
    hash_secret,
    require_institution_admin,
)

router = APIRouter(prefix="/api/institutions", tags=["institutions"])

_VALID_ROLES = {"teacher", "student"}


def _bad_request(message: str, hint: str) -> HTTPException:
    return HTTPException(status_code=400, detail={"code": "bad_request", "message": message, "hint": hint})


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "not_found", "message": "Not found", "hint": "Check the id"},
    )


def _user_out(user: User) -> dict:
    return {
        "id": str(user.id),
        "role": user.role,
        "display_name": user.display_name,
        "roll_number": user.roll_number,
        "email": user.email,
        "status": user.status,
    }


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "institution"
    return f"{base}-{secrets.token_hex(3)}"


async def _issue_invite(
    db: AsyncSession, *, institution_id: uuid.UUID, role: str, display_name: str,
    roll_number: str | None, email: str | None, invited_by: uuid.UUID,
) -> tuple[User, str]:
    code = generate_activation_code()
    user = User(
        id=uuid.uuid4(),
        institution_id=institution_id,
        role=role,
        display_name=display_name,
        roll_number=roll_number,
        email=email,
        password_hash=None,
        status="invited",
        activation_code_hash=hash_secret(code),
        locale=settings.get("locales", "default", default="en"),
        issued_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    await record_event(db, user_id=user.id, event_type="user_invited", payload={"invited_by": str(invited_by)})
    return user, code


class SelfServeRequest(BaseModel):
    institution_name: str
    display_name: str
    email: str
    password: str


class InviteUserRequest(BaseModel):
    role: str
    display_name: str
    roll_number: str | None = None
    email: str | None = None


class CsvImportRequest(BaseModel):
    csv_text: str


@router.post("/self-serve")
async def self_serve_signup(body: SelfServeRequest, db: AsyncSession = Depends(get_db)) -> dict:
    if not settings.get("features", "self_serve_teacher_tier", default=False):
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Not found", "hint": ""},
        )
    min_length = settings.get("auth", "password", "min_length", default=8)
    if len(body.password) < min_length:
        raise _bad_request("Password too short", f"Use at least {min_length} characters")

    institution = Institution(
        id=uuid.uuid4(), name=body.institution_name, slug=_slugify(body.institution_name), is_personal=True
    )
    db.add(institution)
    await db.flush()

    user = User(
        id=uuid.uuid4(),
        institution_id=institution.id,
        role="teacher",
        display_name=body.display_name,
        roll_number=None,
        email=body.email,
        password_hash=hash_secret(body.password),
        status="active",
        activation_code_hash=None,
        locale=settings.get("locales", "default", default="en"),
        issued_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    await record_event(db, user_id=user.id, event_type="self_serve_signup", payload={"institution_slug": institution.slug})
    await db.commit()

    return {
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
        "user": {**_user_out(user), "institution_id": str(institution.id)},
        "institution": {"slug": institution.slug, "name": institution.name},
    }


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db), admin: User = Depends(require_institution_admin)
) -> list[dict]:
    users = (
        await db.execute(
            select(User).where(User.institution_id == admin.institution_id).order_by(User.created_at)
        )
    ).scalars().all()
    return [_user_out(u) for u in users]


@router.post("/users")
async def invite_user(
    body: InviteUserRequest, db: AsyncSession = Depends(get_db), admin: User = Depends(require_institution_admin)
) -> dict:
    role = body.role.strip().lower()
    if role not in _VALID_ROLES:
        raise _bad_request("Invalid role", f"role must be one of: {', '.join(sorted(_VALID_ROLES))}")
    if not body.roll_number and not body.email:
        raise _bad_request("Missing identifier", "Provide a roll_number or an email")

    user, code = await _issue_invite(
        db,
        institution_id=admin.institution_id,
        role=role,
        display_name=body.display_name,
        roll_number=body.roll_number,
        email=body.email,
        invited_by=admin.id,
    )
    await db.commit()
    return {"user": _user_out(user), "activation_code": code}


@router.post("/users/csv")
async def import_users_csv(
    body: CsvImportRequest, db: AsyncSession = Depends(get_db), admin: User = Depends(require_institution_admin)
) -> dict:
    reader = csv.DictReader(io.StringIO(body.csv_text))
    if reader.fieldnames is None or set(reader.fieldnames) < {"display_name", "role"}:
        raise _bad_request(
            "Invalid CSV", "Header row must include at least: display_name,role,roll_number,email"
        )

    rows = list(reader)
    if not rows:
        raise _bad_request("Empty CSV", "Provide at least one student/teacher row")

    existing = (
        await db.execute(select(User.roll_number, User.email).where(User.institution_id == admin.institution_id))
    ).all()
    existing_rolls = {r for r, _ in existing if r}
    existing_emails = {e.lower() for _, e in existing if e}

    errors: list[str] = []
    seen_rolls: set[str] = set()
    seen_emails: set[str] = set()
    for i, row in enumerate(rows, start=2):  # header is row 1
        role = (row.get("role") or "").strip().lower()
        display_name = (row.get("display_name") or "").strip()
        roll_number = (row.get("roll_number") or "").strip() or None
        email = (row.get("email") or "").strip() or None

        if not display_name:
            errors.append(f"row {i}: missing display_name")
        if role not in _VALID_ROLES:
            errors.append(f"row {i}: invalid role '{role}'")
        if not roll_number and not email:
            errors.append(f"row {i}: needs a roll_number or an email")
        if roll_number and (roll_number in existing_rolls or roll_number in seen_rolls):
            errors.append(f"row {i}: roll_number '{roll_number}' already exists")
        if email and (email.lower() in existing_emails or email.lower() in seen_emails):
            errors.append(f"row {i}: email '{email}' already exists")
        if roll_number:
            seen_rolls.add(roll_number)
        if email:
            seen_emails.add(email.lower())

    if errors:
        raise _bad_request("CSV validation failed", "; ".join(errors))

    created = []
    for row in rows:
        user, code = await _issue_invite(
            db,
            institution_id=admin.institution_id,
            role=row["role"].strip().lower(),
            display_name=row["display_name"].strip(),
            roll_number=(row.get("roll_number") or "").strip() or None,
            email=(row.get("email") or "").strip() or None,
            invited_by=admin.id,
        )
        created.append({"user": _user_out(user), "activation_code": code})
    await db.commit()
    return {"created": created}


@router.post("/users/{user_id}/reissue-code")
async def reissue_code(
    user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_institution_admin)
) -> dict:
    user = (
        await db.execute(select(User).where(User.id == user_id, User.institution_id == admin.institution_id))
    ).scalar_one_or_none()
    if user is None:
        raise _not_found()

    code = generate_activation_code()
    user.activation_code_hash = hash_secret(code)
    user.issued_at = datetime.now(timezone.utc)
    user.status = "invited"
    await record_event(db, user_id=user.id, event_type="activation_code_reissued", payload={"issued_by": str(admin.id)})
    await db.commit()
    return {"activation_code": code}
