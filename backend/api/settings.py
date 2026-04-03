from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, Setting, UserSetting, User
from models import SettingsUpdate, CookieSubmit, AuthStatus
from vinted.auth import parse_cookie_string, validate_session
from auth_deps import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])


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


@router.get("")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    poll_ms = await _get_setting(db, "poll_interval_ms", "4000")
    max_buy = await _get_user_setting(db, user.id, "max_buy_per_hour", "5")
    has_cookies = bool(await _get_setting(db, "vinted_cookies"))
    return {
        "poll_interval_ms": int(poll_ms),
        "max_buy_per_hour": int(max_buy),
        "has_cookies": has_cookies,
    }


@router.put("")
async def update_settings(
    payload: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.max_buy_per_hour is not None:
        await _set_user_setting(db, user.id, "max_buy_per_hour", str(payload.max_buy_per_hour))
    # Poll interval is global — only admin can change it
    if payload.poll_interval_ms is not None and user.role == "admin":
        row = await db.get(Setting, "poll_interval_ms")
        if row:
            row.value = str(payload.poll_interval_ms)
        else:
            db.add(Setting(key="poll_interval_ms", value=str(payload.poll_interval_ms)))
        await db.commit()
    return {"ok": True}


@router.post("/cookies")
async def submit_cookies(
    payload: CookieSubmit,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Accept and validate new Vinted cookies for the primary polling client."""
    from vinted.client import VintedClient

    cookies_raw = payload.cookies.strip()
    if not cookies_raw:
        return AuthStatus(authenticated=False)

    client: VintedClient = request.app.state.vinted_client
    cookies = parse_cookie_string(cookies_raw)
    client.set_cookies(cookies)
    await client.fetch_csrf_token()
    result = await validate_session(client)

    if result["authenticated"]:
        await _set_user_setting(db, user.id, "vinted_cookies", cookies_raw)

    return AuthStatus(**result)


@router.get("/auth-status")
async def auth_status(
    request: Request,
    user: User = Depends(get_current_user),
):
    from vinted.client import VintedClient
    client: VintedClient = request.app.state.vinted_client
    result = await validate_session(client)
    return AuthStatus(**result)
