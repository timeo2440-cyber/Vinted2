import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, func as sa_func
from database import AsyncSessionLocal, Purchase, ActivityLog, Setting
from vinted.client import VintedClient
from vinted.checkout import full_purchase_flow
from vinted.exceptions import VintedAuthError
from ws.manager import WebSocketManager


class BuyEngine:
    def __init__(self, client: VintedClient, ws_manager: WebSocketManager):
        self.client = client
        self.ws = ws_manager
        self._buy_lock = asyncio.Lock()
        self._bought_this_session: set[str] = set()

    async def attempt_buy(self, item: dict, matched_filter) -> None:
        """
        Attempt to auto-buy an item matching a filter.
        Guards: already bought, session buy, per-filter budget cap, global hourly limit.
        """
        item_id = item.get("id", "")

        # Guard: already bought in this session
        if item_id in self._bought_this_session:
            return

        def get_attr(attr, default=None):
            if isinstance(matched_filter, dict):
                return matched_filter.get(attr, default)
            return getattr(matched_filter, attr, default)

        filter_id = get_attr("id")
        filter_name = get_attr("name", "Unknown")

        # Guard: auto_buy must be enabled
        if not get_attr("auto_buy", False):
            return

        async with AsyncSessionLocal() as db:
            # Guard: per-filter daily budget
            if not await self._check_budget(db, filter_id, get_attr("max_budget")):
                await self._log(db, "warn", f"Budget dépassé pour le filtre '{filter_name}', article ignoré: {item.get('title')}", "buy")
                return

            # Guard: global hourly purchase limit
            if not await self._check_hourly_global_limit(db):
                await self._log(db, "warn", f"Limite horaire d'achats atteinte, article ignoré: {item.get('title')}", "buy")
                return

        # Acquire lock — one purchase at a time
        async with self._buy_lock:
            # Double-check after acquiring lock
            if item_id in self._bought_this_session:
                return

            await self.ws.broadcast_buy_attempt(item_id, filter_id)
            await self.ws.broadcast_log("info", f"Tentative d'achat: {item.get('title')} ({item.get('price')}€)", "buy")

            # Record pending purchase
            async with AsyncSessionLocal() as db:
                purchase = Purchase(
                    filter_id=filter_id,
                    vinted_item_id=item_id,
                    item_title=item.get("title"),
                    price=item.get("price"),
                    status="pending",
                )
                db.add(purchase)
                await db.commit()
                await db.refresh(purchase)
                purchase_id = purchase.id

            # Execute purchase
            result = await full_purchase_flow(self.client, item_id)

            # Update DB record
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
        """Return True if spending on this filter in the last 24h is under max_budget."""
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
        """Return True if global hourly purchase count is below the max_buy_per_hour setting."""
        # Load setting
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
        count = result.scalar() or 0
        return count < max_per_hour

    async def _log(self, db, level: str, message: str, category: str) -> None:
        log = ActivityLog(level=level, category=category, message=message)
        db.add(log)
        await db.commit()
