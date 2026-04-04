"""
Backup & restore API — export/import all user data as JSON.
Only accessible to admins.
"""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from database import AsyncSessionLocal, User, Filter, Account, Purchase, UserSetting, LicenseKey
from auth_deps import get_current_admin

router = APIRouter(prefix="/api/admin/backup", tags=["backup"])


@router.get("/export")
async def export_data(admin=Depends(get_current_admin)):
    """Export all platform data as JSON."""
    async with AsyncSessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()
        filters = (await db.execute(select(Filter))).scalars().all()
        accounts = (await db.execute(select(Account))).scalars().all()
        purchases = (await db.execute(select(Purchase))).scalars().all()
        settings = (await db.execute(select(UserSetting))).scalars().all()
        licenses = (await db.execute(select(LicenseKey))).scalars().all()

    def ser(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "users": [
            {"id": u.id, "email": u.email, "password_hash": u.password_hash,
             "role": u.role, "plan": u.plan, "is_active": u.is_active,
             "plan_expires_at": ser(u.plan_expires_at), "created_at": ser(u.created_at)}
            for u in users
        ],
        "filters": [
            {"id": f.id, "user_id": f.user_id, "name": f.name, "enabled": f.enabled,
             "auto_buy": f.auto_buy, "max_budget": f.max_budget, "keywords": f.keywords,
             "category_ids": f.category_ids, "brand_ids": f.brand_ids,
             "size_ids": f.size_ids, "conditions": f.conditions,
             "price_min": f.price_min, "price_max": f.price_max,
             "country_codes": f.country_codes}
            for f in filters
        ],
        "accounts": [
            {"id": a.id, "user_id": a.user_id, "name": a.name, "email": a.email,
             "password_enc": a.password_enc, "cookies": a.cookies,
             "csrf_token": a.csrf_token, "vinted_user_id": a.vinted_user_id,
             "vinted_username": a.vinted_username, "is_authenticated": a.is_authenticated,
             "is_active": a.is_active, "purchases_count": a.purchases_count}
            for a in accounts
        ],
        "purchases": [
            {"id": p.id, "user_id": p.user_id, "filter_id": p.filter_id,
             "vinted_item_id": p.vinted_item_id, "item_title": p.item_title,
             "price": p.price, "status": p.status, "attempted_at": ser(p.attempted_at)}
            for p in purchases
        ],
        "user_settings": [
            {"user_id": s.user_id, "key": s.key, "value": s.value}
            for s in settings
        ],
        "licenses": [
            {"key": l.key, "plan": l.plan, "duration_days": l.duration_days,
             "used_by_user_id": l.used_by_user_id, "created_at": ser(l.created_at)}
            for l in licenses
        ],
    }
    return JSONResponse(content=data, headers={
        "Content-Disposition": f'attachment; filename="vintedbot_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'
    })
