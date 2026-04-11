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
    2. Try API login via browser context (has valid Cloudflare cookies)
    3. Fall back to DOM-based login
    4. Return the authenticated session cookies

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
            try:
                await page.goto(base_url, wait_until="networkidle", timeout=timeout_ms)
            except Exception:
                await page.goto(base_url, wait_until="domcontentloaded", timeout=timeout_ms)
            await asyncio.sleep(3)

            # Step 2: Get CSRF token from cookies
            all_cookies = await context.cookies()
            cookie_dict = {c["name"]: c["value"] for c in all_cookies}
            csrf = unquote(cookie_dict.get("XSRF-TOKEN") or cookie_dict.get("xsrf-token") or "")
            logger.info(f"Initial cookies: {len(cookie_dict)}, csrf={'yes' if csrf else 'no'}")

            # Step 3: Try API login via browser context (reuses Cloudflare cookies)
            user_id = ""
            username = ""
            api_success = False

            if csrf:
                api_success, user_id, username = await _api_login(
                    context, base_url, email, password, csrf
                )

            # Step 4: Fall back to DOM login
            if not api_success:
                logger.info("Tentative de connexion via formulaire DOM…")
                dom_result = await _dom_login(page, context, base_url, email, password, timeout_ms)
                if not dom_result:
                    await browser.close()
                    return {
                        "success": False,
                        "error": "Connexion échouée — vérifiez email/mot de passe et réessayez",
                    }
                user_id = dom_result.get("user_id", "")
                username = dom_result.get("username", "")

            # Step 5: Collect final cookies (includes session cookies set after login)
            final_cookies = await context.cookies()
            final_cookie_dict = {c["name"]: c["value"] for c in final_cookies}
            final_csrf = unquote(
                final_cookie_dict.get("XSRF-TOKEN") or
                final_cookie_dict.get("xsrf-token") or csrf or ""
            )

            # Step 6: Try to get user info if we don't have it yet
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
                        logger.info(f"User info from API: {username} (id={user_id})")
                except Exception as e:
                    logger.debug(f"current_user fetch: {e}")

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


async def _api_login(context, base_url: str, email: str, password: str, csrf: str) -> tuple:
    """
    Try API-based login using the browser context (which has Cloudflare cookies).
    Returns (success: bool, user_id: str, username: str)
    """
    endpoints = [
        ("/api/v2/users/login", {"login": email, "password": password}),
        ("/api/v2/auth/sign_in", {"user": {"login": email, "password": password}}),
        ("/api/v2/sessions", {"login": email, "password": password, "grant_type": "password"}),
    ]

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf,
        "X-App-Version": "web",
        "Origin": base_url,
        "Referer": f"{base_url}/login",
    }

    for path, payload in endpoints:
        try:
            resp = await context.request.post(
                f"{base_url}{path}",
                data=json.dumps(payload),
                headers=headers,
                timeout=15_000,
            )
            status = resp.status
            logger.info(f"API login {path}: status={status}")

            if status in (200, 201):
                try:
                    data = await resp.json()
                    user = data.get("user") or data.get("data", {}).get("user") or {}
                    if user and user.get("id"):
                        user_id = str(user.get("id", ""))
                        username = user.get("login") or user.get("username") or ""
                        logger.info(f"API login success via {path}: {username} (id={user_id})")
                        return True, user_id, username
                except Exception as e:
                    logger.debug(f"API login {path} parse error: {e}")

            elif status in (401, 403, 422):
                logger.warning(f"API login {path}: credentials rejected (HTTP {status})")
                # Credentials wrong — no point trying DOM
                return False, "", ""

        except Exception as e:
            logger.debug(f"API login {path} error: {e}")

    return False, "", ""


async def _dom_login(page, context, base_url: str, email: str, password: str, timeout_ms: int) -> Optional[dict]:
    """
    Log in by interacting with the Vinted login page DOM.
    React SPA compatible: uses type() with delays and dispatches synthetic events.
    """
    email_selectors = [
        'input[data-testid="username"]',
        'input[name="username"]',
        'input[id="username"]',
        'input[name="user[login]"]',
        'input[data-testid="login-form-username"]',
        'input[autocomplete="username"]',
        'input[autocomplete="email"]',
        'input[type="email"]',
        '[class*="login"] input[type="text"]',
    ]
    password_selectors = [
        'input[data-testid="password"]',
        'input[name="password"]',
        'input[id="password"]',
        'input[name="user[password]"]',
        'input[data-testid="login-form-password"]',
        'input[autocomplete="current-password"]',
        'input[type="password"]',
    ]
    submit_selectors = [
        'button[data-testid="submit-button"]',
        'button[data-testid="login-submit"]',
        'button[data-testid="login-form-submit"]',
        'button[type="submit"]',
        'button:text("Connexion")',
        'button:text("Se connecter")',
    ]
    consent_selectors = [
        'button#onetrust-accept-btn-handler',
        'button[data-testid="accept-all-cookies"]',
        'button[id*="accept"][id*="cookie"]',
    ]

    async def dismiss_consent():
        for sel in consent_selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.click(timeout=3000)
                    await asyncio.sleep(0.5)
                    logger.debug(f"Consent dismissed via {sel}")
                    break
            except Exception:
                pass

    async def wait_and_fill(selector: str, value: str, field_name: str) -> bool:
        """Wait for a field, then fill it using React-compatible typing."""
        try:
            el = page.locator(selector).first
            count = await el.count()
            if not count:
                return False

            # Click to focus the element
            await el.click(timeout=5000)
            await asyncio.sleep(0.2)

            # Select all existing text and delete it
            await page.keyboard.press("Control+a")
            await asyncio.sleep(0.1)
            await page.keyboard.press("Delete")
            await asyncio.sleep(0.1)

            # Type character by character — triggers React onChange events
            await el.type(value, delay=40)
            await asyncio.sleep(0.3)

            # Also dispatch React synthetic events via JavaScript as insurance
            await page.evaluate(
                """([sel, val]) => {
                    const el = document.querySelector(sel);
                    if (!el) return;
                    try {
                        const setter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        ).set;
                        setter.call(el, val);
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                        el.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true}));
                    } catch(e) {}
                }""",
                [selector, value],
            )

            logger.info(f"{field_name} filled via {selector}")
            return True
        except Exception as e:
            logger.debug(f"wait_and_fill({selector}): {e}")
            return False

    try:
        # Try two login URLs
        email_filled = False
        for url in [f"{base_url}/login", f"{base_url}/member/login_form"]:
            try:
                await page.goto(url, wait_until="networkidle", timeout=30_000)
            except Exception:
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                except Exception as e:
                    logger.debug(f"goto {url}: {e}")
                    continue

            await asyncio.sleep(2)
            await dismiss_consent()
            await asyncio.sleep(1)

            # Wait up to 10s for any email selector
            for sel in email_selectors:
                try:
                    await page.wait_for_selector(sel, timeout=5000)
                    logger.info(f"Email field found: {sel}")
                    if await wait_and_fill(sel, email, "Email"):
                        email_filled = True
                        break
                except Exception:
                    pass

            if email_filled:
                break

        if not email_filled:
            logger.error("Email field not found or could not be filled on any login URL")
            return None

        await asyncio.sleep(0.5)

        # Fill password
        password_filled = False
        for sel in password_selectors:
            try:
                if await page.locator(sel).count() > 0:
                    if await wait_and_fill(sel, password, "Password"):
                        password_filled = True
                        break
            except Exception:
                pass

        if not password_filled:
            logger.warning("Password field not found — trying keyboard Tab")
            await page.keyboard.press("Tab")
            await asyncio.sleep(0.3)
            await page.keyboard.type(password, delay=40)

        await asyncio.sleep(0.5)

        # Submit the form
        submitted = False
        for sel in submit_selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.click(timeout=5000)
                    submitted = True
                    logger.info(f"Form submitted via {sel}")
                    break
            except Exception:
                pass

        if not submitted:
            logger.warning("Submit button not found — pressing Enter")
            await page.keyboard.press("Enter")

        # Wait for navigation away from login page
        try:
            await page.wait_for_url(
                lambda url: "/login" not in url and "/member" not in url,
                timeout=15_000,
            )
        except Exception:
            pass

        await asyncio.sleep(2)
        current_url = page.url
        logger.info(f"After login, URL: {current_url}")

        if "/login" in current_url or "/member" in current_url:
            logger.error("Still on login page — credentials wrong or form submission failed")
            return None

        return {"user_id": "", "username": ""}

    except Exception as e:
        logger.error(f"DOM login failed: {e}")
        return None
