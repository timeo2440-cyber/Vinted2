import httpx
import random
import asyncio
from typing import Optional
from vinted.exceptions import VintedAuthError, VintedRateLimitError, VintedNetworkError

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]


class VintedClient:
    def __init__(self, base_url: str = "https://www.vinted.fr"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api/v2"
        self._user_agent = random.choice(USER_AGENTS)
        self._session: Optional[httpx.AsyncClient] = None
        self._cookies: dict = {}
        self._csrf_token: Optional[str] = None

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=self._default_headers(),
            follow_redirects=True,
            timeout=httpx.Timeout(15.0),
        )

    def _default_headers(self) -> dict:
        return {
            "User-Agent": self._user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "X-Requested-With": "XMLHttpRequest",
            "DNT": "1",
            "Connection": "keep-alive",
        }

    async def __aenter__(self):
        self._session = self._build_client()
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.aclose()
            self._session = None

    def set_cookies(self, cookies: dict) -> None:
        self._cookies = cookies
        if self._session:
            for name, value in cookies.items():
                self._session.cookies.set(name, value, domain=".vinted.fr")

    def set_csrf_token(self, token: str) -> None:
        self._csrf_token = token

    async def _ensure_session(self):
        if not self._session:
            self._session = self._build_client()
            for name, value in self._cookies.items():
                self._session.cookies.set(name, value, domain=".vinted.fr")

    async def request(self, method: str, path: str, **kwargs) -> dict:
        await self._ensure_session()

        # Add jitter to avoid pattern detection
        await asyncio.sleep(random.uniform(0.1, 0.4))

        url = f"{self.api_base}{path}" if path.startswith("/") else path

        headers = kwargs.pop("headers", {})
        if self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token

        try:
            response = await self._session.request(method, url, headers=headers, **kwargs)
        except httpx.TimeoutException as e:
            raise VintedNetworkError(f"Request timeout: {e}") from e
        except httpx.RequestError as e:
            raise VintedNetworkError(f"Request error: {e}") from e

        if response.status_code == 401 or response.status_code == 403:
            raise VintedAuthError(f"Authentication failed: {response.status_code}")

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 30))
            raise VintedRateLimitError(retry_after)

        response.raise_for_status()

        try:
            return response.json()
        except Exception:
            return {"raw": response.text}

    async def get(self, path: str, params: Optional[dict] = None) -> dict:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, json: Optional[dict] = None) -> dict:
        return await self.request("POST", path, json=json)

    async def patch(self, path: str, json: Optional[dict] = None) -> dict:
        return await self.request("PATCH", path, json=json)

    async def fetch_csrf_token(self) -> Optional[str]:
        """Fetch CSRF token from Vinted homepage."""
        await self._ensure_session()
        try:
            resp = await self._session.get(self.base_url)
            # Extract from cookie
            csrf = self._session.cookies.get("XSRF-TOKEN") or self._session.cookies.get("_vinted_fr_session")
            if resp.headers.get("X-CSRF-Token"):
                self._csrf_token = resp.headers["X-CSRF-Token"]
                return self._csrf_token
            return None
        except Exception:
            return None

    async def close(self):
        if self._session:
            await self._session.aclose()
            self._session = None
