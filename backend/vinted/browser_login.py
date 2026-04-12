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
    Log into Vinted using Playwright.

    Strategy:
    1. Open Chromium → get Cloudflare session cookies
    2. Try API login via browser context (uses Cloudflare cookies)
    3. Fall back to DOM login (logs all inputs found for debugging)
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

            # Step 2: Get CSRF from cookies AND from page HTML
            all_cookies = await context.cookies()
            cookie_dict = {c["name"]: c["value"] for c in all_cookies}
            csrf = unquote(cookie_dict.get("XSRF-TOKEN") or cookie_dict.get("xsrf-token") or "")

            # Try to extract CSRF from page meta tag or JS state
            if not csrf:
                try:
                    csrf_from_page = await page.evaluate("""
                        () => {
                            const meta = document.querySelector('meta[name="csrf-token"]');
                            if (meta) return meta.getAttribute('content') || '';
                            try {
                                return window.__INITIAL_STATE__?.csrfToken ||
                                       window.gon?.current_user_id && document.cookie.match(/XSRF-TOKEN=([^;]+)/)?.[1] ||
                                       '';
                            } catch(e) { return ''; }
                        }
                    """)
                    if csrf_from_page:
                        csrf = csrf_from_page
                        logger.info("CSRF extracted from page HTML")
                except Exception:
                    pass

            logger.info(f"Initial cookies: {len(cookie_dict)}, csrf={'yes' if csrf else 'no'}")

            # Step 3: Try API login via browser context
            user_id = ""
            username = ""
            api_success = False

            api_success, user_id, username = await _api_login(
                context, base_url, email, password, csrf
            )

            # Step 4: Fall back to DOM login
            if not api_success:
                logger.info("API login failed — trying DOM login…")
                dom_result = await _dom_login(page, context, base_url, email, password, timeout_ms)
                if not dom_result:
                    await browser.close()
                    return {
                        "success": False,
                        "error": "Connexion échouée — vérifiez email/mot de passe et réessayez",
                    }
                user_id = dom_result.get("user_id", "")
                username = dom_result.get("username", "")

            # Step 5: Collect final cookies
            final_cookies = await context.cookies()
            final_cookie_dict = {c["name"]: c["value"] for c in final_cookies}
            final_csrf = unquote(
                final_cookie_dict.get("XSRF-TOKEN") or
                final_cookie_dict.get("xsrf-token") or csrf or ""
            )

            # Step 6: Get user info if missing
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
    Tries with AND without CSRF token.
    Returns (success: bool, user_id: str, username: str)
    """
    endpoints = [
        ("/api/v2/users/login", {"login": email, "password": password}),
        ("/api/v2/auth/sign_in", {"user": {"login": email, "password": password}}),
        ("/api/v2/sessions", {"login": email, "password": password, "grant_type": "password"}),
        ("/api/v2/tokens", {"grant_type": "password", "username": email, "password": password}),
    ]

    base_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-App-Version": "web",
        "Origin": base_url,
        "Referer": f"{base_url}/login",
    }
    if csrf:
        base_headers["X-CSRF-Token"] = csrf

    for path, payload in endpoints:
        try:
            resp = await context.request.post(
                f"{base_url}{path}",
                data=json.dumps(payload),
                headers=base_headers,
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
                logger.warning(f"API login {path}: identifiants refusés (HTTP {status})")
                # Wrong credentials — don't bother with DOM either
                return False, "", ""

        except Exception as e:
            logger.debug(f"API login {path} error: {e}")

    return False, "", ""


async def _dom_login(page, context, base_url: str, email: str, password: str, timeout_ms: int) -> Optional[dict]:
    """
    Log in by interacting with the Vinted login page DOM.
    Logs all inputs found for debugging, uses type-based fallback selection.
    """
    # Known selectors (tried in order)
    email_selectors = [
        'input[data-testid="username"]',
        'input[data-testid="Username"]',
        'input[data-testid="login-form-username"]',
        'input[name="username"]',
        'input[name="user[login]"]',
        'input[id="username"]',
        'input[autocomplete="username"]',
        'input[autocomplete="email"]',
        'input[type="email"]',
    ]
    password_selectors = [
        'input[data-testid="password"]',
        'input[data-testid="Password"]',
        'input[data-testid="login-form-password"]',
        'input[name="password"]',
        'input[name="user[password]"]',
        'input[id="password"]',
        'input[autocomplete="current-password"]',
        'input[type="password"]',
    ]
    submit_selectors = [
        'button[data-testid="submit-button"]',
        'button[data-testid="login-submit"]',
        'button[data-testid="login-form-submit"]',
        'button[type="submit"]',
    ]
    consent_selectors = [
        'button#onetrust-accept-btn-handler',
        'button[data-testid="accept-all-cookies"]',
    ]

    async def dismiss_consent():
        for sel in consent_selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.click(timeout=3000)
                    await asyncio.sleep(0.5)
                    logger.debug(f"Cookie consent dismissed via {sel}")
                    break
            except Exception:
                pass

    async def log_all_inputs():
        """Log all inputs on the page to help debug selector issues."""
        try:
            count = await page.locator('input').count()
            logger.info(f"DEBUG: {count} inputs found on page (url={page.url})")
            for i in range(min(count, 12)):
                try:
                    info = await page.locator('input').nth(i).evaluate("""(e) => ({
                        type: e.type, name: e.name, id: e.id,
                        placeholder: e.placeholder,
                        testid: e.getAttribute('data-testid'),
                        autocomplete: e.autocomplete,
                        visible: e.offsetParent !== null
                    })""")
                    logger.info(
                        f"  input[{i}]: type={info.get('type')!r} name={info.get('name')!r} "
                        f"id={info.get('id')!r} placeholder={info.get('placeholder')!r} "
                        f"testid={info.get('testid')!r} visible={info.get('visible')}"
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"log_all_inputs: {e}")

    async def fill_input(locator, value: str, field: str) -> bool:
        """Fill a React input using type() + synthetic events."""
        try:
            await locator.scroll_into_view_if_needed()
            await locator.click(timeout=5000)
            await asyncio.sleep(0.2)
            await page.keyboard.press("Control+a")
            await asyncio.sleep(0.1)
            await page.keyboard.press("Delete")
            await asyncio.sleep(0.1)
            await locator.type(value, delay=40)
            await asyncio.sleep(0.2)
            # Dispatch React synthetic events
            try:
                await locator.evaluate("""(el, val) => {
                    const setter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value').set;
                    setter.call(el, val);
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                }""", value)
            except Exception:
                pass
            logger.info(f"{field} filled")
            return True
        except Exception as e:
            logger.debug(f"fill_input({field}): {e}")
            return False

    async def find_input_by_selectors(selectors: list) -> Optional[object]:
        """Try selectors in order, return first matching locator."""
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    return loc
            except Exception:
                pass
        return None

    async def find_input_by_type(input_type: str) -> Optional[object]:
        """Fallback: find any visible input of the given type."""
        try:
            loc = page.locator(f'input[type="{input_type}"]').first
            if await loc.count() > 0:
                return loc
        except Exception:
            pass
        return None

    async def find_first_text_input() -> Optional[object]:
        """Fallback: find first visible text-like input (not password/hidden)."""
        try:
            inputs = page.locator('input:not([type="hidden"]):not([type="password"]):not([type="checkbox"]):not([type="radio"]):not([type="submit"])')
            for i in range(await inputs.count()):
                el = inputs.nth(i)
                try:
                    if await el.is_visible():
                        return el
                except Exception:
                    pass
        except Exception:
            pass
        return None

    try:
        # Try two login URLs
        email_found = False
        for url in [f"{base_url}/login", f"{base_url}/member/login_form"]:
            try:
                await page.goto(url, wait_until="networkidle", timeout=30_000)
            except Exception:
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                except Exception as e:
                    logger.debug(f"goto {url}: {e}")
                    continue

            await asyncio.sleep(3)
            await dismiss_consent()
            await asyncio.sleep(1)

            # Log all inputs for debugging
            await log_all_inputs()

            # Try known selectors first
            email_loc = await find_input_by_selectors(email_selectors)

            # Fallback: find by type
            if not email_loc:
                logger.info("Known selectors failed — trying type-based fallback")
                email_loc = await find_input_by_type("email") or await find_first_text_input()

            if email_loc:
                if await fill_input(email_loc, email, "Email"):
                    email_found = True
                    break
            else:
                logger.warning(f"No email input found at {url}")

        if not email_found:
            logger.error("Email field not found or could not be filled on any login URL")
            return None

        await asyncio.sleep(0.5)

        # Fill password
        password_loc = await find_input_by_selectors(password_selectors)
        if not password_loc:
            password_loc = await find_input_by_type("password")

        if password_loc:
            await fill_input(password_loc, password, "Password")
        else:
            logger.warning("Password field not found — Tab + type fallback")
            await page.keyboard.press("Tab")
            await asyncio.sleep(0.3)
            await page.keyboard.type(password, delay=40)

        await asyncio.sleep(0.5)

        # Submit
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
