import base64
import json
import logging
import random
from datetime import datetime, timezone
from typing import Optional
from vinted.client import VintedClient
from database import AsyncSessionLocal, Account
from sqlalchemy import select

logger = logging.getLogger("vinted.account_manager")


class AccountManager:
    """
    Manages a pool of VintedClient instances, one per authenticated account.
    Automatically logs in accounts using Playwright if cookies are missing.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url
        # account_id → {"client": VintedClient, "user_id": int}
        self._clients: dict[int, dict] = {}

    async def initialize(self) -> None:
        """Load all active accounts, auto-login those missing cookies."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Account).where(Account.is_active == True)
            )
            accounts = result.scalars().all()

        for account in accounts:
            if account.cookies:
                # Already has cookies — load directly
                await self._load_client(account)
            elif account.password_enc:
                # Has password but no cookies — auto-login via browser
                logger.info(f"Account {account.email}: no cookies, auto-login via browser…")
                await self._auto_login_and_load(account)
            else:
                logger.warning(f"Account {account.email}: no cookies and no password — skipping")

    async def _auto_login_and_load(self, account) -> bool:
        """Login via Playwright browser and store cookies in DB."""
        try:
            password = base64.b64decode(account.password_enc.encode()).decode()
        except Exception:
            logger.error(f"Account {account.email}: cannot decode password")
            return False

        from vinted.browser_login import login_via_browser
        result = await login_via_browser(self.base_url, account.email, password)

        if not result["success"]:
            logger.error(f"Account {account.email}: browser login failed — {result['error']}")
            # Ne pas marquer comme expiré — l'utilisateur peut corriger son mot de passe
            # On garde is_authenticated=True pour ne pas bloquer l'interface
            return False

        # Save cookies to DB
        async with AsyncSessionLocal() as db:
            acc = await db.get(Account, account.id)
            if acc:
                acc.cookies = json.dumps(result["cookies"])
                acc.csrf_token = result["csrf_token"]
                acc.is_authenticated = True
                acc.last_login = datetime.now(timezone.utc)
                if result["user_id"]:
                    acc.vinted_user_id = result["user_id"]
                if result["username"]:
                    acc.vinted_username = result["username"]
                await db.commit()
                await db.refresh(acc)
                await self._load_client(acc)

        logger.info(f"Account {account.email}: browser login success ✓")
        return True

    async def _load_client(self, account) -> VintedClient:
        if account.id in self._clients:
            try:
                await self._clients[account.id]["client"].close()
            except Exception:
                pass

        client = VintedClient(self.base_url)
        await client.__aenter__()

        if account.cookies:
            try:
                cookies = json.loads(account.cookies)
                client.set_cookies(cookies)
            except Exception:
                pass

        if account.csrf_token:
            client.set_csrf_token(account.csrf_token)

        self._clients[account.id] = {"client": client, "user_id": account.user_id}
        return client

    async def refresh_account(self, account_id: int) -> None:
        async with AsyncSessionLocal() as db:
            account = await db.get(Account, account_id)

        if not account or not account.is_active:
            await self.remove_account(account_id)
            return

        if account.cookies:
            await self._load_client(account)
        elif account.password_enc:
            await self._auto_login_and_load(account)

    async def relogin_account(self, account_id: int) -> dict:
        """Force re-login for an account (called when session expires)."""
        async with AsyncSessionLocal() as db:
            account = await db.get(Account, account_id)

        if not account or not account.password_enc:
            return {"success": False, "error": "Mot de passe non enregistré"}

        # Clear old cookies first
        async with AsyncSessionLocal() as db:
            acc = await db.get(Account, account_id)
            if acc:
                acc.cookies = None
                acc.csrf_token = None
                await db.commit()

        success = await self._auto_login_and_load(account)
        return {"success": success}

    async def remove_account(self, account_id: int) -> None:
        if account_id in self._clients:
            try:
                await self._clients[account_id]["client"].close()
            except Exception:
                pass
            del self._clients[account_id]

    def get_client(self, account_id: int) -> Optional[VintedClient]:
        entry = self._clients.get(account_id)
        return entry["client"] if entry else None

    def get_random_client_for_user(self, user_id: int) -> Optional[tuple[int, VintedClient]]:
        """Return (account_id, client) for a random active account of user_id."""
        user_accounts = [
            (acc_id, entry["client"])
            for acc_id, entry in self._clients.items()
            if entry["user_id"] == user_id
        ]
        if not user_accounts:
            return None
        return random.choice(user_accounts)

    def get_random_client(self) -> Optional[tuple[int, VintedClient]]:
        if not self._clients:
            return None
        acc_id = random.choice(list(self._clients.keys()))
        return acc_id, self._clients[acc_id]["client"]

    def has_clients(self) -> bool:
        return bool(self._clients)

    async def close_all(self) -> None:
        for entry in list(self._clients.values()):
            try:
                await entry["client"].close()
            except Exception:
                pass
        self._clients.clear()
