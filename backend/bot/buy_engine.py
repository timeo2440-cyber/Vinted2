import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, func as sa_func
from database import AsyncSessionLocal, Purchase, ActivityLog
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
        Guards: already bought, session buy, budget cap.
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

        # Guard: budget check
        async with AsyncSessionLocal() as db:
            if not await self._check_budget(db, filter_id, get_attr("max_budget")):
                await self._log(db, "warn", f"Budget exceeded for filter '{filter_name}', skipping {item.get('title')}", "buy")
                return

        # Acquire lock — one purchase at a time
        async with self._buy_lock:
            # Double-check after acquiring lock
            if item_id in self._bought_this_session:
                return

            await self.ws.broadcast_buy_attempt(item_id, filter_id)
            await self.ws.broadcast_log("info", f"Attempting to buy: {item.get('title')} ({item.get('price')}€)", "buy")

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
                    await self._log(db, "success", f"Bought: {item.get('title')} for {result.price_paid}€", "buy")
                else:
                    await self._log(db, "error", f"Buy failed for {item.get('title')}: {result.error}", "buy")

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

    async def _log(self, db, level: str, message: str, category: str) -> None:
        log = ActivityLog(level=level, category=category, message=message)
        db.add(log)
        await db.commit()
