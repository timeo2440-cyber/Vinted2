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
    Strategy: click the login button FROM the homepage (already loaded with CF cookies)
    rather than navigating directly to /login (which shows 0 inputs from datacenter IPs).
    """
    submit_selectors = [
        'button[data-testid="submit-button"]',
        'button[data-testid="login-submit"]',
        'button[data-testid="login-form-submit"]',
        'button[type="submit"]',
    ]

    async def dismiss_consent():
        for sel in [
            'button#onetrust-accept-btn-handler',
            'button[data-testid="accept-all-cookies"]',
        ]:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.click(timeout=3000)
                    await asyncio.sleep(0.5)
                    break
            except Exception:
                pass

    async def log_all_inputs(label=""):
        """Log all inputs on the current page."""
        try:
            count = await page.locator('input').count()
            html_len = len(await page.content())
            logger.info(f"DEBUG{' ' + label if label else ''}: {count} inputs, HTML={html_len}b, url={page.url}")
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

    async def wait_for_any_input(timeout_s: int = 15) -> bool:
        """Wait until at least one input appears on the page."""
        for _ in range(timeout_s * 2):
            try:
                if await page.locator('input').count() > 0:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return False

    async def fill_input(locator, value: str, field: str) -> bool:
        """Fill a React input: click → select all → type + dispatch events."""
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

    async def find_input(selectors: list, fallback_type: str = "") -> Optional[object]:
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    return loc
            except Exception:
                pass
        if fallback_type:
            try:
                loc = page.locator(f'input[type="{fallback_type}"]').first
                if await loc.count() > 0:
                    return loc
            except Exception:
                pass
            # Last resort: any visible non-special input — EXCLUDE search bars
            if fallback_type != "password":
                try:
                    inputs = page.locator(
                        'input:not([type="hidden"]):not([type="password"])'
                        ':not([type="checkbox"]):not([type="radio"]):not([type="submit"])'
                        ':not([name="search_text"]):not([id*="search"]):not([name*="search"])'
                    )
                    for i in range(await inputs.count()):
                        el = inputs.nth(i)
                        if await el.is_visible():
                            return el
                except Exception:
                    pass
        return None

    email_selectors = [
        'input[data-testid="username"]',
        'input[data-testid="Username"]',
        'input[name="username"]',
        'input[id="username"]',
        'input[autocomplete="username"]',
        'input[autocomplete="email"]',
        'input[type="email"]',
        'input[name="user[login]"]',
    ]
    password_selectors = [
        'input[data-testid="password"]',
        'input[data-testid="Password"]',
        'input[name="password"]',
        'input[id="password"]',
        'input[autocomplete="current-password"]',
        'input[type="password"]',
        'input[name="user[password]"]',
    ]

    try:
        # ── Strategy 1: click the login button from the homepage (already loaded) ──
        # This avoids navigating directly to /login which shows 0 inputs from DC IPs
        logger.info("DOM login: trying to click login button from homepage…")
        await dismiss_consent()
        await asyncio.sleep(1)

        login_btn_selectors = [
            'a[data-testid="header--loginLink"]',
            'a[data-testid="login-link"]',
            'button[data-testid="login-button"]',
            f'a[href="/login"]',
            f'a[href*="/login"]',
            'button:has-text("Se connecter")',
            'a:has-text("Se connecter")',
            '[class*="Header"] a[href*="login"]',
        ]
        clicked_login = False
        for sel in login_btn_selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible():
                    await el.click(timeout=5000)
                    logger.info(f"Clicked login button via {sel}")
                    clicked_login = True
                    break
            except Exception:
                pass

        if clicked_login:
            await asyncio.sleep(2)

            # Vinted redirects to signup/select_type — now navigate directly to /login
            # (we have proper CF cookies from all the navigation so far)
            if "signup" in page.url or "select_type" in page.url or "/login" not in page.url:
                logger.info(f"On {page.url} — navigating directly to /login with CF cookies…")
                try:
                    await page.goto(f"{base_url}/login", wait_until="networkidle", timeout=25_000)
                except Exception:
                    try:
                        await page.goto(f"{base_url}/login", wait_until="domcontentloaded", timeout=20_000)
                    except Exception as e:
                        logger.debug(f"goto /login after CF: {e}")
                await asyncio.sleep(3)

            # Wait for form inputs to appear
            appeared = await wait_for_any_input(timeout_s=15)
            await asyncio.sleep(1)
            await log_all_inputs("after-click")

            if appeared:
                email_loc = await find_input(email_selectors, fallback_type="email")
                if email_loc and await fill_input(email_loc, email, "Email"):
                    pwd_loc = await find_input(password_selectors, fallback_type="password")
                    if pwd_loc:
                        await fill_input(pwd_loc, password, "Password")
                    else:
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
                                break
                        except Exception:
                            pass
                    if not submitted:
                        await page.keyboard.press("Enter")
                    try:
                        await page.wait_for_url(
                            lambda u: "/login" not in u and "/member" not in u,
                            timeout=15_000,
                        )
                    except Exception:
                        pass
                    await asyncio.sleep(2)
                    current_url = page.url
                    logger.info(f"After login (strategy 1), URL: {current_url}")
                    if "/login" not in current_url and "/member" not in current_url:
                        return {"user_id": "", "username": ""}
                    logger.warning("Strategy 1 failed — trying direct navigation")

        # ── Strategy 2: navigate directly to /login, wait longer for React ──
        logger.info("DOM login: direct navigation to /login with extended wait…")
        for url in [f"{base_url}/login", f"{base_url}/member/login_form"]:
            try:
                await page.goto(url, wait_until="networkidle", timeout=30_000)
            except Exception:
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                except Exception as e:
                    logger.debug(f"goto {url}: {e}")
                    continue

            # Wait up to 15s for React to render inputs
            appeared = await wait_for_any_input(timeout_s=15)
            await dismiss_consent()
            await asyncio.sleep(1)
            await log_all_inputs(f"direct-{url.split('/')[-1]}")

            if not appeared:
                logger.warning(f"No inputs appeared at {url}")
                continue

            email_loc = await find_input(email_selectors, fallback_type="email")
            if not email_loc:
                logger.warning(f"No email input at {url}")
                continue

            if not await fill_input(email_loc, email, "Email"):
                continue

            await asyncio.sleep(0.5)
            pwd_loc = await find_input(password_selectors, fallback_type="password")
            if pwd_loc:
                await fill_input(pwd_loc, password, "Password")
            else:
                await page.keyboard.press("Tab")
                await asyncio.sleep(0.3)
                await page.keyboard.type(password, delay=40)

            await asyncio.sleep(0.5)
            submitted = False
            for sel in submit_selectors:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0:
                        await el.click(timeout=5000)
                        submitted = True
                        break
                except Exception:
                    pass
            if not submitted:
                await page.keyboard.press("Enter")

            try:
                await page.wait_for_url(
                    lambda u: "/login" not in u and "/member" not in u,
                    timeout=15_000,
                )
            except Exception:
                pass

            await asyncio.sleep(2)
            current_url = page.url
            logger.info(f"After login (strategy 2), URL: {current_url}")
            if "/login" not in current_url and "/member" not in current_url:
                return {"user_id": "", "username": ""}

        logger.error("Both DOM login strategies failed")
        return None

    except Exception as e:
        logger.error(f"DOM login failed: {e}")
        return None
