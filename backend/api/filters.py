import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, Filter, SeenItem, User
from models import FilterCreate, FilterUpdate, FilterOut
from bot.filter_engine import FilterEngine
from auth_deps import get_current_user, check_plan_limit

router = APIRouter(prefix="/api/filters", tags=["filters"])
_engine = FilterEngine()


async def _replay_filter_on_seen_items(f: Filter, user_id: int) -> None:
    """
    After a filter is created/updated, immediately replay it against the last
    500 seen items and send item_match WS events for anything that matches.
    This fills the feed instantly instead of waiting for the next poll cycle.
    """
    from ws.manager import ws_manager

    async with __import__('database').AsyncSessionLocal() as db:
        result = await db.execute(
            select(SeenItem).order_by(SeenItem.first_seen_at.desc()).limit(500)
        )
        items = result.scalars().all()

    matched = 0
    for item in items:
        item_dict = {
            "id": item.vinted_id,
            "title": item.title,
            "price": item.price,
            "brand": item.brand,
            "brand_id": item.brand_id,
            "size": item.size,
            "size_id": item.size_id,
            "condition": item.condition,
            "condition_code": getattr(item, "condition_code", None),
            "photo_url": item.photo_url,
            "item_url": item.item_url,
            "country_code": item.country_code,
        }
        if _engine.match_item(item_dict, f):
            await ws_manager.broadcast_item_match(
                item_dict, f.id, f.name, user_id=user_id
            )
            matched += 1
            if matched >= 50:   # max 50 retroactive matches to not spam the feed
                break



def _serialize_filter(f: Filter) -> FilterOut:
    def parse_json(val):
        if val is None:
            return None
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return None
        return val

    return FilterOut(
        id=f.id,
        name=f.name,
        enabled=f.enabled,
        auto_buy=f.auto_buy,
        max_budget=f.max_budget,
        keywords=f.keywords,
        category_ids=parse_json(f.category_ids),
        brand_ids=parse_json(f.brand_ids),
        size_ids=parse_json(f.size_ids),
        conditions=parse_json(f.conditions),
        price_min=f.price_min,
        price_max=f.price_max,
        country_codes=parse_json(f.country_codes),
        created_at=f.created_at,
        updated_at=f.updated_at,
    )


def _apply_filter_data(f: Filter, data: dict) -> None:
    for field in ["name", "enabled", "auto_buy", "max_budget", "keywords", "price_min", "price_max"]:
        if field in data and data[field] is not None:
            setattr(f, field, data[field])

    for list_field in ["category_ids", "brand_ids", "size_ids", "conditions", "country_codes"]:
        if list_field in data:
            val = data[list_field]
            setattr(f, list_field, json.dumps(val) if val is not None else None)


@router.get("", response_model=list[FilterOut])
async def list_filters(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Filter).where(Filter.user_id == user.id).order_by(Filter.created_at)
    )
    return [_serialize_filter(f) for f in result.scalars()]


@router.post("", response_model=FilterOut, status_code=201)
async def create_filter(
    payload: FilterCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Check plan limits
    count_result = await db.execute(
        select(Filter).where(Filter.user_id == user.id)
    )
    current_count = len(count_result.scalars().all())
    check_plan_limit(user, "filters", current_count)

    # Check auto_buy permission
    if payload.auto_buy:
        from database import PLAN_LIMITS
        if not PLAN_LIMITS.get(user.plan, {}).get("auto_buy", False):
            raise HTTPException(403, "L'achat automatique nécessite le plan Pro ou supérieur")

    f = Filter(
        user_id=user.id,
        name=payload.name,
        enabled=payload.enabled,
        auto_buy=payload.auto_buy,
        max_budget=payload.max_budget,
        keywords=payload.keywords,
        price_min=payload.price_min,
        price_max=payload.price_max,
    )
    for list_field in ["category_ids", "brand_ids", "size_ids", "conditions", "country_codes"]:
        val = getattr(payload, list_field)
        setattr(f, list_field, json.dumps(val) if val is not None else None)
    db.add(f)
    await db.commit()
    await db.refresh(f)

    # Replay immediately on already-seen items so the feed isn't empty
    if f.enabled:
        asyncio.create_task(_replay_filter_on_seen_items(f, user.id))

    return _serialize_filter(f)


@router.get("/{filter_id}", response_model=FilterOut)
async def get_filter(
    filter_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    f = await db.get(Filter, filter_id)
    if not f or f.user_id != user.id:
        raise HTTPException(404, "Filtre introuvable")
    return _serialize_filter(f)


@router.put("/{filter_id}", response_model=FilterOut)
async def replace_filter(
    filter_id: int,
    payload: FilterCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    f = await db.get(Filter, filter_id)
    if not f or f.user_id != user.id:
        raise HTTPException(404, "Filtre introuvable")
    if payload.auto_buy:
        from database import PLAN_LIMITS
        if not PLAN_LIMITS.get(user.plan, {}).get("auto_buy", False):
            raise HTTPException(403, "L'achat automatique nécessite le plan Pro ou supérieur")
    _apply_filter_data(f, payload.model_dump())
    await db.commit()
    await db.refresh(f)
    if f.enabled:
        asyncio.create_task(_replay_filter_on_seen_items(f, user.id))
    return _serialize_filter(f)


@router.patch("/{filter_id}", response_model=FilterOut)
async def update_filter(
    filter_id: int,
    payload: FilterUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    f = await db.get(Filter, filter_id)
    if not f or f.user_id != user.id:
        raise HTTPException(404, "Filtre introuvable")
    data = payload.model_dump(exclude_unset=True)
    if data.get("auto_buy"):
        from database import PLAN_LIMITS
        if not PLAN_LIMITS.get(user.plan, {}).get("auto_buy", False):
            raise HTTPException(403, "L'achat automatique nécessite le plan Pro ou supérieur")
    _apply_filter_data(f, data)
    await db.commit()
    await db.refresh(f)
    if f.enabled:
        asyncio.create_task(_replay_filter_on_seen_items(f, user.id))
    return _serialize_filter(f)


@router.delete("/{filter_id}", status_code=204)
async def delete_filter(
    filter_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    f = await db.get(Filter, filter_id)
    if not f or f.user_id != user.id:
        raise HTTPException(404, "Filtre introuvable")
    await db.delete(f)
    await db.commit()


@router.post("/{filter_id}/test")
async def test_filter(
    filter_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    f = await db.get(Filter, filter_id)
    if not f or f.user_id != user.id:
        raise HTTPException(404, "Filtre introuvable")

    result = await db.execute(
        select(SeenItem).order_by(SeenItem.first_seen_at.desc()).limit(200)
    )
    items = result.scalars().all()

    matched = []
    for item in items:
        item_dict = {
            "id": item.vinted_id,
            "title": item.title,
            "price": item.price,
            "brand": item.brand,
            "brand_id": item.brand_id,
            "size": item.size,
            "size_id": item.size_id,
            "condition": item.condition,
            "condition_code": getattr(item, "condition_code", None),
            "photo_url": item.photo_url,
            "item_url": item.item_url,
            "country_code": item.country_code,
        }
        if _engine.match_item(item_dict, f):
            matched.append(item_dict)

    return {"matched_count": len(matched), "items": matched[:50]}
