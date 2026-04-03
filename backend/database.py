import secrets
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
    "free":      {"max_accounts": 2,   "max_filters": 3,   "auto_buy": False},
    "pro":       {"max_accounts": 10,  "max_filters": 20,  "auto_buy": True},
    "unlimited": {"max_accounts": 999, "max_filters": 999, "auto_buy": True},
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user")        # user / admin
    plan: Mapped[str] = mapped_column(String(50), default="free")        # free / pro / unlimited
    plan_expires_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class LicenseKey(Base):
    __tablename__ = "license_keys"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan: Mapped[str] = mapped_column(String(50), nullable=False)        # pro / unlimited
    duration_days: Mapped[int] = mapped_column(Integer, default=30)
    used_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    used_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)

    @staticmethod
    def generate() -> str:
        return secrets.token_urlsafe(32)


class Filter(Base):
    __tablename__ = "filters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_buy: Mapped[bool] = mapped_column(Boolean, default=False)
    max_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_ids: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON array
    brand_ids: Mapped[str | None] = mapped_column(Text, nullable=True)      # JSON array
    size_ids: Mapped[str | None] = mapped_column(Text, nullable=True)       # JSON array
    conditions: Mapped[str | None] = mapped_column(Text, nullable=True)     # JSON array
    price_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    country_codes: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SeenItem(Base):
    __tablename__ = "seen_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vinted_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    price: Mapped[float | None] = mapped_column(Float)
    brand: Mapped[str | None] = mapped_column(String(200))
    size: Mapped[str | None] = mapped_column(String(100))
    condition: Mapped[str | None] = mapped_column(String(100))
    photo_url: Mapped[str | None] = mapped_column(Text)
    item_url: Mapped[str | None] = mapped_column(Text)
    seller_id: Mapped[str | None] = mapped_column(String(100))
    country_code: Mapped[str | None] = mapped_column(String(10))
    published_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    first_seen_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    filter_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vinted_item_id: Mapped[str] = mapped_column(String(100), nullable=False)
    item_title: Mapped[str | None] = mapped_column(String(500))
    price: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    attempted_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class UserSetting(Base):
    """Per-user settings (autocop, max_buy_per_hour, etc.)"""
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str | None] = mapped_column(Text)


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    level: Mapped[str] = mapped_column(String(20), default="info")
    category: Mapped[str | None] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(300), nullable=False)
    password_enc: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Vinted session
    cookies: Mapped[str | None] = mapped_column(Text, nullable=True)
    csrf_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vinted_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vinted_username: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_authenticated: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)

    # Shipping preferences
    default_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_pickup_points: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    ban_suspected: Mapped[bool] = mapped_column(Boolean, default=False)
    purchases_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


async def _run_migrations(conn):
    """SQLite schema migrations — adds columns/tables missing from older DBs."""
    from sqlalchemy import text

    async def column_exists(table: str, column: str) -> bool:
        result = await conn.execute(text(f"PRAGMA table_info({table})"))
        return any(row[1] == column for row in result.fetchall())

    async def table_exists(table: str) -> bool:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
            {"t": table},
        )
        return result.fetchone() is not None

    # Add user_id to accounts
    if await table_exists("accounts") and not await column_exists("accounts", "user_id"):
        await conn.execute(text("ALTER TABLE accounts ADD COLUMN user_id INTEGER REFERENCES users(id)"))

    # Add user_id to filters
    if await table_exists("filters") and not await column_exists("filters", "user_id"):
        await conn.execute(text("ALTER TABLE filters ADD COLUMN user_id INTEGER REFERENCES users(id)"))

    # Add user_id to purchases
    if await table_exists("purchases") and not await column_exists("purchases", "user_id"):
        await conn.execute(text("ALTER TABLE purchases ADD COLUMN user_id INTEGER REFERENCES users(id)"))

    # Add user_id to activity_log
    if await table_exists("activity_log") and not await column_exists("activity_log", "user_id"):
        await conn.execute(text("ALTER TABLE activity_log ADD COLUMN user_id INTEGER REFERENCES users(id)"))

    await conn.commit()


async def init_db():
    async with engine.begin() as conn:
        # Run migrations before create_all to ensure columns exist
        await _run_migrations(conn)
        await conn.run_sync(Base.metadata.create_all)

    # If no user exists, create a default admin with a random password
    # (user must change it or use the register form — first register = admin)
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(select(User).limit(1))
        if not result.scalar_one_or_none():
            pass  # No default user — first to register via UI becomes admin

        # If there are accounts/filters with NULL user_id, assign them to the first admin
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

    # Insert default global settings if not present
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


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
