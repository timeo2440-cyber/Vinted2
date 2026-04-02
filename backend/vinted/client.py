"""
Vinted API client using curl_cffi to mimic Chrome TLS fingerprint,
bypassing Cloudflare bot detection transparently.
"""
import random
import asyncio
from typing import Optional
from urllib.parse import unquote

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException, ConnectionError as CurlConnectionError, Timeout as CurlTimeout
from curl_cffi.curl import CurlError

from vinted.exceptions import VintedAuthError, VintedRateLimitError, VintedNetworkError

# Rotate between recent Chrome versions
CHROME_VERSIONS = ["chrome120", "chrome124", "chrome131"]


class VintedClient:
    def __init__(self, base_url: str = "https://www.vinted.fr"):
        self.base_url = base_url.rstrip("/")
        self.api_base = f"{self.base_url}/api/v2"
        self._impersonate = random.choice(CHROME_VERSIONS)
        self._session: Optional[AsyncSession] = None
        self._cookies: dict = {}
        self._csrf_token: Optional[str] = None

    def _build_session(self) -> AsyncSession:
        session = AsyncSession(
            impersonate=self._impersonate,
            verify=True,
            timeout=20,
        )
        for name, value in self._cookies.items():
            session.cookies.set(name, value, domain=".vinted.fr")
        return session

    async def __aenter__(self):
        self._session = self._build_session()
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()
            self._session = None

    def set_cookies(self, cookies: dict) -> None:
        self._cookies = dict(cookies)
        if self._session:
            for name, value in cookies.items():
                self._session.cookies.set(name, value, domain=".vinted.fr")

    def set_csrf_token(self, token: str) -> None:
        self._csrf_token = token

    async def _ensure_session(self):
        if not self._session:
            self._session = self._build_session()

    async def request(self, method: str, path: str, **kwargs) -> dict:
        await self._ensure_session()

        await asyncio.sleep(random.uniform(0.05, 0.3))

        url = f"{self.api_base}{path}" if path.startswith("/") else path

        headers = kwargs.pop("headers", {})
        headers.setdefault("Accept", "application/json, text/plain, */*")
        headers.setdefault("Accept-Language", "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7")
        headers.setdefault("Referer", f"{self.base_url}/catalog")
        headers.setdefault("X-Requested-With", "XMLHttpRequest")
        if self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token

        try:
            response = await self._session.request(
                method, url,
                headers=headers,
                **kwargs,
            )
        except (CurlError, RequestException, CurlConnectionError, CurlTimeout) as e:
            raise VintedNetworkError(f"Request error: {e}") from e
        except Exception as e:
            raise VintedNetworkError(f"Unexpected error: {e}") from e

        if response.status_code in (401, 403):
            raise VintedAuthError(f"Authentication failed: {response.status_code}")

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 30))
            raise VintedRateLimitError(retry_after)

        if response.status_code >= 400:
            raise VintedNetworkError(f"HTTP {response.status_code}")

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
        """
        Load Vinted homepage to get session cookies + CSRF token.
        curl_cffi automatically passes Cloudflare JS challenges via Chrome TLS fingerprint.
        """
        await self._ensure_session()
        try:
            resp = await self._session.get(
                self.base_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Upgrade-Insecure-Requests": "1",
                },
            )

            # Priority 1: response header
            token = resp.headers.get("X-CSRF-Token") or resp.headers.get("x-csrf-token")
            if token:
                self._csrf_token = token
                return self._csrf_token

            # Priority 2: XSRF-TOKEN cookie (URL-encoded on Vinted)
            for name in ("XSRF-TOKEN", "xsrf-token"):
                raw = self._session.cookies.get(name)
                if raw:
                    self._csrf_token = unquote(raw)
                    return self._csrf_token

            # Priority 3: API endpoint
            try:
                api_resp = await self._session.get(
                    f"{self.api_base}/oauth/token_info",
                    headers={"Accept": "application/json, text/plain, */*"},
                )
                t = api_resp.headers.get("X-CSRF-Token", "")
                if t:
                    self._csrf_token = t
                    return self._csrf_token
            except Exception:
                pass

            # Re-check cookie after API call
            for name in ("XSRF-TOKEN", "xsrf-token"):
                raw = self._session.cookies.get(name)
                if raw:
                    self._csrf_token = unquote(raw)
                    return self._csrf_token

            return None
        except Exception:
            return None

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
