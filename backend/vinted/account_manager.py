import json
import random
from typing import Optional
from vinted.client import VintedClient
from database import AsyncSessionLocal, Account
from sqlalchemy import select


class AccountManager:
    """
    Manages a pool of VintedClient instances, one per authenticated account.
    Used by BuyEngine to rotate accounts when purchasing.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url
        self._clients: dict[int, VintedClient] = {}  # account_id -> client

    async def initialize(self) -> None:
        """Load all active + authenticated accounts from DB and create clients."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Account).where(
                    Account.is_active == True,
                    Account.is_authenticated == True,
                )
            )
            accounts = result.scalars().all()
        for account in accounts:
            await self._load_client(account)

    async def _load_client(self, account) -> VintedClient:
        """Create (or replace) the VintedClient for an account."""
        # Close existing client if any
        if account.id in self._clients:
            try:
                await self._clients[account.id].close()
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

        self._clients[account.id] = client
        return client

    async def refresh_account(self, account_id: int) -> None:
        """Reload the client for a specific account (call after login/update)."""
        async with AsyncSessionLocal() as db:
            account = await db.get(Account, account_id)

        if account and account.is_active and account.is_authenticated:
            await self._load_client(account)
        elif account_id in self._clients:
            try:
                await self._clients[account_id].close()
            except Exception:
                pass
            del self._clients[account_id]

    async def remove_account(self, account_id: int) -> None:
        """Remove and close client for a deleted account."""
        if account_id in self._clients:
            try:
                await self._clients[account_id].close()
            except Exception:
                pass
            del self._clients[account_id]

    def get_client(self, account_id: int) -> Optional[VintedClient]:
        return self._clients.get(account_id)

    def get_random_client(self) -> Optional[tuple[int, VintedClient]]:
        """Return (account_id, client) for a random active account, or None."""
        if not self._clients:
            return None
        account_id = random.choice(list(self._clients.keys()))
        return account_id, self._clients[account_id]

    def has_clients(self) -> bool:
        return bool(self._clients)

    async def close_all(self) -> None:
        for client in list(self._clients.values()):
            try:
                await client.close()
            except Exception:
                pass
        self._clients.clear()
