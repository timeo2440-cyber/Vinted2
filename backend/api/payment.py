"""
Stripe payment endpoints.
Flow: landing → /payer?plan=starter → Stripe Checkout → /paiement/succes?session_id=xxx → licence key affichée
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from config import settings

router = APIRouter(prefix="/api/payment", tags=["payment"])

PRICES = {
    "starter": {"amount": 1000, "label": "Flashcop Starter — 10€/mois"},
    "pro":     {"amount": 3000, "label": "Flashcop Pro — 30€/mois"},
    "premium": {"amount": 8000, "label": "Flashcop Premium — 80€/mois"},
}


def _stripe():
    """Return stripe module configured with secret key."""
    import stripe as _s
    if not settings.stripe_secret_key:
        return None
    _s.api_key = settings.stripe_secret_key
    return _s


@router.post("/checkout")
async def create_checkout(request: Request):
    """Create a Stripe Checkout session and return the URL."""
    body = await request.json()
    plan = body.get("plan", "starter")
    customer_email = body.get("customer_email") or None

    if plan not in PRICES:
        raise HTTPException(400, "Plan invalide")

    stripe = _stripe()
    if not stripe:
        raise HTTPException(503, "Paiement non configuré — contactez l'administrateur")

    price_info = PRICES[plan]
    base_url = str(request.base_url).rstrip("/")

    kwargs = dict(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {"name": price_info["label"]},
                "unit_amount": price_info["amount"],
                "recurring": {"interval": "month"},
            },
            "quantity": 1,
        }],
        mode="subscription",
        success_url=f"{base_url}/paiement/succes?session_id={{CHECKOUT_SESSION_ID}}&plan={plan}",
        cancel_url=f"{base_url}/inscription?plan={plan}",
        metadata={"plan": plan},
    )
    if customer_email:
        kwargs["customer_email"] = customer_email

    session = stripe.checkout.Session.create(**kwargs)
    return {"url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks — auto-generate license key on payment success."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    stripe = _stripe()
    if not stripe:
        return {"ok": False}

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except Exception:
        raise HTTPException(400, "Webhook invalide")

    if event["type"] in ("checkout.session.completed", "invoice.payment_succeeded"):
        session = event["data"]["object"]
        plan = session.get("metadata", {}).get("plan", "starter")
        await _auto_create_license(plan)

    return {"ok": True}


async def _auto_create_license(plan: str) -> str:
    """Auto-generate a license key for a paid plan."""
    import secrets as _secrets
    from database import AsyncSessionLocal, LicenseKey
    key = _secrets.token_urlsafe(32)
    async with AsyncSessionLocal() as db:
        db.add(LicenseKey(key=key, plan=plan, duration_days=30))
        await db.commit()
    return key


@router.get("/session/{session_id}")
async def get_session_license(session_id: str, plan: str = "starter"):
    """After successful payment, return the generated license key."""
    stripe = _stripe()
    if not stripe:
        raise HTTPException(503, "Paiement non configuré")

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        raise HTTPException(404, "Session introuvable")

    if session.payment_status not in ("paid", "no_payment_needed"):
        raise HTTPException(402, "Paiement non confirmé")

    # Check if a license was already created for this session
    from database import AsyncSessionLocal, LicenseKey
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(LicenseKey)
            .where(LicenseKey.plan == plan, LicenseKey.used_by_user_id == None)
            .order_by(LicenseKey.created_at.desc())
            .limit(1)
        )
        lic = existing.scalar_one_or_none()
        if not lic:
            key = await _auto_create_license(plan)
        else:
            key = lic.key

    return {"key": key, "plan": plan}


class CompleteSignupBody(BaseModel):
    session_id: str
    email: str
    password: str
    plan: str = "starter"


@router.post("/complete-signup")
async def complete_signup(body: CompleteSignupBody):
    """
    After Stripe payment, create a user account in one step.
    Verifies that the Stripe session is paid, then registers the user.
    """
    if not body.email or not body.password:
        raise HTTPException(400, "Email et mot de passe requis")
    if len(body.password) < 6:
        raise HTTPException(400, "Mot de passe trop court (min 6 caractères)")
    if body.plan not in PRICES:
        raise HTTPException(400, "Plan invalide")

    # Verify Stripe payment
    stripe = _stripe()
    if stripe:
        try:
            session = stripe.checkout.Session.retrieve(body.session_id)
            if session.payment_status not in ("paid", "no_payment_needed"):
                raise HTTPException(402, "Paiement non confirmé. Réessaie ou contacte le support.")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(404, "Session de paiement introuvable")

    # Create user account
    import bcrypt as _bcrypt
    from database import AsyncSessionLocal, User, LicenseKey
    from auth_deps import create_token
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as db:
        # Check if email already exists
        existing = await db.execute(select(User).where(User.email == body.email.lower().strip()))
        existing_user = existing.scalar_one_or_none()
        if existing_user:
            # Already registered (e.g. page refreshed) — just log them in
            token = create_token(existing_user.id, existing_user.role)
            from api.auth import _serialize_user
            return {"token": token, "user": _serialize_user(existing_user)}

        # Count existing users (first = admin)
        count_res = await db.execute(select(func.count()).select_from(User))
        user_count = count_res.scalar()
        is_first = user_count == 0

        plan = "unlimited" if is_first else body.plan
        role = "admin" if is_first else "user"

        password_hash = _bcrypt.hashpw(body.password.encode()[:72], _bcrypt.gensalt()).decode()
        user = User(
            email=body.email.lower().strip(),
            password_hash=password_hash,
            role=role,
            plan=plan,
        )
        db.add(user)
        await db.flush()

        # Auto-generate and mark a license key as used for this user
        key = await _auto_create_license(body.plan)
        lic = await db.get(LicenseKey, key)
        if lic:
            from datetime import datetime, timezone
            lic.used_by_user_id = user.id
            lic.used_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(user)

    token = create_token(user.id, user.role)
    from api.auth import _serialize_user
    return {"token": token, "user": _serialize_user(user)}
