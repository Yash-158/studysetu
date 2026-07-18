"""modules/pools: scope in docs/FEATURE_EXPLANATION.md S10 + docs/ROADMAP.md M2.
Owns its router, service functions, repository queries. Config via app.core.config.settings ONLY.
Emits a timeline event for every user-visible action (RULES: events over state).

Institution-scoping (RULES #10): every pool query is filtered by the CALLER's own
institution_id; a pool belonging to another institution 404s rather than leaking existence.
Enrollment snapshot+delta (S10) is subjects/curriculum territory (M3) - this module only owns
the pool + its membership roster.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Pool, PoolMember, User, get_db, record_event
from app.core.security import require_institution_admin

router = APIRouter(prefix="/api/pools", tags=["pools"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "not_found", "message": "Not found", "hint": "Check the id"})


async def _get_owned_pool(db: AsyncSession, pool_id: uuid.UUID, institution_id: uuid.UUID) -> Pool:
    pool = (
        await db.execute(select(Pool).where(Pool.id == pool_id, Pool.institution_id == institution_id))
    ).scalar_one_or_none()
    if pool is None:
        raise _not_found()
    return pool


def _pool_out(pool: Pool, member_count: int) -> dict:
    return {"id": str(pool.id), "name": pool.name, "member_count": member_count}


class CreatePoolRequest(BaseModel):
    name: str


class AddMembersRequest(BaseModel):
    user_ids: list[uuid.UUID]


@router.get("")
async def list_pools(
    db: AsyncSession = Depends(get_db), admin: User = Depends(require_institution_admin)
) -> list[dict]:
    pools = (
        await db.execute(select(Pool).where(Pool.institution_id == admin.institution_id).order_by(Pool.created_at))
    ).scalars().all()
    out = []
    for pool in pools:
        count = (
            await db.execute(select(PoolMember).where(PoolMember.pool_id == pool.id))
        ).scalars().all()
        out.append(_pool_out(pool, len(count)))
    return out


@router.post("")
async def create_pool(
    body: CreatePoolRequest, db: AsyncSession = Depends(get_db), admin: User = Depends(require_institution_admin)
) -> dict:
    pool = Pool(id=uuid.uuid4(), institution_id=admin.institution_id, name=body.name)
    db.add(pool)
    await db.flush()
    await record_event(db, user_id=admin.id, event_type="pool_created", payload={"pool_id": str(pool.id), "name": pool.name})
    await db.commit()
    return _pool_out(pool, 0)


@router.get("/{pool_id}")
async def get_pool(
    pool_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_institution_admin)
) -> dict:
    pool = await _get_owned_pool(db, pool_id, admin.institution_id)
    members = (
        await db.execute(
            select(User).join(PoolMember, PoolMember.user_id == User.id).where(PoolMember.pool_id == pool.id)
        )
    ).scalars().all()
    return {
        "id": str(pool.id),
        "name": pool.name,
        "members": [
            {"id": str(u.id), "display_name": u.display_name, "role": u.role, "roll_number": u.roll_number,
             "email": u.email, "status": u.status}
            for u in members
        ],
    }


@router.post("/{pool_id}/members")
async def add_members(
    pool_id: uuid.UUID, body: AddMembersRequest, db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_institution_admin),
) -> dict:
    pool = await _get_owned_pool(db, pool_id, admin.institution_id)

    valid_ids = set(
        (
            await db.execute(
                select(User.id).where(User.id.in_(body.user_ids), User.institution_id == admin.institution_id)
            )
        ).scalars().all()
    )
    if len(valid_ids) != len(set(body.user_ids)):
        raise HTTPException(
            status_code=400,
            detail={"code": "bad_request", "message": "One or more users are not in your institution", "hint": ""},
        )

    for user_id in valid_ids:
        await db.execute(
            pg_insert(PoolMember).values(pool_id=pool.id, user_id=user_id).on_conflict_do_nothing()
        )
        await record_event(db, user_id=user_id, event_type="pool_member_added", payload={"pool_id": str(pool.id)})
    await db.commit()
    return {"added": len(valid_ids)}


@router.delete("/{pool_id}/members/{user_id}")
async def remove_member(
    pool_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_institution_admin),
) -> dict:
    pool = await _get_owned_pool(db, pool_id, admin.institution_id)
    member = (
        await db.execute(
            select(PoolMember).where(PoolMember.pool_id == pool.id, PoolMember.user_id == user_id)
        )
    ).scalar_one_or_none()
    if member is None:
        raise _not_found()
    await db.delete(member)
    await record_event(db, user_id=user_id, event_type="pool_member_removed", payload={"pool_id": str(pool.id)})
    await db.commit()
    return {"removed": True}
