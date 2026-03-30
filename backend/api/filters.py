import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, Filter, SeenItem
from models import FilterCreate, FilterUpdate, FilterOut
from bot.filter_engine import FilterEngine

router = APIRouter(prefix="/api/filters", tags=["filters"])
_engine = FilterEngine()


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
async def list_filters(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Filter).order_by(Filter.created_at))
    return [_serialize_filter(f) for f in result.scalars()]


@router.post("", response_model=FilterOut, status_code=201)
async def create_filter(payload: FilterCreate, db: AsyncSession = Depends(get_db)):
    f = Filter(name=payload.name, enabled=payload.enabled, auto_buy=payload.auto_buy,
               max_budget=payload.max_budget, keywords=payload.keywords,
               price_min=payload.price_min, price_max=payload.price_max)
    for list_field in ["category_ids", "brand_ids", "size_ids", "conditions", "country_codes"]:
        val = getattr(payload, list_field)
        setattr(f, list_field, json.dumps(val) if val is not None else None)
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return _serialize_filter(f)


@router.get("/{filter_id}", response_model=FilterOut)
async def get_filter(filter_id: int, db: AsyncSession = Depends(get_db)):
    f = await db.get(Filter, filter_id)
    if not f:
        raise HTTPException(404, "Filter not found")
    return _serialize_filter(f)


@router.put("/{filter_id}", response_model=FilterOut)
async def replace_filter(filter_id: int, payload: FilterCreate, db: AsyncSession = Depends(get_db)):
    f = await db.get(Filter, filter_id)
    if not f:
        raise HTTPException(404, "Filter not found")
    _apply_filter_data(f, payload.model_dump())
    await db.commit()
    await db.refresh(f)
    return _serialize_filter(f)


@router.patch("/{filter_id}", response_model=FilterOut)
async def update_filter(filter_id: int, payload: FilterUpdate, db: AsyncSession = Depends(get_db)):
    f = await db.get(Filter, filter_id)
    if not f:
        raise HTTPException(404, "Filter not found")
    _apply_filter_data(f, payload.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(f)
    return _serialize_filter(f)


@router.delete("/{filter_id}", status_code=204)
async def delete_filter(filter_id: int, db: AsyncSession = Depends(get_db)):
    f = await db.get(Filter, filter_id)
    if not f:
        raise HTTPException(404, "Filter not found")
    await db.delete(f)
    await db.commit()


@router.post("/{filter_id}/test")
async def test_filter(filter_id: int, db: AsyncSession = Depends(get_db)):
    """Test a filter against the last 200 seen items."""
    f = await db.get(Filter, filter_id)
    if not f:
        raise HTTPException(404, "Filter not found")

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
            "size": item.size,
            "condition": item.condition,
            "photo_url": item.photo_url,
            "item_url": item.item_url,
            "country_code": item.country_code,
        }
        if _engine.match_item(item_dict, f):
            matched.append(item_dict)

    return {"matched_count": len(matched), "items": matched[:50]}
