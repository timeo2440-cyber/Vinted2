from __future__ import annotations
import secrets
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy import Integer, String, Boolean, Float, DateTime, Text, ForeignKey, func
from config import settings
from pathlib import Path

# Ensure data directory exists
Path(settings.database_url.replace("sqlite+aiosqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ── Plans & limits ────────────────────────────────────────────────────────────
PLAN_LIMITS = {
    "starter":   {"max_accounts": 5,   "max_filters": 999, "auto_buy": False, "price": 10,  "label": "Starter"},
    "pro":       {"max_accounts": 15,  "max_filters": 999, "auto_buy": False, "price": 30,  "label": "Pro"},
    "premium":   {"max_accounts": 50,  "max_filters": 999, "auto_buy": True,  "price": 80,  "label": "Premium"},
    # Plans internes (admin/gratuit)
    "free":      {"max_accounts": 1,   "max_filters": 2,   "auto_buy": False, "price": 0,   "label": "Gratuit"},
    "unlimited": {"max_accounts": 999, "max_filters": 999, "auto_buy": True,  "price": 0,   "label": "Unlimited"},
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user")
    plan: Mapped[str] = mapped_column(String(50), default="free")
    plan_expires_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class LicenseKey(Base):
    __tablename__ = "license_keys"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, default=30)
    used_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    used_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)


class PromoCode(Base):
    __tablename__ = "promo_codes"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)   # 0-100
    plan_override: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)   # force a plan (null = keep chosen)
    max_uses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)           # null = unlimited
    current_uses: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    @staticmethod
    def generate() -> str:
        return secrets.token_urlsafe(32)


class Filter(Base):
    __tablename__ = "filters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_buy: Mapped[bool] = mapped_column(Boolean, default=False)
    max_budget: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brand_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brand_names: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    size_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    country_codes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SeenItem(Base):
    __tablename__ = "seen_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vinted_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(500))
    price: Mapped[Optional[float]] = mapped_column(Float)
    brand: Mapped[Optional[str]] = mapped_column(String(200))
    brand_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    size: Mapped[Optional[str]] = mapped_column(String(100))
    size_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    condition: Mapped[Optional[str]] = mapped_column(String(100))
    condition_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(Text)
    item_url: Mapped[Optional[str]] = mapped_column(Text)
    seller_id: Mapped[Optional[str]] = mapped_column(String(100))
    country_code: Mapped[Optional[str]] = mapped_column(String(10))
    published_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    first_seen_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    filter_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    account_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vinted_item_id: Mapped[str] = mapped_column(String(100), nullable=False)
    item_title: Mapped[Optional[str]] = mapped_column(String(500))
    price: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    attempted_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class UserSetting(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[Optional[str]] = mapped_column(Text)


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    level: Mapped[str] = mapped_column(String(20), default="info")
    category: Mapped[Optional[str]] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(300), nullable=False)
    password_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    cookies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    csrf_token: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    vinted_user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vinted_username: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_authenticated: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)

    default_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preferred_pickup_points: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    ban_suspected: Mapped[bool] = mapped_column(Boolean, default=False)
    purchases_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


async def _run_migrations():
    """SQLite schema migrations — adds columns/tables missing from older DBs."""
    from sqlalchemy import text

    async with engine.begin() as conn:
        async def column_exists(table: str, column: str) -> bool:
            result = await conn.execute(text(f"PRAGMA table_info({table})"))
            return any(row[1] == column for row in result.fetchall())

        async def table_exists(table: str) -> bool:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
                {"t": table},
            )
            return result.fetchone() is not None

        if await table_exists("accounts") and not await column_exists("accounts", "user_id"):
            await conn.execute(text("ALTER TABLE accounts ADD COLUMN user_id INTEGER REFERENCES users(id)"))

        if await table_exists("filters") and not await column_exists("filters", "user_id"):
            await conn.execute(text("ALTER TABLE filters ADD COLUMN user_id INTEGER REFERENCES users(id)"))

        if await table_exists("purchases") and not await column_exists("purchases", "user_id"):
            await conn.execute(text("ALTER TABLE purchases ADD COLUMN user_id INTEGER REFERENCES users(id)"))

        if await table_exists("activity_log") and not await column_exists("activity_log", "user_id"):
            await conn.execute(text("ALTER TABLE activity_log ADD COLUMN user_id INTEGER REFERENCES users(id)"))

        # Add brand_id, size_id, condition_code to seen_items if missing
        if await table_exists("seen_items"):
            if not await column_exists("seen_items", "brand_id"):
                await conn.execute(text("ALTER TABLE seen_items ADD COLUMN brand_id INTEGER"))
            if not await column_exists("seen_items", "size_id"):
                await conn.execute(text("ALTER TABLE seen_items ADD COLUMN size_id INTEGER"))
            if not await column_exists("seen_items", "condition_code"):
                await conn.execute(text("ALTER TABLE seen_items ADD COLUMN condition_code TEXT"))

        # Add brand_names to filters if missing
        if await table_exists("filters"):
            if not await column_exists("filters", "brand_names"):
                await conn.execute(text("ALTER TABLE filters ADD COLUMN brand_names TEXT"))

        # Create promo_codes table if missing (new feature)
        if not await table_exists("promo_codes"):
            await conn.execute(text("""
                CREATE TABLE promo_codes (
                    code TEXT PRIMARY KEY,
                    discount_percent INTEGER DEFAULT 0,
                    plan_override TEXT,
                    max_uses INTEGER,
                    current_uses INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))


async def init_db():
    await _run_migrations()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        admin_res = await session.execute(select(User).where(User.role == "admin").limit(1))
        admin = admin_res.scalar_one_or_none()
        if admin:
            from sqlalchemy import update as sa_update
            for table_cls in (Account, Filter, Purchase, ActivityLog):
                if hasattr(table_cls, "user_id"):
                    await session.execute(
                        sa_update(table_cls)
                        .where(table_cls.user_id == None)
                        .values(user_id=admin.id)
                    )
            await session.commit()

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        defaults = {
            "poll_interval_ms": "2000",
            "max_buy_per_hour": "5",
            "bot_enabled": "false",
            "vinted_cookies": "",
        }
        for key, value in defaults.items():
            result = await session.execute(select(Setting).where(Setting.key == key))
            if not result.scalar_one_or_none():
                session.add(Setting(key=key, value=value))
        await session.commit()

    # Seed default promo codes
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        existing = await session.execute(select(PromoCode).where(PromoCode.code == "BETA"))
        if not existing.scalar_one_or_none():
            session.add(PromoCode(
                code="BETA",
                discount_percent=100,
                plan_override=None,   # keeps the plan the user chose
                max_uses=None,        # unlimited during beta
                is_active=True,
                description="Accès bêta gratuit — tous les plans inclus",
            ))
            await session.commit()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
