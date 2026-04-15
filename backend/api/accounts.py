import json
import base64
import secrets
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from database import AsyncSessionLocal, Account, User
from vinted.auth import login_with_credentials, validate_session, parse_cookie_string
from vinted.client import VintedClient
from auth_deps import get_current_user, check_plan_limit

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountCreate(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    ban_suspected: Optional[bool] = None
    default_address: Optional[dict] = None
    preferred_pickup_points: Optional[list] = None
    phone_number: Optional[str] = None
    payment_card: Optional[dict] = None  # {number, expiry, cvv, holder}


class CookiesBody(BaseModel):
    cookies: str


def _serialize(account: Account) -> dict:
    return {
        "id": account.id,
        "name": account.name,
        "email": account.email,
        "vinted_user_id": account.vinted_user_id,
        "vinted_username": account.vinted_username,
        "is_authenticated": account.is_authenticated,
        "is_active": account.is_active,
        "ban_suspected": account.ban_suspected,
        "purchases_count": account.purchases_count,
        "last_login": account.last_login.isoformat() if account.last_login else None,
        "default_address": json.loads(account.default_address) if account.default_address else None,
        "preferred_pickup_points": json.loads(account.preferred_pickup_points) if account.preferred_pickup_points else [],
        "phone_number": account.phone_number,
        "payment_card": json.loads(account.payment_card) if account.payment_card else None,
        "created_at": account.created_at.isoformat() if account.created_at else None,
    }


@router.get("")
async def list_accounts(user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Account).where(Account.user_id == user.id).order_by(Account.created_at.desc())
        )
        return [_serialize(a) for a in result.scalars().all()]


@router.post("")
async def create_account(body: AccountCreate, request: Request, user: User = Depends(get_current_user)):
    # Check plan limits
    async with AsyncSessionLocal() as db:
        count_res = await db.execute(select(Account).where(Account.user_id == user.id))
        current_count = len(count_res.scalars().all())
    check_plan_limit(user, "accounts", current_count)

    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Account).where(Account.email == body.email, Account.user_id == user.id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(400, "Un compte avec cet email existe déjà")

    password_enc = base64.b64encode(body.password.encode()).decode()

    # Créer le compte immédiatement comme "connecté" — la connexion Vinted
    # se fait en arrière-plan au prochain démarrage ou lors de l'autocop
    async with AsyncSessionLocal() as db:
        account = Account(
            user_id=user.id,
            name=body.name or body.email.split("@")[0],
            email=body.email,
            password_enc=password_enc,
            cookies=None,
            csrf_token=None,
            vinted_user_id=None,
            vinted_username=None,
            is_authenticated=True,  # Faire confiance à l'utilisateur
            last_login=datetime.now(timezone.utc),
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)

        # Tenter la connexion en arrière-plan (non bloquant)
        mgr = getattr(request.app.state, "account_manager", None)
        if mgr:
            import asyncio
            asyncio.create_task(mgr.refresh_account(account.id))

        return _serialize(account)


@router.get("/{account_id}")
async def get_account(account_id: int, user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as db:
        account = await db.get(Account, account_id)
        if not account or account.user_id != user.id:
            raise HTTPException(404, "Compte introuvable")
        return _serialize(account)


@router.put("/{account_id}")
async def update_account(account_id: int, body: AccountUpdate, request: Request, user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as db:
        account = await db.get(Account, account_id)
        if not account or account.user_id != user.id:
            raise HTTPException(404, "Compte introuvable")
        if body.name is not None:
            account.name = body.name
        if body.is_active is not None:
            account.is_active = body.is_active
        if body.ban_suspected is not None:
            account.ban_suspected = body.ban_suspected
        if body.default_address is not None:
            account.default_address = json.dumps(body.default_address)
        if body.preferred_pickup_points is not None:
            account.preferred_pickup_points = json.dumps(body.preferred_pickup_points)
        if body.phone_number is not None:
            account.phone_number = body.phone_number or None
        if body.payment_card is not None:
            account.payment_card = json.dumps(body.payment_card) if body.payment_card else None
        await db.commit()
        await db.refresh(account)

        mgr = getattr(request.app.state, "account_manager", None)
        if mgr:
            import asyncio
            asyncio.create_task(mgr.refresh_account(account_id))
        return _serialize(account)


@router.delete("/{account_id}")
async def delete_account(account_id: int, request: Request, user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as db:
        account = await db.get(Account, account_id)
        if not account or account.user_id != user.id:
            raise HTTPException(404, "Compte introuvable")
        await db.delete(account)
        await db.commit()

    mgr = getattr(request.app.state, "account_manager", None)
    if mgr:
        await mgr.remove_account(account_id)
    return {"ok": True}


@router.post("/{account_id}/login")
async def relogin_account(account_id: int, request: Request, user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as db:
        account = await db.get(Account, account_id)
        if not account or account.user_id != user.id:
            raise HTTPException(404, "Compte introuvable")
        if not account.password_enc:
            raise HTTPException(400, "Mot de passe non enregistré — utilisez les cookies manuels")
        try:
            password = base64.b64decode(account.password_enc.encode()).decode()
        except Exception:
            raise HTTPException(400, "Mot de passe corrompu")

        from config import settings as app_settings
        from vinted.browser_login import login_via_browser
        result = await login_via_browser(app_settings.vinted_base_url, account.email, password)

        account.is_authenticated = result["success"]
        if result["success"]:
            account.cookies = json.dumps(result["cookies"]) if result.get("cookies") else None
            account.csrf_token = result.get("csrf_token")
            account.vinted_user_id = result.get("user_id")
            account.vinted_username = result.get("username")
            account.last_login = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(account)

    mgr = getattr(request.app.state, "account_manager", None)
    if mgr:
        await mgr.refresh_account(account_id)

    resp = _serialize(account)
    if not result["success"]:
        resp["error"] = result.get("error")
    return resp


@router.post("/{account_id}/cookies")
async def set_account_cookies(account_id: int, body: CookiesBody, request: Request, user: User = Depends(get_current_user)):
    """Set cookies manually — trusted unconditionally (no network validation)."""
    from urllib.parse import unquote as _unquote

    async with AsyncSessionLocal() as db:
        account = await db.get(Account, account_id)
        if not account or account.user_id != user.id:
            raise HTTPException(404, "Compte introuvable")

        cookies = parse_cookie_string(body.cookies)
        if not cookies:
            raise HTTPException(400, "Cookies invalides")

        csrf = _unquote(cookies.get("XSRF-TOKEN") or cookies.get("xsrf-token") or "")

        # Trust the user's cookies unconditionally — no validation call.
        account.cookies = json.dumps(cookies)
        account.csrf_token = csrf or ""
        account.is_authenticated = True
        account.last_login = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(account)

    mgr = getattr(request.app.state, "account_manager", None)
    if mgr:
        await mgr.refresh_account(account_id)
    result = _serialize(account)
    result["validation_reason"] = "trusted"
    return result


@router.get("/{account_id}/sync-token")
async def get_sync_token(account_id: int, user: User = Depends(get_current_user)):
    """Retourne le token de synchronisation pour le bookmarklet."""
    async with AsyncSessionLocal() as db:
        account = await db.get(Account, account_id)
        if not account or account.user_id != user.id:
            raise HTTPException(404, "Compte introuvable")
        if not account.sync_token:
            account.sync_token = secrets.token_urlsafe(32)
            await db.commit()
        return {"sync_token": account.sync_token, "account_id": account_id}


@router.post("/sync/{sync_token}")
async def sync_cookies_via_token(sync_token: str, body: CookiesBody, request: Request):
    """
    Endpoint public (appelé par le bookmarklet depuis vinted.fr).
    CORS autorisé pour permettre les appels cross-origin.
    """
    from urllib.parse import unquote as _unquote
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Account).where(Account.sync_token == sync_token))
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(404, "Token invalide")

        cookies = parse_cookie_string(body.cookies)
        if not cookies:
            raise HTTPException(400, "Cookies invalides")

        csrf = _unquote(cookies.get("XSRF-TOKEN") or cookies.get("xsrf-token") or "")
        account.cookies = json.dumps(cookies)
        account.csrf_token = csrf or ""
        account.is_authenticated = True
        account.last_login = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(account)

    mgr = getattr(request.app.state, "account_manager", None)
    if mgr:
        import asyncio
        asyncio.create_task(mgr.refresh_account(account.id))

    resp = JSONResponse({"ok": True, "username": account.vinted_username or account.email})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@router.options("/sync/{sync_token}")
async def sync_cookies_options(sync_token: str):
    """CORS preflight pour le bookmarklet."""
    resp = JSONResponse({})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@router.get("/{account_id}/status")
async def check_account_status(account_id: int, request: Request, user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as db:
        account = await db.get(Account, account_id)
        if not account or account.user_id != user.id:
            raise HTTPException(404, "Compte introuvable")

    mgr = getattr(request.app.state, "account_manager", None)
    if not mgr:
        return {"authenticated": account.is_authenticated}

    client = mgr.get_client(account_id)
    if not client:
        return {"authenticated": account.is_authenticated, "reason": "no_client"}

    result = await validate_session(client)
    auth = result.get("authenticated")
    if auth is True and not account.is_authenticated:
        async with AsyncSessionLocal() as db:
            acc = await db.get(Account, account_id)
            if acc:
                acc.is_authenticated = True
                await db.commit()
    elif auth is False:
        async with AsyncSessionLocal() as db:
            acc = await db.get(Account, account_id)
            if acc:
                acc.is_authenticated = False
                await db.commit()
    return result
