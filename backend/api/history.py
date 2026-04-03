from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, Purchase, SeenItem, User
from models import PurchaseOut
from auth_deps import get_current_user

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/purchases", response_model=list[PurchaseOut])
async def list_purchases(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    offset = (page - 1) * per_page
    result = await db.execute(
        select(Purchase)
        .where(Purchase.user_id == user.id)
        .order_by(Purchase.attempted_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    return result.scalars().all()


@router.get("/seen-items")
async def list_seen_items(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    offset = (page - 1) * per_page
    result = await db.execute(
        select(SeenItem)
        .order_by(SeenItem.first_seen_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    items = result.scalars().all()
    return [
        {
            "id": i.vinted_id,
            "title": i.title,
            "price": i.price,
            "brand": i.brand,
            "size": i.size,
            "condition": i.condition,
            "photo_url": i.photo_url,
            "item_url": i.item_url,
            "country_code": i.country_code,
            "first_seen_at": i.first_seen_at,
        }
        for i in items
    ]


@router.delete("/seen-items", status_code=204)
async def clear_seen_items(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from sqlalchemy import delete
    await db.execute(delete(SeenItem))
    await db.commit()
