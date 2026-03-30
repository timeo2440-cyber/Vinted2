from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, Setting
from models import SettingsUpdate, CookieSubmit, AuthStatus
from vinted.auth import parse_cookie_string, validate_session

router = APIRouter(prefix="/api/settings", tags=["settings"])


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


@router.get("")
async def get_settings(db: AsyncSession = Depends(get_db)):
    poll_ms = await _get_setting(db, "poll_interval_ms", "4000")
    max_buy = await _get_setting(db, "max_buy_per_hour", "5")
    has_cookies = bool(await _get_setting(db, "vinted_cookies"))
    return {
        "poll_interval_ms": int(poll_ms),
        "max_buy_per_hour": int(max_buy),
        "has_cookies": has_cookies,
    }


@router.put("")
async def update_settings(payload: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    if payload.poll_interval_ms is not None:
        await _set_setting(db, "poll_interval_ms", str(payload.poll_interval_ms))
    if payload.max_buy_per_hour is not None:
        await _set_setting(db, "max_buy_per_hour", str(payload.max_buy_per_hour))
    return {"ok": True}


@router.post("/cookies")
async def submit_cookies(payload: CookieSubmit, request: Request, db: AsyncSession = Depends(get_db)):
    """Accept and validate new Vinted cookies."""
    from vinted.client import VintedClient

    cookies_raw = payload.cookies.strip()
    if not cookies_raw:
        return AuthStatus(authenticated=False)

    # Validate immediately
    client: VintedClient = request.app.state.vinted_client
    cookies = parse_cookie_string(cookies_raw)
    client.set_cookies(cookies)
    await client.fetch_csrf_token()
    result = await validate_session(client)

    if result["authenticated"]:
        # Store in DB
        await _set_setting(db, "vinted_cookies", cookies_raw)

    return AuthStatus(**result)


@router.get("/auth-status")
async def auth_status(request: Request, db: AsyncSession = Depends(get_db)):
    """Check current authentication status."""
    from vinted.client import VintedClient
    client: VintedClient = request.app.state.vinted_client
    result = await validate_session(client)
    return AuthStatus(**result)
