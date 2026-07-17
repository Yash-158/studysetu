"""modules/auth: scope in docs/FEATURE_EXPLANATION.md S6 + docs/ROADMAP.md M1.
Owns its router, service functions, repository queries. Config via app.core.config.settings ONLY.
Emits a timeline event for every user-visible action (RULES: events over state).

Activation codes are teacher/seed-issued out of band in M1 (no email-sending code exists yet -
see config/email.yaml). Issuance UX itself is M2's "activation issuance" scope.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import Institution, User, get_db, record_event
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_secret,
    verify_secret,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _bad_request(message: str, hint: str) -> HTTPException:
    return HTTPException(status_code=400, detail={"code": "bad_request", "message": message, "hint": hint})


async def _find_user(db: AsyncSession, institution_slug: str, identifier: str) -> User | None:
    institution = (
        await db.execute(select(Institution).where(Institution.slug == institution_slug))
    ).scalar_one_or_none()
    if institution is None:
        return None
    return (
        await db.execute(
            select(User).where(
                User.institution_id == institution.id,
                or_(User.roll_number == identifier, User.email == identifier),
            )
        )
    ).scalar_one_or_none()


def _user_out(user: User) -> dict:
    return {
        "id": str(user.id),
        "role": user.role,
        "display_name": user.display_name,
        "roll_number": user.roll_number,
        "email": user.email,
        "institution_id": str(user.institution_id),
        "locale": user.locale,
    }


class ActivateRequest(BaseModel):
    institution_slug: str
    identifier: str
    activation_code: str
    new_password: str


class LoginRequest(BaseModel):
    institution_slug: str
    identifier: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str


@router.post("/activate")
async def activate(body: ActivateRequest, db: AsyncSession = Depends(get_db)) -> dict:
    generic_error = _bad_request(
        "Invalid activation details", "Check the institution code, identifier, and activation code"
    )
    user = await _find_user(db, body.institution_slug, body.identifier)
    if user is None or user.status != "invited" or not verify_secret(body.activation_code, user.activation_code_hash):
        raise generic_error

    # ponytail: TTL measured from created_at (no issued_at column exists yet). Good enough while
    # activation codes are only ever set at account-creation time; M2's reissue flow should add a
    # dedicated issued_at column once codes can be reissued independently of creation.
    ttl_hours = settings.get("auth", "activation", "code_ttl_hours", default=72)
    if datetime.now(timezone.utc) - user.created_at > timedelta(hours=ttl_hours):
        raise generic_error

    min_length = settings.get("auth", "password", "min_length", default=8)
    if len(body.new_password) < min_length:
        raise _bad_request(
            "Password too short", f"Use at least {min_length} characters"
        )

    user.password_hash = hash_secret(body.new_password)
    user.activation_code_hash = None
    user.status = "active"
    await record_event(db, user_id=user.id, event_type="account_activated")
    await db.commit()
    return {"message": "activated", "user": _user_out(user)}


@router.post("/login", response_model=None)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> dict:
    invalid = HTTPException(
        status_code=401,
        detail={"code": "invalid_credentials", "message": "Invalid credentials", "hint": "Check your identifier and password"},
    )
    user = await _find_user(db, body.institution_slug, body.identifier)
    if user is None or user.status != "active" or not verify_secret(body.password, user.password_hash):
        raise invalid

    anomaly_policy = settings.get("auth", "anomaly", "concurrent_session_flag", default="warn")
    if anomaly_policy != "off" and user.last_login_at is not None:
        access_window = timedelta(minutes=settings.get("auth", "jwt", "access_ttl_minutes", default=30))
        if datetime.now(timezone.utc) - user.last_login_at < access_window:
            await record_event(
                db, user_id=user.id, event_type="login_anomaly", payload={"reason": "concurrent_session"}
            )

    user.last_login_at = datetime.now(timezone.utc)
    await record_event(db, user_id=user.id, event_type="login_succeeded")
    await db.commit()

    return {
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
        "user": _user_out(user),
    }


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    claims = decode_token(body.refresh_token, expected_type="refresh")
    user = (await db.execute(select(User).where(User.id == uuid.UUID(claims["sub"])))).scalar_one_or_none()
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Account not active", "hint": "Log in again"},
        )
    return TokenPair(access_token=create_access_token(user), refresh_token=create_refresh_token(user))


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> dict:
    return _user_out(user)
