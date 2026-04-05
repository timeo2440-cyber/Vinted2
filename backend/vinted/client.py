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

# Rotate between recent Chrome versions — newest first for better CF bypass
CHROME_VERSIONS = ["chrome131", "chrome124", "chrome120"]

# Realistic browser Accept headers
_ACCEPT_HTML = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
_ACCEPT_JSON = "application/json, text/plain, */*"
_ACCEPT_LANG = "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"


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
            timeout=30,
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
        headers.setdefault("Accept", _ACCEPT_JSON)
        headers.setdefault("Accept-Language", _ACCEPT_LANG)
        headers.setdefault("Accept-Encoding", "gzip, deflate, br")
        headers.setdefault("Referer", f"{self.base_url}/catalog")
        headers.setdefault("Origin", self.base_url)
        headers.setdefault("X-Requested-With", "XMLHttpRequest")
        headers.setdefault("Sec-Fetch-Dest", "empty")
        headers.setdefault("Sec-Fetch-Mode", "cors")
        headers.setdefault("Sec-Fetch-Site", "same-origin")
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
            # Distinguish real Vinted auth errors from Cloudflare blocks.
            # Cloudflare returns HTML; Vinted returns JSON.
            content_type = response.headers.get("Content-Type", "")
            body_text = response.text or ""
            is_cloudflare = (
                "text/html" in content_type
                or "<html" in body_text[:200].lower()
                or "cloudflare" in body_text[:500].lower()
            )
            if is_cloudflare:
                raise VintedNetworkError(f"Cloudflare block: {response.status_code}")
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
        Retries up to 3 times with a new session on failure.
        """
        for _attempt in range(3):
            result = await self._fetch_csrf_token_once()
            if result:
                return result
            # Rebuild session with a different Chrome version before retrying
            if self._session:
                try:
                    await self._session.close()
                except Exception:
                    pass
            self._impersonate = random.choice(CHROME_VERSIONS)
            self._session = self._build_session()
            await asyncio.sleep(5)
        return None

    async def _fetch_csrf_token_once(self) -> Optional[str]:
        await self._ensure_session()
        try:
            resp = await self._session.get(
                self.base_url,
                headers={
                    "Accept": _ACCEPT_HTML,
                    "Accept-Language": _ACCEPT_LANG,
                    "Accept-Encoding": "gzip, deflate, br",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Cache-Control": "max-age=0",
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
