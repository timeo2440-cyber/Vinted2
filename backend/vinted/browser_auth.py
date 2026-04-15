"""
Playwright-based Cloudflare bypass for Vinted.
Launches a real headless Chromium browser to solve Cloudflare JS challenges
and obtain valid session cookies — works even from datacenter IPs.
"""
import asyncio
import logging
from typing import Optional
from urllib.parse import unquote

logger = logging.getLogger("vinted.browser_auth")


async def fetch_cookies_via_browser(
    base_url: str = "https://www.vinted.fr",
    timeout_ms: int = 60_000,
) -> Optional[dict]:
    """
    Launch headless Chromium, load Vinted, wait for Cloudflare to clear,
    then return all cookies as a plain dict {name: value}.
    Returns None if playwright is unavailable or the fetch fails.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("playwright not installed — browser auth unavailable")
        return None

    logger.info("Browser auth: launching Chromium to bypass Cloudflare…")
    try:
        from config import settings as _s
        _proxy_url = _s.vinted_proxy_url
    except Exception:
        _proxy_url = ""
    proxy_cfg = {"server": _proxy_url} if _proxy_url else None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                proxy=proxy_cfg,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--no-first-run",
                    "--no-zygote",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                locale="fr-FR",
                viewport={"width": 1280, "height": 720},
                extra_http_headers={
                    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                },
            )

            page = await context.new_page()

            # Hide webdriver flag so Cloudflare doesn't detect automation
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            # Navigate — wait for network idle so CF challenge fully resolves
            try:
                await page.goto(base_url, wait_until="networkidle", timeout=timeout_ms)
            except Exception:
                # Fallback: domcontentloaded is enough to get cookies
                await page.goto(base_url, wait_until="domcontentloaded", timeout=timeout_ms)

            # Give an extra moment for CF to set its cookies
            await asyncio.sleep(3)

            cookies = await context.cookies()
            await browser.close()

        cookie_dict = {c["name"]: c["value"] for c in cookies}

        csrf = None
        for name in ("XSRF-TOKEN", "xsrf-token"):
            if name in cookie_dict:
                csrf = unquote(cookie_dict[name])
                break

        logger.info(
            f"Browser auth: got {len(cookie_dict)} cookies, "
            f"csrf={'yes' if csrf else 'no'}"
        )
        return cookie_dict

    except Exception as e:
        logger.error(f"Browser auth failed: {e}")
        return None
