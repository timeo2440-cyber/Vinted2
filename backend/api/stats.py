from fastapi import APIRouter, Depends
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
from database import get_db, SeenItem, Purchase

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_1h = now - timedelta(hours=1)

    total_seen = (await db.execute(select(sa_func.count(SeenItem.id)))).scalar() or 0
    total_purchases = (await db.execute(select(sa_func.count(Purchase.id)))).scalar() or 0
    successful = (await db.execute(
        select(sa_func.count(Purchase.id)).where(Purchase.status == "success")
    )).scalar() or 0
    failed = (await db.execute(
        select(sa_func.count(Purchase.id)).where(Purchase.status == "failed")
    )).scalar() or 0

    total_spend_row = await db.execute(
        select(sa_func.sum(Purchase.price)).where(Purchase.status == "success")
    )
    total_spend = total_spend_row.scalar() or 0.0

    spend_24h_row = await db.execute(
        select(sa_func.sum(Purchase.price)).where(
            Purchase.status == "success",
            Purchase.attempted_at >= cutoff_24h,
        )
    )
    spend_24h = spend_24h_row.scalar() or 0.0

    items_1h_row = await db.execute(
        select(sa_func.count(SeenItem.id)).where(SeenItem.first_seen_at >= cutoff_1h)
    )
    items_1h = items_1h_row.scalar() or 0

    return {
        "total_seen": total_seen,
        "total_purchases": total_purchases,
        "successful_purchases": successful,
        "failed_purchases": failed,
        "total_spend": round(float(total_spend), 2),
        "spend_24h": round(float(spend_24h), 2),
        "items_per_hour": items_1h,
    }


@router.get("/timeline")
async def get_timeline(db: AsyncSession = Depends(get_db)):
    """Return item counts per hour for the last 24 hours."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(SeenItem.first_seen_at).where(
            SeenItem.first_seen_at >= now - timedelta(hours=24)
        )
    )
    timestamps = [row for row in result.scalars()]

    # Bucket into hours
    buckets: dict[int, int] = {}
    for ts in timestamps:
        if ts:
            hour = ts.replace(minute=0, second=0, microsecond=0)
            hour_ts = int(hour.timestamp()) if hasattr(hour, 'timestamp') else 0
            buckets[hour_ts] = buckets.get(hour_ts, 0) + 1

    # Fill missing hours with 0
    timeline = []
    for i in range(23, -1, -1):
        hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=i)
        ts = int(hour.timestamp())
        timeline.append({"hour": hour.strftime("%H:%M"), "ts": ts, "count": buckets.get(ts, 0)})

    return {"timeline": timeline}
