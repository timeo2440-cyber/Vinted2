from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, ActivityLog, User
from models import LogOut
from auth_deps import get_current_user

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=list[LogOut])
async def list_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    level: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    offset = (page - 1) * per_page
    # Show user's own logs + global logs (user_id IS NULL)
    from sqlalchemy import or_
    query = (
        select(ActivityLog)
        .where(or_(ActivityLog.user_id == user.id, ActivityLog.user_id == None))
        .order_by(ActivityLog.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    if level:
        query = query.where(ActivityLog.level == level)
    result = await db.execute(query)
    return result.scalars().all()


@router.delete("", status_code=204)
async def clear_logs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await db.execute(delete(ActivityLog).where(ActivityLog.user_id == user.id))
    await db.commit()
