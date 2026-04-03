"""
JWT authentication dependencies for FastAPI.
"""
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import AsyncSessionLocal, User
from config import settings

security = HTTPBearer(auto_error=False)

TOKEN_EXPIRE_DAYS = 30
ALGORITHM = "HS256"


def create_token(user_id: int, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Non authentifié")
    try:
        payload = jwt.decode(
            credentials.credentials, settings.secret_key, algorithms=[ALGORITHM]
        )
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expiré — reconnectez-vous")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalide")

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Compte désactivé ou introuvable")
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès réservé aux administrateurs")
    return user


def check_plan_limit(user: User, resource: str, current_count: int) -> None:
    """Raise 403 if the user's plan doesn't allow adding more of `resource`."""
    from database import PLAN_LIMITS
    limits = PLAN_LIMITS.get(user.plan, PLAN_LIMITS["free"])
    max_val = limits.get(f"max_{resource}", 0)
    if current_count >= max_val:
        plan_name = user.plan.capitalize()
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Limite {plan_name} atteinte ({current_count}/{max_val} {resource}). "
            f"Passez au plan supérieur."
        )
