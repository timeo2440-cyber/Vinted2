from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, Setting, UserSetting, Purchase, ActivityLog, User
from datetime import datetime, timezone
from auth_deps import get_current_user

router = APIRouter(prefix="/api/bot", tags=["bot"])


async def _get_setting(db, key: str, default: str = "") -> str:
    result = await db.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row and row.value else default


async def _get_user_setting(db, user_id: int, key: str, default: str = "") -> str:
    result = await db.execute(
        select(UserSetting).where(UserSetting.user_id == user_id, UserSetting.key == key)
    )
    row = result.scalar_one_or_none()
    return row.value if row and row.value else default


async def _set_user_setting(db, user_id: int, key: str, value: str) -> None:
    result = await db.execute(
        select(UserSetting).where(UserSetting.user_id == user_id, UserSetting.key == key)
    )
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(UserSetting(user_id=user_id, key=key, value=value))
    await db.commit()


@router.get("/status")
async def bot_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    poller = request.app.state.poller
    status = await poller.get_status()
    status["ws_connections"] = request.app.state.ws_manager.connection_count
    # Per-user autocop state
    autocop_val = await _get_user_setting(db, user.id, "autocop", "false")
    status["autocop_enabled"] = autocop_val.lower() == "true"
    return status


@router.get("/autocop")
async def get_autocop(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    val = await _get_user_setting(db, user.id, "autocop", "false")
    return {"autocop_enabled": val.lower() == "true"}


@router.post("/autocop")
async def set_autocop(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Check plan allows auto_buy
    from database import PLAN_LIMITS
    if not PLAN_LIMITS.get(user.plan, {}).get("auto_buy", False):
        from fastapi import HTTPException
        raise HTTPException(403, "L'Autocop nécessite le plan Pro ou supérieur")

    body = await request.json()
    enabled = bool(body.get("enabled", False))
    await _set_user_setting(db, user.id, "autocop", "true" if enabled else "false")
    return {"autocop_enabled": enabled}


@router.post("/start")
async def start_bot(request: Request, user: User = Depends(get_current_user)):
    if user.role != "admin":
        from fastapi import HTTPException
        raise HTTPException(403, "Admin uniquement")
    poller = request.app.state.poller
    if poller.running:
        return {"ok": True, "message": "Bot already running"}
    await poller.start()
    return {"ok": True, "message": "Bot started"}


@router.post("/stop")
async def stop_bot(request: Request, user: User = Depends(get_current_user)):
    if user.role != "admin":
        from fastapi import HTTPException
        raise HTTPException(403, "Admin uniquement")
    poller = request.app.state.poller
    if not poller.running:
        return {"ok": True, "message": "Bot already stopped"}
    await poller.stop()
    return {"ok": True, "message": "Bot stopped"}


class ManualBuyRequest(BaseModel):
    id: str
    title: Optional[str] = None
    price: Optional[float] = None
    item_url: Optional[str] = None


@router.post("/manual-buy")
async def manual_buy(
    payload: ManualBuyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from vinted.checkout import full_purchase_flow
    from database import AsyncSessionLocal

    account_manager = request.app.state.account_manager
    primary_client = request.app.state.vinted_client

    # Use this user's accounts
    account_id = None
    buy_client = primary_client
    if account_manager and account_manager.has_clients():
        pair = account_manager.get_random_client_for_user(user.id)
        if pair:
            account_id, buy_client = pair

    async with AsyncSessionLocal() as adb:
        purchase = Purchase(
            user_id=user.id,
            filter_id=None,
            account_id=account_id,
            vinted_item_id=payload.id,
            item_title=payload.title,
            price=payload.price,
            status="pending",
        )
        adb.add(purchase)
        await adb.commit()
        await adb.refresh(purchase)
        purchase_id = purchase.id

    result = await full_purchase_flow(buy_client, payload.id)

    async with AsyncSessionLocal() as adb:
        purchase = await adb.get(Purchase, purchase_id)
        if purchase:
            purchase.status = "success" if result.success else "failed"
            purchase.error_message = result.error
            purchase.completed_at = datetime.now(timezone.utc)
            if result.price_paid:
                purchase.price = result.price_paid
            await adb.commit()

        log = ActivityLog(
            user_id=user.id,
            level="success" if result.success else "error",
            category="buy",
            message=(
                f"Achat manuel réussi : {payload.title} — {result.price_paid}€"
                if result.success
                else f"Achat manuel échoué : {payload.title} — {result.error}"
            ),
        )
        adb.add(log)
        await adb.commit()

    ws = request.app.state.ws_manager
    await ws.send_to_user(user.id, "buy_result", {
        "item_id": payload.id,
        "status": "success" if result.success else "failed",
        "price": result.price_paid,
        "error": result.error,
    })

    return {"success": result.success, "error": result.error, "price_paid": result.price_paid}
