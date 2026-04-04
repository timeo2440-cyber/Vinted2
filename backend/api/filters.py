import json
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, Filter, SeenItem, User, AsyncSessionLocal
from models import FilterCreate, FilterUpdate, FilterOut
from bot.filter_engine import FilterEngine
from auth_deps import get_current_user, check_plan_limit
from ws.manager import ws_manager

router = APIRouter(prefix="/api/filters", tags=["filters"])
_engine = FilterEngine()
logger = logging.getLogger("api.filters")


async def _replay_filter_on_seen_items(f: Filter, user_id: int) -> None:
    """
    After a filter is created/updated, immediately replay it against the last
    500 seen items and send item_match WS events for anything that matches.
    This fills the feed instantly instead of waiting for the next poll cycle.
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SeenItem).order_by(SeenItem.first_seen_at.desc()).limit(500)
            )
            items = result.scalars().all()

        logger.info(f"Replay filtre '{f.name}' (user {user_id}) sur {len(items)} articles vus")

        matched = 0
        for item in items:
            item_dict = {
                "id": item.vinted_id,
                "title": item.title,
                "price": item.price,
                "brand": item.brand,
                "brand_id": getattr(item, "brand_id", None),
                "category_id": getattr(item, "category_id", None),
                "size": item.size,
                "size_id": getattr(item, "size_id", None),
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
                if matched >= 50:
                    break

        logger.info(f"Replay terminé: {matched} correspondance(s) pour filtre '{f.name}'")

        # If seen_items was empty, the bot hasn't fetched anything yet.
        # Log a hint so the user knows to wait or check settings.
        if not items:
            logger.warning(
                f"Replay: aucun article en base (bot vient de démarrer ou Vinted inaccessible). "
                f"Les résultats apparaîtront dès que le bot scrappe des articles."
            )
            await ws_manager.broadcast_log(
                "warn",
                "Aucun article encore scanné — le bot démarre. "
                "Les correspondances apparaîtront dès que Vinted est scrappé (< 10s).",
                "filters",
                user_id=user_id,
            )

    except Exception as e:
        logger.error(f"Replay filter error: {e}", exc_info=True)



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
        brand_names=parse_json(f.brand_names),
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

    for list_field in ["category_ids", "brand_ids", "brand_names", "size_ids", "conditions", "country_codes"]:
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
    for list_field in ["category_ids", "brand_ids", "brand_names", "size_ids", "conditions", "country_codes"]:
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


@router.get("/{filter_id}/debug")
async def debug_filter(
    filter_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Live debug: do a real targeted Vinted fetch with this filter's params,
    then show exactly why each item passes or fails the filter.
    """
    import json as _json
    from fastapi import Request as _Request
    from vinted.catalog import fetch_newest_items, search_items

    f = await db.get(Filter, filter_id)
    if not f or f.user_id != user.id:
        raise HTTPException(404, "Filtre introuvable")

    def _parse(val):
        if not val: return []
        if isinstance(val, list): return val
        try: return _json.loads(val)
        except: return []

    brand_ids   = _parse(f.brand_ids)
    category_ids = _parse(f.category_ids)
    size_ids    = _parse(f.size_ids)
    keywords    = (f.keywords or "").strip()

    client = request.app.state.vinted_client
    items = []
    fetch_method = "none"

    if brand_ids or category_ids or size_ids:
        fetch_method = f"targeted (brands={brand_ids}, cats={category_ids})"
        try:
            items = await fetch_newest_items(
                client, per_page=20,
                brand_ids=[int(b) for b in brand_ids] if brand_ids else None,
                category_ids=[int(c) for c in category_ids] if category_ids else None,
                size_ids=[int(s) for s in size_ids] if size_ids else None,
            )
            # Tag items (same as poller)
            for item in items:
                if brand_ids:
                    item["_targeted_brand_ids"] = [int(b) for b in brand_ids]
                if category_ids:
                    item["_targeted_category_ids"] = [int(c) for c in category_ids]
        except Exception as e:
            return {"error": str(e), "fetch_method": fetch_method}
    elif keywords:
        fetch_method = f"keyword search: {keywords!r}"
        try:
            items = await search_items(client, query=keywords, per_page=20)
        except Exception as e:
            return {"error": str(e), "fetch_method": fetch_method}
    else:
        from vinted.catalog import fetch_newest_items as _fn
        fetch_method = "generic (no criteria)"
        try:
            items = await _fn(client, per_page=20)
        except Exception as e:
            return {"error": str(e), "fetch_method": fetch_method}

    # Analyse each item
    results = []
    for item in items[:15]:
        why_pass = []
        why_fail = []

        # Brand
        if brand_ids:
            ibid = str(item.get("brand_id") or "")
            tbids = [str(b) for b in (item.get("_targeted_brand_ids") or [])]
            if ibid and ibid in [str(b) for b in brand_ids]:
                why_pass.append(f"brand_id={ibid} ✓")
            elif tbids:
                why_pass.append(f"trusted brand (targeted fetch) ✓")
            elif not ibid:
                ibrand = (item.get("brand") or "").strip()
                brand_names = _parse(f.brand_names)
                if brand_names and ibrand:
                    matched_text = any(bn.lower() in ibrand.lower() or ibrand.lower() in bn.lower() for bn in brand_names if bn)
                    if matched_text:
                        why_pass.append(f"brand text match: '{ibrand}' ✓")
                    else:
                        why_fail.append(f"brand text mismatch: item='{ibrand}', filter={brand_names}")
                else:
                    why_pass.append(f"brand skip (no brand_id, no text) ✓")
            else:
                why_fail.append(f"brand_id={ibid} not in filter {brand_ids}")

        # Category
        if category_ids:
            icid = item.get("category_id")
            tcids = [str(c) for c in (item.get("_targeted_category_ids") or [])]
            if icid is not None and str(icid) in [str(c) for c in category_ids]:
                why_pass.append(f"category_id={icid} ✓")
            elif tcids:
                why_pass.append(f"trusted category (targeted fetch) ✓")
            elif icid is not None:
                why_fail.append(f"category_id={icid} not in filter {category_ids}")
            else:
                why_pass.append(f"category skip (no category_id) ✓")

        passed = _engine.match_item(item, f)
        results.append({
            "id": item.get("id"),
            "title": item.get("title", "")[:60],
            "brand": item.get("brand"),
            "brand_id": item.get("brand_id"),
            "category_id": item.get("category_id"),
            "price": item.get("price"),
            "match": passed,
            "why_pass": why_pass,
            "why_fail": why_fail,
        })

    matched_count = sum(1 for r in results if r["match"])
    return {
        "filter": {"name": f.name, "brand_ids": brand_ids, "category_ids": category_ids, "keywords": keywords},
        "fetch_method": fetch_method,
        "total_fetched": len(items),
        "matched": matched_count,
        "items": results,
    }

