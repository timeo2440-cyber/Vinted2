import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, func as sa_func
from database import AsyncSessionLocal, Purchase, ActivityLog, UserSetting, Account
from vinted.client import VintedClient
from vinted.checkout import full_purchase_flow
from ws.manager import WebSocketManager


class BuyEngine:
    def __init__(self, client: VintedClient, ws_manager: WebSocketManager, account_manager=None):
        self.primary_client = client
        self.account_manager = account_manager
        self.ws = ws_manager
        self._buy_lock = asyncio.Lock()
        self._bought_this_session: set[str] = set()

    def set_account_manager(self, account_manager) -> None:
        self.account_manager = account_manager

    async def attempt_buy(self, item: dict, matched_filter, user_id: int) -> None:
        item_id = item.get("id", "")
        if item_id in self._bought_this_session:
            return

        def get_attr(attr, default=None):
            if isinstance(matched_filter, dict):
                return matched_filter.get(attr, default)
            return getattr(matched_filter, attr, default)

        filter_id = get_attr("id")
        filter_name = get_attr("name", "Unknown")

        if not get_attr("auto_buy", False):
            return

        # Check this user's autocop toggle
        async with AsyncSessionLocal() as db:
            row = await db.execute(
                select(UserSetting).where(
                    UserSetting.user_id == user_id,
                    UserSetting.key == "autocop",
                )
            )
            setting = row.scalar_one_or_none()
            if not setting or setting.value.lower() != "true":
                return

            if not await self._check_budget(db, filter_id, get_attr("max_budget")):
                await self._log(db, "warn",
                    f"Budget dépassé pour le filtre '{filter_name}', article ignoré: {item.get('title')}",
                    "buy", user_id)
                return

            if not await self._check_hourly_limit(db, user_id):
                await self._log(db, "warn",
                    f"Limite horaire atteinte, article ignoré: {item.get('title')}",
                    "buy", user_id)
                return

        async with self._buy_lock:
            if item_id in self._bought_this_session:
                return

            # Use this user's accounts (not another user's)
            account_id = None
            buy_client = self.primary_client
            if self.account_manager and self.account_manager.has_clients():
                pair = self.account_manager.get_random_client_for_user(user_id)
                if pair:
                    account_id, buy_client = pair

            await self.ws.broadcast_buy_attempt(item_id, filter_id, user_id=user_id)
            await self.ws.broadcast_log(
                "info", f"Tentative d'achat: {item.get('title')} ({item.get('price')}€)",
                "buy", user_id=user_id,
            )

            async with AsyncSessionLocal() as db:
                purchase = Purchase(
                    user_id=user_id,
                    filter_id=filter_id,
                    account_id=account_id,
                    vinted_item_id=item_id,
                    item_title=item.get("title"),
                    price=item.get("price"),
                    status="pending",
                )
                db.add(purchase)
                await db.commit()
                await db.refresh(purchase)
                purchase_id = purchase.id

            result = await full_purchase_flow(buy_client, item_id)

            async with AsyncSessionLocal() as db:
                purchase = await db.get(Purchase, purchase_id)
                if purchase:
                    purchase.status = "success" if result.success else "failed"
                    purchase.error_message = result.error
                    purchase.completed_at = datetime.now(timezone.utc)
                    if result.price_paid:
                        purchase.price = result.price_paid
                    await db.commit()

                if result.success:
                    self._bought_this_session.add(item_id)
                    if account_id:
                        acc = await db.get(Account, account_id)
                        if acc:
                            acc.purchases_count = (acc.purchases_count or 0) + 1
                            await db.commit()
                    await self._log(db, "success",
                        f"Acheté: {item.get('title')} pour {result.price_paid}€",
                        "buy", user_id)
                else:
                    await self._log(db, "error",
                        f"Échec d'achat: {item.get('title')}: {result.error}",
                        "buy", user_id)

            await self.ws.broadcast_buy_result(
                item_id=item_id,
                success=result.success,
                price=result.price_paid,
                error=result.error,
                user_id=user_id,
            )

    async def _check_budget(self, db, filter_id: Optional[int], max_budget: Optional[float]) -> bool:
        if not max_budget or not filter_id:
            return True
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        result = await db.execute(
            select(sa_func.sum(Purchase.price)).where(
                Purchase.filter_id == filter_id,
                Purchase.status == "success",
                Purchase.attempted_at >= cutoff,
            )
        )
        return (result.scalar() or 0.0) < max_budget

    async def _check_hourly_limit(self, db, user_id: int) -> bool:
        """Per-user hourly purchase limit."""
        row = await db.execute(
            select(UserSetting).where(
                UserSetting.user_id == user_id,
                UserSetting.key == "max_buy_per_hour",
            )
        )
        setting = row.scalar_one_or_none()
        try:
            max_per_hour = int(setting.value) if setting and setting.value else 5
        except (ValueError, TypeError):
            max_per_hour = 5
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        result = await db.execute(
            select(sa_func.count(Purchase.id)).where(
                Purchase.user_id == user_id,
                Purchase.status == "success",
                Purchase.attempted_at >= cutoff,
            )
        )
        return (result.scalar() or 0) < max_per_hour

    async def _log(self, db, level: str, message: str, category: str, user_id: Optional[int] = None) -> None:
        db.add(ActivityLog(user_id=user_id, level=level, category=category, message=message))
        await db.commit()
