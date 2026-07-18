"""JWT issue/verify, password + activation-code hashing, role dependency guards.
Contract: require_role('teacher') dependency used by EVERY non-student route (RULES.md #12)."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import Institution, User, get_db

_JWT_ALGORITHM = settings.get("auth", "jwt", "algorithm", default="HS256")
_ACCESS_TTL = timedelta(minutes=settings.get("auth", "jwt", "access_ttl_minutes", default=30))
_REFRESH_TTL = timedelta(days=settings.get("auth", "jwt", "refresh_ttl_days", default=30))

bearer_scheme = HTTPBearer(auto_error=False)


def _auth_error(message: str, hint: str) -> HTTPException:
    return HTTPException(status_code=401, detail={"code": "unauthorized", "message": message, "hint": hint})


def hash_secret(value: str) -> str:
    return bcrypt.hashpw(value.encode(), bcrypt.gensalt()).decode()


def verify_secret(value: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    return bcrypt.checkpw(value.encode(), hashed.encode())


def generate_activation_code() -> str:
    length = settings.get("auth", "activation", "code_length", default=8)
    return "".join(secrets.choice("0123456789") for _ in range(length))


def _issue_token(user: User, token_type: str, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user.id),
        "role": user.role,
        "institution_id": str(user.institution_id),
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=_JWT_ALGORITHM)


def create_access_token(user: User) -> str:
    return _issue_token(user, "access", _ACCESS_TTL)


def create_refresh_token(user: User) -> str:
    return _issue_token(user, "refresh", _REFRESH_TTL)


def decode_token(token: str, expected_type: str) -> dict:
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[_JWT_ALGORITHM])
    except JWTError as exc:
        raise _auth_error("Invalid or expired token", "Log in again to get a fresh token") from exc
    if claims.get("type") != expected_type:
        raise _auth_error("Wrong token type", f"Expected a {expected_type} token")
    return claims


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None:
        raise _auth_error("Missing credentials", "Include an Authorization: Bearer header")
    claims = decode_token(creds.credentials, expected_type="access")
    user = (await db.execute(select(User).where(User.id == uuid.UUID(claims["sub"])))).scalar_one_or_none()
    if user is None or user.status != "active":
        raise _auth_error("Account not active", "Contact your institution admin")
    return user


def require_role(*roles: str):
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "forbidden",
                    "message": "Your role cannot access this route",
                    "hint": f"Requires one of: {', '.join(roles)}",
                },
            )
        return user

    return dependency


async def require_institution_admin(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> User:
    """Institution-admin capability: real admins, plus a self-serve teacher acting as the sole
    admin-teacher of their own personal institution (FEATURE_EXPLANATION S11: "one admin-teacher").
    No new role added - a teacher only gets this on an is_personal institution, never another's."""
    if user.role == "admin":
        return user
    if user.role == "teacher":
        institution = (
            await db.execute(select(Institution).where(Institution.id == user.institution_id))
        ).scalar_one_or_none()
        if institution is not None and institution.is_personal:
            return user
    raise HTTPException(
        status_code=403,
        detail={
            "code": "forbidden",
            "message": "Your role cannot access this route",
            "hint": "Requires institution admin capability",
        },
    )
