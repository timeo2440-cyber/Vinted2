from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, ActivityLog
from models import LogOut

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=list[LogOut])
async def list_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    level: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * per_page
    query = select(ActivityLog).order_by(ActivityLog.created_at.desc()).offset(offset).limit(per_page)
    if level:
        query = query.where(ActivityLog.level == level)
    result = await db.execute(query)
    return result.scalars().all()


@router.delete("", status_code=204)
async def clear_logs(db: AsyncSession = Depends(get_db)):
    await db.execute(delete(ActivityLog))
    await db.commit()
