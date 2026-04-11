"""
Playwright-based Vinted login.
Logs into Vinted with email/password via a real headless Chromium browser,
bypassing Cloudflare and 2FA challenges automatically.
"""
import asyncio
import logging
from typing import Optional
from urllib.parse import unquote

logger = logging.getLogger("vinted.browser_login")

# Vinted login page selectors (multiple fallbacks for robustness)
_EMAIL_SELECTORS = [
    'input[name="user[login]"]',
    'input[id="username"]',
    'input[type="email"]',
    'input[placeholder*="mail" i]',
    'input[autocomplete="email"]',
]
_PASSWORD_SELECTORS = [
    'input[name="user[password]"]',
    'input[id="password"]',
    'input[type="password"]',
    'input[placeholder*="mot de passe" i]',
    'input[autocomplete="current-password"]',
]
_SUBMIT_SELECTORS = [
    'button[data-testid="submit-button"]',
    'button[type="submit"]',
    'input[type="submit"]',
]


async def _try_fill(page, selectors: list[str], value: str) -> bool:
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.fill(value)
                return True
        except Exception:
            continue
    return False


async def _try_click(page, selectors: list[str]) -> bool:
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.click()
                return True
        except Exception:
            continue
    return False


async def login_via_browser(
    base_url: str,
    email: str,
    password: str,
    timeout_ms: int = 60_000,
) -> dict:
    """
    Log into Vinted using Playwright headless Chromium.

    Returns:
        {
            "success": bool,
            "cookies": dict,       # {name: value}
            "csrf_token": str,
            "user_id": str,
            "username": str,
            "error": str,          # set on failure
        }
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"success": False, "error": "playwright non installé"}

    logger.info(f"Browser login: connecting as {email}…")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
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
                    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8",
                },
            )
            page = await context.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            # 1. Load homepage first to get Cloudflare cookies
            await page.goto(base_url, wait_until="networkidle", timeout=timeout_ms)
            await asyncio.sleep(2)

            # 2. Navigate to login page
            login_url = f"{base_url}/login"
            await page.goto(login_url, wait_until="networkidle", timeout=timeout_ms)
            await asyncio.sleep(1)

            # 3. Fill email
            if not await _try_fill(page, _EMAIL_SELECTORS, email):
                # Maybe login form is in a modal or different route
                await page.goto(f"{base_url}/member/login_form", wait_until="networkidle", timeout=30_000)
                await asyncio.sleep(1)
                if not await _try_fill(page, _EMAIL_SELECTORS, email):
                    await browser.close()
                    return {"success": False, "error": "Champ email introuvable sur la page de connexion"}

            await asyncio.sleep(0.3)

            # 4. Fill password
            if not await _try_fill(page, _PASSWORD_SELECTORS, password):
                await browser.close()
                return {"success": False, "error": "Champ mot de passe introuvable"}

            await asyncio.sleep(0.3)

            # 5. Submit
            if not await _try_click(page, _SUBMIT_SELECTORS):
                # Fallback: press Enter
                await page.keyboard.press("Enter")

            # 6. Wait for navigation (login redirect)
            try:
                await page.wait_for_url(
                    lambda url: "/login" not in url and "/member" not in url,
                    timeout=15_000,
                )
            except Exception:
                pass  # May already be on correct page

            await asyncio.sleep(2)

            # 7. Check for error message on page
            current_url = page.url
            if "/login" in current_url or "/member" in current_url:
                # Still on login page — wrong credentials or blocked
                error_text = ""
                for sel in ['[class*="error"]', '[class*="alert"]', '[role="alert"]']:
                    try:
                        el = page.locator(sel).first
                        if await el.count() > 0:
                            error_text = await el.inner_text()
                            break
                    except Exception:
                        pass
                await browser.close()
                return {
                    "success": False,
                    "error": f"Connexion échouée: {error_text or 'Email ou mot de passe incorrect'}",
                }

            # 8. Extract cookies
            cookies = await context.cookies()
            cookie_dict = {c["name"]: c["value"] for c in cookies}

            # 9. Extract CSRF token
            csrf = ""
            for name in ("XSRF-TOKEN", "xsrf-token"):
                if name in cookie_dict:
                    csrf = unquote(cookie_dict[name])
                    break

            # 10. Try to get user info from the page or API
            user_id = ""
            username = ""
            try:
                resp = await context.request.get(
                    f"{base_url}/api/v2/users/current_user",
                    headers={"Accept": "application/json"},
                )
                if resp.ok:
                    data = await resp.json()
                    user = data.get("user", {})
                    user_id = str(user.get("id", ""))
                    username = user.get("login") or user.get("username") or ""
            except Exception:
                pass

            await browser.close()

            logger.info(
                f"Browser login success: {email} → "
                f"user={username or user_id}, cookies={len(cookie_dict)}"
            )
            return {
                "success": True,
                "cookies": cookie_dict,
                "csrf_token": csrf,
                "user_id": user_id,
                "username": username,
                "error": "",
            }

    except Exception as e:
        logger.error(f"Browser login error for {email}: {e}")
        return {"success": False, "error": str(e)}
