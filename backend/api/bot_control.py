from fastapi import APIRouter, Request, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, Setting

router = APIRouter(prefix="/api/bot", tags=["bot"])


async def _get_setting(db, key: str, default: str = "") -> str:
    result = await db.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row and row.value else default


async def _set_setting(db, key: str, value: str) -> None:
    row = await db.get(Setting, key)
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    await db.commit()


@router.get("/status")
async def bot_status(request: Request, db: AsyncSession = Depends(get_db)):
    poller = request.app.state.poller
    status = await poller.get_status()
    from vinted.auth import validate_session
    client = request.app.state.vinted_client
    auth = await validate_session(client)
    status["authenticated"] = auth["authenticated"]
    status["username"] = auth.get("username")
    status["ws_connections"] = request.app.state.ws_manager.connection_count
    # Include global autocop state
    autocop_val = await _get_setting(db, "global_autocop", "false")
    status["autocop_enabled"] = autocop_val.lower() == "true"
    return status


@router.get("/autocop")
async def get_autocop(db: AsyncSession = Depends(get_db)):
    val = await _get_setting(db, "global_autocop", "false")
    return {"autocop_enabled": val.lower() == "true"}


@router.post("/autocop")
async def set_autocop(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    enabled = bool(body.get("enabled", False))
    await _set_setting(db, "global_autocop", "true" if enabled else "false")
    return {"autocop_enabled": enabled}


# Keep start/stop for emergency use (not shown in UI)
@router.post("/start")
async def start_bot(request: Request):
    poller = request.app.state.poller
    if poller.running:
        return {"ok": True, "message": "Bot already running"}
    await poller.start()
    return {"ok": True, "message": "Bot started"}


@router.post("/stop")
async def stop_bot(request: Request):
    poller = request.app.state.poller
    if not poller.running:
        return {"ok": True, "message": "Bot already stopped"}
    await poller.stop()
    return {"ok": True, "message": "Bot stopped"}
