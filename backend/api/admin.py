"""
Admin panel endpoints — only accessible to users with role='admin'.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from database import AsyncSessionLocal, User, LicenseKey, Filter, Account, Purchase, ActivityLog
from auth_deps import get_current_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _serialize_user(u: User) -> dict:
    from database import PLAN_LIMITS
    return {
        "id": u.id,
        "email": u.email,
        "role": u.role,
        "plan": u.plan,
        "plan_expires_at": u.plan_expires_at.isoformat() if u.plan_expires_at else None,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "limits": PLAN_LIMITS.get(u.plan, PLAN_LIMITS["free"]),
    }


# ── Users ──────────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(_: User = Depends(get_current_admin)):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).order_by(User.created_at.desc()))
        users = result.scalars().all()

        # Enrich with counts
        out = []
        for u in users:
            fcount = await db.execute(select(func.count()).select_from(Filter).where(Filter.user_id == u.id))
            acount = await db.execute(select(func.count()).select_from(Account).where(Account.user_id == u.id))
            pcount = await db.execute(select(func.count()).select_from(Purchase).where(Purchase.user_id == u.id))
            d = _serialize_user(u)
            d["filter_count"] = fcount.scalar() or 0
            d["account_count"] = acount.scalar() or 0
            d["purchase_count"] = pcount.scalar() or 0
            out.append(d)
    return out


@router.put("/users/{user_id}")
async def update_user(user_id: int, body: dict, admin: User = Depends(get_current_admin)):
    async with AsyncSessionLocal() as db:
        u = await db.get(User, user_id)
        if not u:
            raise HTTPException(404, "Utilisateur introuvable")
        if "plan" in body and body["plan"] in ("free", "pro", "unlimited"):
            u.plan = body["plan"]
        if "is_active" in body:
            u.is_active = bool(body["is_active"])
        if "role" in body and body["role"] in ("user", "admin"):
            if user_id == admin.id:
                raise HTTPException(400, "Impossible de modifier son propre rôle")
            u.role = body["role"]
        await db.commit()
        await db.refresh(u)
    return _serialize_user(u)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int, admin: User = Depends(get_current_admin)):
    if user_id == admin.id:
        raise HTTPException(400, "Impossible de supprimer son propre compte")
    async with AsyncSessionLocal() as db:
        u = await db.get(User, user_id)
        if not u:
            raise HTTPException(404, "Utilisateur introuvable")
        await db.delete(u)
        await db.commit()


# ── License keys ───────────────────────────────────────────────────────────────

@router.get("/licenses")
async def list_licenses(_: User = Depends(get_current_admin)):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(LicenseKey).order_by(LicenseKey.created_at.desc()))
        keys = result.scalars().all()
    return [
        {
            "key": k.key,
            "plan": k.plan,
            "duration_days": k.duration_days,
            "used_by_user_id": k.used_by_user_id,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "used_at": k.used_at.isoformat() if k.used_at else None,
        }
        for k in keys
    ]


@router.post("/licenses")
async def create_license(body: dict, _: User = Depends(get_current_admin)):
    plan = body.get("plan", "pro")
    if plan not in ("pro", "unlimited"):
        raise HTTPException(400, "Plan invalide (pro ou unlimited)")
    duration_days = int(body.get("duration_days", 30))

    key = LicenseKey.generate()
    async with AsyncSessionLocal() as db:
        db.add(LicenseKey(key=key, plan=plan, duration_days=duration_days))
        await db.commit()

    return {"key": key, "plan": plan, "duration_days": duration_days}


@router.delete("/licenses/{key}", status_code=204)
async def delete_license(key: str, _: User = Depends(get_current_admin)):
    async with AsyncSessionLocal() as db:
        lic = await db.get(LicenseKey, key)
        if not lic:
            raise HTTPException(404, "Clé introuvable")
        if lic.used_by_user_id:
            raise HTTPException(400, "Impossible de supprimer une clé déjà utilisée")
        await db.delete(lic)
        await db.commit()


# ── Global stats ───────────────────────────────────────────────────────────────

@router.get("/stats")
async def global_stats(_: User = Depends(get_current_admin)):
    async with AsyncSessionLocal() as db:
        user_count = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
        filter_count = (await db.execute(select(func.count()).select_from(Filter))).scalar() or 0
        account_count = (await db.execute(select(func.count()).select_from(Account))).scalar() or 0
        purchase_count = (await db.execute(select(func.count()).select_from(Purchase))).scalar() or 0
        from database import SeenItem
        seen_count = (await db.execute(select(func.count()).select_from(SeenItem))).scalar() or 0

        # Plan breakdown
        pro_count = (await db.execute(
            select(func.count()).select_from(User).where(User.plan == "pro")
        )).scalar() or 0
        unlimited_count = (await db.execute(
            select(func.count()).select_from(User).where(User.plan == "unlimited")
        )).scalar() or 0
        free_count = (await db.execute(
            select(func.count()).select_from(User).where(User.plan == "free")
        )).scalar() or 0

    return {
        "users": {"total": user_count, "free": free_count, "pro": pro_count, "unlimited": unlimited_count},
        "filters": filter_count,
        "accounts": account_count,
        "purchases": purchase_count,
        "seen_items": seen_count,
    }
