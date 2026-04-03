import json
import random
from typing import Optional
from vinted.client import VintedClient
from database import AsyncSessionLocal, Account
from sqlalchemy import select


class AccountManager:
    """
    Manages a pool of VintedClient instances, one per authenticated account.
    Accounts are scoped per user: each user only uses their own accounts.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url
        # account_id → {"client": VintedClient, "user_id": int}
        self._clients: dict[int, dict] = {}

    async def initialize(self) -> None:
        """Load all active + authenticated accounts and create clients."""
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

        if account and account.is_active and account.is_authenticated:
            await self._load_client(account)
        elif account_id in self._clients:
            try:
                await self._clients[account_id]["client"].close()
            except Exception:
                pass
            del self._clients[account_id]

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
        """Return (account_id, client) for a random account belonging to user_id."""
        user_accounts = [
            (acc_id, entry["client"])
            for acc_id, entry in self._clients.items()
            if entry["user_id"] == user_id
        ]
        if not user_accounts:
            return None
        return random.choice(user_accounts)

    def get_random_client(self) -> Optional[tuple[int, VintedClient]]:
        """Return any random client (used by manual buy as fallback)."""
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
