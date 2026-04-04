from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# --- Filter schemas ---

class FilterCreate(BaseModel):
    name: str
    enabled: bool = True
    auto_buy: bool = False
    max_budget: Optional[float] = None
    keywords: Optional[str] = None
    category_ids: Optional[list[int]] = None
    brand_ids: Optional[list[int]] = None
    brand_names: Optional[list[str]] = None
    size_ids: Optional[list[int]] = None
    conditions: Optional[list[str]] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    country_codes: Optional[list[str]] = None


class FilterUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    auto_buy: Optional[bool] = None
    max_budget: Optional[float] = None
    keywords: Optional[str] = None
    category_ids: Optional[list[int]] = None
    brand_ids: Optional[list[int]] = None
    brand_names: Optional[list[str]] = None
    size_ids: Optional[list[int]] = None
    conditions: Optional[list[str]] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    country_codes: Optional[list[str]] = None


class FilterOut(BaseModel):
    id: int
    name: str
    enabled: bool
    auto_buy: bool
    max_budget: Optional[float]
    keywords: Optional[str]
    category_ids: Optional[list[int]]
    brand_ids: Optional[list[int]]
    brand_names: Optional[list[str]]
    size_ids: Optional[list[int]]
    conditions: Optional[list[str]]
    price_min: Optional[float]
    price_max: Optional[float]
    country_codes: Optional[list[str]]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# --- Settings schemas ---

class SettingsUpdate(BaseModel):
    poll_interval_ms: Optional[int] = Field(None, ge=1000, le=30000)
    max_buy_per_hour: Optional[int] = Field(None, ge=1, le=100)


class CookieSubmit(BaseModel):
    cookies: str


class AuthStatus(BaseModel):
    authenticated: bool
    username: Optional[str] = None
    user_id: Optional[str] = None


# --- Purchase schemas ---

class PurchaseOut(BaseModel):
    id: int
    filter_id: Optional[int]
    vinted_item_id: str
    item_title: Optional[str]
    price: Optional[float]
    status: str
    error_message: Optional[str]
    attempted_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# --- Stats schemas ---

class StatsSummary(BaseModel):
    total_seen: int
    total_purchases: int
    successful_purchases: int
    failed_purchases: int
    total_spend: float
    spend_24h: float
    items_per_hour: float


# --- Log schemas ---

class LogOut(BaseModel):
    id: int
    level: str
    category: Optional[str]
    message: str
    payload: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# --- Bot status ---

class BotStatus(BaseModel):
    running: bool
    items_seen: int
    items_matched: int
    poll_interval_ms: int
    authenticated: bool
    uptime_seconds: float
