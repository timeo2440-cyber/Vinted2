"""
Playwright-based Vinted login.
Combines Playwright (for Cloudflare bypass) with Vinted's JSON API
to authenticate without scraping the DOM — much more reliable.
"""
import asyncio
import json
import logging
from typing import Optional
from urllib.parse import unquote

logger = logging.getLogger("vinted.browser_login")


async def login_via_browser(
    base_url: str,
    email: str,
    password: str,
    timeout_ms: int = 60_000,
) -> dict:
    """
    Log into Vinted using Playwright + Vinted's API.

    Strategy:
    1. Open Chromium to get valid Cloudflare session cookies
    2. Use those cookies to call Vinted's login API (/api/v2/sessions)
    3. Return the authenticated session cookies

    Returns:
        {
            "success": bool,
            "cookies": dict,
            "csrf_token": str,
            "user_id": str,
            "username": str,
            "error": str,
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

            # Step 1: Navigate to Vinted homepage to solve Cloudflare challenge
            logger.info("Browser login: getting Cloudflare session…")
            await page.goto(base_url, wait_until="networkidle", timeout=timeout_ms)
            await asyncio.sleep(3)

            # Step 2: Get CSRF token from cookies
            all_cookies = await context.cookies()
            cookie_dict = {c["name"]: c["value"] for c in all_cookies}
            csrf = unquote(cookie_dict.get("XSRF-TOKEN") or cookie_dict.get("xsrf-token") or "")

            # Step 3: Try Vinted's login API endpoints
            login_endpoints = [
                f"{base_url}/api/v2/sessions",
                f"{base_url}/api/v2/tokens",
            ]
            login_bodies = [
                json.dumps({"user": {"login": email, "password": password, "remember_me": "true"}}),
                json.dumps({"username": email, "password": password}),
            ]

            user_id = ""
            username = ""
            api_success = False

            for endpoint in login_endpoints:
                for body in login_bodies:
                    try:
                        headers = {
                            "Content-Type": "application/json",
                            "Accept": "application/json, text/plain, */*",
                            "X-CSRF-Token": csrf,
                            "Referer": f"{base_url}/login",
                            "Origin": base_url,
                        }
                        resp = await context.request.post(
                            endpoint,
                            data=body,
                            headers=headers,
                            timeout=30_000,
                        )
                        status = resp.status
                        logger.info(f"Login API {endpoint}: status={status}")

                        if status == 200 or status == 201:
                            try:
                                data = await resp.json()
                                user = data.get("user", {})
                                user_id = str(user.get("id", ""))
                                username = user.get("login") or user.get("username") or ""
                            except Exception:
                                pass
                            api_success = True
                            break
                        elif status == 401:
                            # Wrong credentials
                            await browser.close()
                            return {"success": False, "error": "Email ou mot de passe incorrect"}
                    except Exception as e:
                        logger.debug(f"Login endpoint {endpoint} failed: {e}")
                        continue

                if api_success:
                    break

            if not api_success:
                # Fallback: try DOM-based login
                logger.info("API login failed, trying DOM login…")
                dom_result = await _dom_login(page, context, base_url, email, password, timeout_ms)
                if not dom_result:
                    await browser.close()
                    return {
                        "success": False,
                        "error": "Connexion échouée — vérifiez email/mot de passe et réessayez",
                    }
                user_id = dom_result.get("user_id", "")
                username = dom_result.get("username", "")

            # Step 4: Collect final cookies (includes session cookies set after login)
            final_cookies = await context.cookies()
            final_cookie_dict = {c["name"]: c["value"] for c in final_cookies}
            final_csrf = unquote(
                final_cookie_dict.get("XSRF-TOKEN") or
                final_cookie_dict.get("xsrf-token") or csrf or ""
            )

            # Step 5: Try to get user info if we don't have it yet
            if not user_id:
                try:
                    resp = await context.request.get(
                        f"{base_url}/api/v2/users/current_user",
                        headers={"Accept": "application/json"},
                        timeout=15_000,
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
                f"user={username or user_id}, cookies={len(final_cookie_dict)}"
            )
            return {
                "success": True,
                "cookies": final_cookie_dict,
                "csrf_token": final_csrf,
                "user_id": user_id,
                "username": username,
                "error": "",
            }

    except Exception as e:
        logger.error(f"Browser login error for {email}: {e}")
        return {"success": False, "error": str(e)}


async def _dom_login(page, context, base_url: str, email: str, password: str, timeout_ms: int) -> Optional[dict]:
    """
    Fallback: log in by interacting with the Vinted login page DOM.
    """
    email_selectors = [
        'input[data-testid="username"]',
        'input[name="user[login]"]',
        'input[id="username"]',
        'input[name="username"]',
        'input[type="email"]',
    ]
    password_selectors = [
        'input[data-testid="password"]',
        'input[name="user[password]"]',
        'input[id="password"]',
        'input[name="password"]',
        'input[type="password"]',
    ]
    submit_selectors = [
        'button[data-testid="submit-button"]',
        'button[data-testid="login-submit"]',
        'button[type="submit"]',
    ]
    consent_selectors = [
        'button#onetrust-accept-btn-handler',
        'button[data-testid="accept-all-cookies"]',
    ]

    async def try_fill(selectors, value):
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.fill(value)
                    return True
            except Exception:
                pass
        return False

    async def try_click(selectors):
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.click()
                    return True
            except Exception:
                pass
        return False

    try:
        # Dismiss consent
        for sel in consent_selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.click(timeout=2000)
            except Exception:
                pass

        # Try login URLs
        for url in [f"{base_url}/login", f"{base_url}/member/login_form"]:
            await page.goto(url, wait_until="networkidle", timeout=30_000)
            await asyncio.sleep(1)
            if await try_fill(email_selectors, email):
                break
        else:
            return None

        await try_fill(password_selectors, password)
        await asyncio.sleep(0.3)

        if not await try_click(submit_selectors):
            await page.keyboard.press("Enter")

        try:
            await page.wait_for_url(
                lambda url: "/login" not in url and "/member" not in url,
                timeout=15_000,
            )
        except Exception:
            pass

        await asyncio.sleep(2)
        current_url = page.url
        if "/login" in current_url or "/member" in current_url:
            return None

        return {"user_id": "", "username": ""}

    except Exception as e:
        logger.error(f"DOM login failed: {e}")
        return None
