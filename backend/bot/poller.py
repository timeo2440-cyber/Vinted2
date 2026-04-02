import asyncio
import json
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from database import AsyncSessionLocal, Filter, SeenItem, Setting, ActivityLog
from vinted.client import VintedClient
from vinted.catalog import fetch_newest_items
from vinted.exceptions import VintedAuthError, VintedRateLimitError, VintedNetworkError
from bot.filter_engine import FilterEngine
from bot.buy_engine import BuyEngine
from bot.rate_limiter import AdaptiveRateLimiter
from ws.manager import WebSocketManager


class ItemPoller:
    def __init__(self, client: VintedClient, ws_manager: WebSocketManager, account_manager=None):
        self.client = client
        self.ws = ws_manager
        self.filter_engine = FilterEngine()
        self.buy_engine = BuyEngine(client, ws_manager, account_manager)
        self.rate_limiter = AdaptiveRateLimiter()
        self.running = False
        self.seen_ids: set[str] = set()
        self.items_seen: int = 0
        self.items_matched: int = 0
        self._start_time: Optional[float] = None
        self._task: Optional[asyncio.Task] = None
        self._consecutive_errors: int = 0
        self._max_seen_cache: int = 5000

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        import time
        self._start_time = time.monotonic()
        await self._seed_seen_ids()
        self._task = asyncio.create_task(self._loop())
        await self._log("info", "Bot started", "poller")
        await self.ws.broadcast_bot_status(await self._get_status())

    async def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._log("info", "Bot stopped", "poller")
        await self.ws.broadcast_bot_status(await self._get_status())

    async def _seed_seen_ids(self) -> None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SeenItem.vinted_id).order_by(SeenItem.first_seen_at.desc()).limit(2000)
            )
            for row in result.scalars():
                self.seen_ids.add(row)

    async def _loop(self) -> None:
        while self.running:
            try:
                await self.rate_limiter.acquire()
                await self._poll_cycle()
                self.rate_limiter.on_success()
                self._consecutive_errors = 0
            except VintedAuthError as e:
                self._consecutive_errors += 1
                await self._log("warn", f"Session Vinted expirée, réinitialisation...", "auth")
                # Try to re-init anonymous session before giving up
                try:
                    await self.client.fetch_csrf_token()
                    await self._log("info", "Session Vinted réinitialisée.", "auth")
                except Exception:
                    await self.ws.broadcast_auth_error(str(e))
                await asyncio.sleep(10)
            except VintedRateLimitError as e:
                self._consecutive_errors += 1
                self.rate_limiter.on_rate_limited(e.retry_after)
                await self._log("warn", f"Rate limited. Waiting {e.retry_after}s", "poller")
                await asyncio.sleep(e.retry_after)
            except VintedNetworkError as e:
                self._consecutive_errors += 1
                self.rate_limiter.on_error()
                await self._log("warn", f"Network error: {e}", "poller")
                backoff = min(30, 2 ** min(self._consecutive_errors, 5))
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._consecutive_errors += 1
                self.rate_limiter.on_error()
                await self._log("error", f"Unexpected error: {e}", "poller")
                await asyncio.sleep(5)

    async def _poll_cycle(self) -> None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Filter).where(Filter.enabled == True))
            filters = list(result.scalars().all())
            poll_ms_row = await db.execute(select(Setting).where(Setting.key == "poll_interval_ms"))
            poll_ms_setting = poll_ms_row.scalar_one_or_none()
            poll_interval = int(poll_ms_setting.value) / 1000 if poll_ms_setting and poll_ms_setting.value else 2.0

        items = await fetch_newest_items(self.client, per_page=96)

        new_items = []
        for item in items:
            item_id = item.get("id", "")
            if not item_id or item_id in self.seen_ids:
                continue
            new_items.append(item)
            self.seen_ids.add(item_id)
            if len(self.seen_ids) > self._max_seen_cache:
                excess = len(self.seen_ids) - self._max_seen_cache
                self.seen_ids = set(list(self.seen_ids)[excess:])

        if not new_items:
            return

        self.items_seen += len(new_items)

        async with AsyncSessionLocal() as db:
            for item in new_items:
                existing = await db.execute(
                    select(SeenItem).where(SeenItem.vinted_id == item["id"])
                )
                if not existing.scalar_one_or_none():
                    db.add(SeenItem(
                        vinted_id=item["id"],
                        title=item.get("title"),
                        price=item.get("price"),
                        brand=item.get("brand"),
                        size=item.get("size"),
                        condition=item.get("condition"),
                        photo_url=item.get("photo_url"),
                        item_url=item.get("item_url"),
                        seller_id=item.get("seller_id"),
                        country_code=item.get("country_code"),
                    ))
            await db.commit()

        for item in new_items:
            matched = self.filter_engine.get_matching_filters(item, filters)
            matched_ids = [f.id for f in matched]
            await self.ws.broadcast_new_item(item, matched_ids)
            if matched:
                self.items_matched += 1
                for f in matched:
                    await self.ws.broadcast_item_match(item, f.id, f.name)
                    if f.auto_buy:
                        asyncio.create_task(self.buy_engine.attempt_buy(item, f))

        await asyncio.sleep(max(0, poll_interval - 0.5))

    async def _get_status(self) -> dict:
        import time
        uptime = (time.monotonic() - self._start_time) if self._start_time else 0.0
        async with AsyncSessionLocal() as db:
            poll_ms_row = await db.execute(select(Setting).where(Setting.key == "poll_interval_ms"))
            poll_ms_setting = poll_ms_row.scalar_one_or_none()
            poll_ms = int(poll_ms_setting.value) if poll_ms_setting and poll_ms_setting.value else 2000
        return {
            "running": self.running,
            "items_seen": self.items_seen,
            "items_matched": self.items_matched,
            "poll_interval_ms": poll_ms,
            "uptime_seconds": round(uptime, 1),
        }

    async def get_status(self) -> dict:
        return await self._get_status()

    async def _log(self, level: str, message: str, category: str) -> None:
        await self.ws.broadcast_log(level, message, category)
        async with AsyncSessionLocal() as db:
            db.add(ActivityLog(level=level, category=category, message=message))
            await db.commit()
