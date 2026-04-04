import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from database import AsyncSessionLocal, Filter, SeenItem, Setting, ActivityLog, UserSetting
from vinted.client import VintedClient
from vinted.catalog import fetch_newest_items, search_items
from vinted.exceptions import VintedAuthError, VintedRateLimitError, VintedNetworkError
from bot.filter_engine import FilterEngine
from bot.buy_engine import BuyEngine
from bot.rate_limiter import AdaptiveRateLimiter
from ws.manager import WebSocketManager

logger = logging.getLogger("bot.poller")


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
        self._empty_cycles: int = 0

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        import time
        self._start_time = time.monotonic()
        await self._seed_seen_ids()
        self._task = asyncio.create_task(self._loop())
        await self._log("info", "Bot démarré — scrutation Vinted en cours…", "poller")
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
        await self._log("info", "Bot arrêté.", "poller")
        await self.ws.broadcast_bot_status(await self._get_status())

    async def _seed_seen_ids(self) -> None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SeenItem.vinted_id).order_by(SeenItem.first_seen_at.desc()).limit(2000)
            )
            for row in result.scalars():
                self.seen_ids.add(row)

    async def _loop(self) -> None:
        await self._log("info", "Initialisation de la session Vinted…", "poller")
        csrf = await self.client.fetch_csrf_token()
        if csrf:
            await self._log("info", "Session Vinted initialisée (token CSRF obtenu).", "poller")
        else:
            await self._log("warn",
                "Impossible d'obtenir le token CSRF. "
                "Si le bot ne montre rien, collez des cookies Vinted valides dans Paramètres.",
                "poller")

        while self.running:
            try:
                await self.rate_limiter.acquire()
                await self._poll_cycle()
                self.rate_limiter.on_success()
                self._consecutive_errors = 0
            except VintedAuthError as e:
                self._consecutive_errors += 1
                await self._log("warn",
                    "Erreur d'authentification Vinted (403/401). "
                    "Tentative de réinitialisation de la session…", "auth")
                try:
                    csrf = await self.client.fetch_csrf_token()
                    if csrf:
                        await self._log("info", "Session réinitialisée avec succès.", "auth")
                    else:
                        await self._log("error",
                            "Réinitialisation échouée. "
                            "➜ Copiez vos cookies Vinted dans Paramètres pour débloquer.", "auth")
                        await self.ws.broadcast_auth_error(str(e))
                except Exception as ex:
                    await self._log("error", f"Réinitialisation échouée : {ex}", "auth")
                await asyncio.sleep(15)
            except VintedRateLimitError as e:
                self._consecutive_errors += 1
                self.rate_limiter.on_rate_limited(e.retry_after)
                await self._log("warn", f"Rate-limited par Vinted. Pause {e.retry_after}s…", "poller")
                await asyncio.sleep(e.retry_after)
            except VintedNetworkError as e:
                self._consecutive_errors += 1
                self.rate_limiter.on_error()
                await self._log("warn", f"Erreur réseau : {e}", "poller")
                backoff = min(30, 2 ** min(self._consecutive_errors, 5))
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._consecutive_errors += 1
                self.rate_limiter.on_error()
                await self._log("error", f"Erreur inattendue : {e}", "poller")
                await asyncio.sleep(5)

    def _parse_ids(self, val) -> list:
        """Parse a JSON list of IDs stored as string in the DB."""
        if not val:
            return []
        if isinstance(val, list):
            return val
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    async def _fetch_all_items(self, all_filters: list) -> dict:
        """
        Smart multi-source fetch:
        1. Generic newest items (broad coverage)
        2. One targeted fetch per unique (brand_ids, category_ids) combo
        3. One keyword search per unique keyword string
        Returns a dict {item_id: item} — deduplicated.
        """
        items_map: dict = {}

        def _add(items_list):
            for item in items_list:
                iid = item.get("id")
                if iid:
                    items_map[str(iid)] = item

        # 1. Generic fetch (always)
        try:
            generic = await fetch_newest_items(self.client, per_page=96)
            _add(generic)
        except (VintedAuthError, VintedRateLimitError):
            raise
        except Exception as e:
            await self._log("warn", f"Fetch générique échoué: {e}", "poller")

        if not all_filters:
            return items_map

        # 2. Targeted fetches — collect unique search param sets
        seen_param_keys = set()
        targeted_calls = 0
        MAX_TARGETED = 5  # max extra API calls per cycle to avoid rate limits

        for f in all_filters:
            if targeted_calls >= MAX_TARGETED:
                break

            brand_ids = self._parse_ids(f.brand_ids)
            category_ids = self._parse_ids(f.category_ids)
            size_ids = self._parse_ids(f.size_ids)
            keywords = (f.keywords or "").strip()

            # --- Targeted ID-based fetch ---
            if brand_ids or category_ids or size_ids:
                # Deduplicate identical param combos
                key = (
                    tuple(sorted(brand_ids)),
                    tuple(sorted(category_ids)),
                    tuple(sorted(size_ids)),
                )
                if key not in seen_param_keys:
                    seen_param_keys.add(key)
                    try:
                        await asyncio.sleep(0.3)  # Small delay between calls
                        targeted = await fetch_newest_items(
                            self.client,
                            per_page=48,
                            brand_ids=[int(b) for b in brand_ids] if brand_ids else None,
                            category_ids=[int(c) for c in category_ids] if category_ids else None,
                            size_ids=[int(s) for s in size_ids] if size_ids else None,
                            price_from=f.price_min,
                            price_to=f.price_max,
                        )
                        _add(targeted)
                        targeted_calls += 1
                        logger.debug(
                            f"Targeted fetch (brands={brand_ids}, cats={category_ids}): "
                            f"{len(targeted)} articles"
                        )
                    except (VintedAuthError, VintedRateLimitError):
                        raise
                    except Exception as e:
                        logger.warning(f"Targeted fetch failed: {e}")

            # --- Keyword search ---
            elif keywords:
                kw_key = keywords.lower()
                if kw_key not in seen_param_keys:
                    seen_param_keys.add(kw_key)
                    try:
                        await asyncio.sleep(0.3)
                        kw_items = await search_items(self.client, query=keywords, per_page=48)
                        _add(kw_items)
                        targeted_calls += 1
                        logger.debug(
                            f"Keyword search '{keywords}': {len(kw_items)} articles"
                        )
                    except (VintedAuthError, VintedRateLimitError):
                        raise
                    except Exception as e:
                        logger.warning(f"Keyword search failed: {e}")

        return items_map

    async def _poll_cycle(self) -> None:
        async with AsyncSessionLocal() as db:
            # Load ALL enabled filters from ALL users
            result = await db.execute(select(Filter).where(Filter.enabled == True))
            all_filters = list(result.scalars().all())

            poll_ms_row = await db.execute(select(Setting).where(Setting.key == "poll_interval_ms"))
            poll_ms_setting = poll_ms_row.scalar_one_or_none()
            poll_interval = int(poll_ms_setting.value) / 1000 if poll_ms_setting and poll_ms_setting.value else 2.0

        # Smart multi-source fetch
        items_map = await self._fetch_all_items(all_filters)
        items = list(items_map.values())

        if not items:
            self._empty_cycles += 1
            if self._empty_cycles % 10 == 1:
                await self._log("warn",
                    f"Vinted ne renvoie aucun article ({self._empty_cycles} cycles vides). "
                    "Cause probable : IP bloquée ou cookies expirés. "
                    "➜ Collez des cookies valides dans l'onglet Paramètres.", "poller")
            await asyncio.sleep(poll_interval)
            return

        self._empty_cycles = 0

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
            await asyncio.sleep(poll_interval)
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
                        brand_id=item.get("brand_id"),
                        size=item.get("size"),
                        size_id=item.get("size_id"),
                        condition=item.get("condition"),
                        condition_code=item.get("condition_code"),
                        photo_url=item.get("photo_url"),
                        item_url=item.get("item_url"),
                        seller_id=item.get("seller_id"),
                        country_code=item.get("country_code"),
                    ))
            await db.commit()

        # Match items against filters and broadcast
        cycle_matches = 0
        for item in new_items:
            matched_filter_ids = []
            for f in all_filters:
                if self.filter_engine.match_item(item, f):
                    matched_filter_ids.append(f.id)

            # Broadcast new item counter to all users
            await self.ws.broadcast_new_item(item, matched_filter_ids)

            # Per-user match events + optional auto-buy
            for f in all_filters:
                if self.filter_engine.match_item(item, f):
                    self.items_matched += 1
                    cycle_matches += 1
                    await self.ws.broadcast_item_match(item, f.id, f.name, user_id=f.user_id)
                    if f.auto_buy:
                        async with AsyncSessionLocal() as db:
                            row = await db.execute(
                                select(UserSetting).where(
                                    UserSetting.user_id == f.user_id,
                                    UserSetting.key == "autocop",
                                )
                            )
                            setting = row.scalar_one_or_none()
                        if setting and setting.value.lower() == "true":
                            asyncio.create_task(
                                self.buy_engine.attempt_buy(item, f, user_id=f.user_id)
                            )

        # Log cycle summary (every cycle so the user can see activity)
        if new_items or cycle_matches:
            filters_desc = f"{len(all_filters)} filtre(s)" if all_filters else "aucun filtre"
            await self._log(
                "info" if cycle_matches else "info",
                f"Cycle : {len(new_items)} nouveaux articles scannés"
                + (f", {cycle_matches} correspondance(s) trouvée(s) !" if cycle_matches else f" — 0 correspondance ({filters_desc})"),
                "poller",
            )

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
        logger.log(
            logging.WARNING if level == "warn" else
            logging.ERROR if level == "error" else
            logging.INFO,
            message
        )
        await self.ws.broadcast_log(level, message, category)
        async with AsyncSessionLocal() as db:
            db.add(ActivityLog(level=level, category=category, message=message))
            await db.commit()
