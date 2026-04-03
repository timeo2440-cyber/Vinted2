"""
Authentication endpoints: register, login, me, activate license.
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from passlib.context import CryptContext
from database import AsyncSessionLocal, User, LicenseKey, PLAN_LIMITS
from auth_deps import create_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


class RegisterBody(BaseModel):
    email: str
    password: str


class LoginBody(BaseModel):
    email: str
    password: str


class ActivateLicenseBody(BaseModel):
    key: str


def _serialize_user(u: User) -> dict:
    from database import PLAN_LIMITS
    limits = PLAN_LIMITS.get(u.plan, PLAN_LIMITS["free"])
    return {
        "id": u.id,
        "email": u.email,
        "role": u.role,
        "plan": u.plan,
        "plan_expires_at": u.plan_expires_at.isoformat() if u.plan_expires_at else None,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "limits": limits,
    }


@router.post("/register")
async def register(body: RegisterBody):
    """
    Register a new user.
    The very first user registered automatically becomes admin with unlimited plan.
    """
    if not body.email or not body.password:
        raise HTTPException(400, "Email et mot de passe requis")
    if len(body.password) < 6:
        raise HTTPException(400, "Mot de passe trop court (min 6 caractères)")

    async with AsyncSessionLocal() as db:
        # Check if email already exists
        existing = await db.execute(select(User).where(User.email == body.email.lower()))
        if existing.scalar_one_or_none():
            raise HTTPException(400, "Cet email est déjà utilisé")

        # First user gets admin + unlimited plan
        count_result = await db.execute(select(User))
        is_first = not count_result.scalars().first()

        user = User(
            email=body.email.lower().strip(),
            password_hash=pwd_ctx.hash(body.password),
            role="admin" if is_first else "user",
            plan="unlimited" if is_first else "free",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_token(user.id, user.role)
    return {"token": token, "user": _serialize_user(user)}


@router.post("/login")
async def login(body: LoginBody):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == body.email.lower().strip()))
        user = result.scalar_one_or_none()

    if not user or not pwd_ctx.verify(body.password, user.password_hash):
        raise HTTPException(401, "Email ou mot de passe incorrect")
    if not user.is_active:
        raise HTTPException(403, "Compte suspendu — contactez l'administrateur")

    token = create_token(user.id, user.role)
    return {"token": token, "user": _serialize_user(user)}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return _serialize_user(user)


@router.post("/activate-license")
async def activate_license(body: ActivateLicenseBody, user: User = Depends(get_current_user)):
    """Use a license key to upgrade the current user's plan."""
    async with AsyncSessionLocal() as db:
        lic = await db.get(LicenseKey, body.key.strip())
        if not lic:
            raise HTTPException(404, "Clé de licence introuvable")
        if lic.used_by_user_id:
            raise HTTPException(400, "Cette clé a déjà été utilisée")

        # Activate
        lic.used_by_user_id = user.id
        lic.used_at = datetime.now(timezone.utc)

        u = await db.get(User, user.id)
        u.plan = lic.plan
        u.plan_expires_at = datetime.now(timezone.utc) + timedelta(days=lic.duration_days)
        await db.commit()
        await db.refresh(u)

    return {"ok": True, "plan": u.plan, "expires_at": u.plan_expires_at.isoformat()}


@router.post("/change-password")
async def change_password(
    body: dict,
    user: User = Depends(get_current_user),
):
    old_pw = body.get("old_password", "")
    new_pw = body.get("new_password", "")
    if not pwd_ctx.verify(old_pw, user.password_hash):
        raise HTTPException(400, "Ancien mot de passe incorrect")
    if len(new_pw) < 6:
        raise HTTPException(400, "Nouveau mot de passe trop court")
    async with AsyncSessionLocal() as db:
        u = await db.get(User, user.id)
        u.password_hash = pwd_ctx.hash(new_pw)
        await db.commit()
    return {"ok": True}
