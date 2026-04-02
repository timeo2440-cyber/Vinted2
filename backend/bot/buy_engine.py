import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, func as sa_func
from database import AsyncSessionLocal, Purchase, ActivityLog, Setting, Account
from vinted.client import VintedClient
from vinted.checkout import full_purchase_flow
from vinted.exceptions import VintedAuthError
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

    async def attempt_buy(self, item: dict, matched_filter) -> None:
        """
        Attempt to auto-buy an item matching a filter.
        Uses a random account client if available, else primary client.
        """
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

        # Check global autocop toggle
        async with AsyncSessionLocal() as db:
            row = await db.execute(select(Setting).where(Setting.key == "global_autocop"))
            autocop_setting = row.scalar_one_or_none()
            if not autocop_setting or autocop_setting.value.lower() != "true":
                return

        async with AsyncSessionLocal() as db:
            if not await self._check_budget(db, filter_id, get_attr("max_budget")):
                await self._log(db, "warn", f"Budget dépassé pour le filtre '{filter_name}', article ignoré: {item.get('title')}", "buy")
                return
            if not await self._check_hourly_global_limit(db):
                await self._log(db, "warn", f"Limite horaire d'achats atteinte, article ignoré: {item.get('title')}", "buy")
                return

        async with self._buy_lock:
            if item_id in self._bought_this_session:
                return

            # Pick client: random account if available, else primary
            account_id = None
            if self.account_manager and self.account_manager.has_clients():
                pair = self.account_manager.get_random_client()
                if pair:
                    account_id, buy_client = pair
                else:
                    buy_client = self.primary_client
            else:
                buy_client = self.primary_client

            await self.ws.broadcast_buy_attempt(item_id, filter_id)
            await self.ws.broadcast_log("info", f"Tentative d'achat: {item.get('title')} ({item.get('price')}€)", "buy")

            async with AsyncSessionLocal() as db:
                purchase = Purchase(
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
                    # Increment account purchase count
                    if account_id:
                        acc = await db.get(Account, account_id)
                        if acc:
                            acc.purchases_count = (acc.purchases_count or 0) + 1
                            await db.commit()
                    await self._log(db, "success", f"Acheté: {item.get('title')} pour {result.price_paid}€", "buy")
                else:
                    await self._log(db, "error", f"Échec d'achat pour {item.get('title')}: {result.error}", "buy")

            await self.ws.broadcast_buy_result(
                item_id=item_id,
                success=result.success,
                price=result.price_paid,
                error=result.error,
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
        spent = result.scalar() or 0.0
        return spent < max_budget

    async def _check_hourly_global_limit(self, db) -> bool:
        row = await db.execute(select(Setting).where(Setting.key == "max_buy_per_hour"))
        setting = row.scalar_one_or_none()
        if not setting or not setting.value:
            return True
        try:
            max_per_hour = int(setting.value)
        except (ValueError, TypeError):
            return True
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        result = await db.execute(
            select(sa_func.count(Purchase.id)).where(
                Purchase.status == "success",
                Purchase.attempted_at >= cutoff,
            )
        )
        return (result.scalar() or 0) < max_per_hour

    async def _log(self, db, level: str, message: str, category: str) -> None:
        log = ActivityLog(level=level, category=category, message=message)
        db.add(log)
        await db.commit()
