import json
import re
from typing import Optional
from vinted.client import VintedClient
from vinted.exceptions import VintedAuthError


def parse_cookie_string(raw: str) -> dict:
    """
    Parse cookies from various formats:
    - "name=value; name2=value2" (header format)
    - JSON dict {"name": "value"}
    - Netscape cookie file format
    """
    if not raw or not raw.strip():
        return {}

    raw = raw.strip()

    # Try JSON first
    if raw.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    # Header format: "name=val; name2=val2"
    cookies = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            name, _, value = part.partition("=")
            cookies[name.strip()] = value.strip()
    return cookies


async def validate_session(client: VintedClient) -> dict:
    """
    Validate the current session by calling /api/v2/users/current_user.
    Returns:
      {"authenticated": True,  "username": ..., "user_id": ...}  — session valide
      {"authenticated": False, "reason": "auth_error"}           — vrai 401/403 Vinted
      {"authenticated": None,  "reason": "network_error"}        — erreur réseau/Cloudflare
    """
    try:
        data = await client.get("/users/current_user")
        user = data.get("user", {})
        # If response has no 'user' key it's probably a Cloudflare HTML page
        if not user:
            return {"authenticated": None, "reason": "network_error"}
        return {
            "authenticated": True,
            "username": user.get("login") or user.get("username"),
            "user_id": str(user.get("id", "")),
        }
    except VintedAuthError:
        return {"authenticated": False, "reason": "auth_error"}
    except Exception:
        return {"authenticated": None, "reason": "network_error"}


async def load_cookies_into_client(client: VintedClient, cookie_string: str) -> bool:
    """
    Parse and load cookies from a raw cookie string into the client.
    Returns True if the session appears valid afterward.
    """
    cookies = parse_cookie_string(cookie_string)
    if not cookies:
        return False
    client.set_cookies(cookies)
    await client.fetch_csrf_token()
    result = await validate_session(client)
    return result["authenticated"]


async def login_with_credentials(base_url: str, email: str, password: str) -> dict:
    """
    Attempt to login to Vinted with email and password.
    Returns {"success": bool, "cookies": str, "csrf_token": str,
             "user_id": str, "username": str, "error": str|None}
    """
    client = VintedClient(base_url)
    await client.__aenter__()
    try:
        # Step 1: Get CSRF token and initial cookies from homepage
        await client.fetch_csrf_token()

        # Step 2: Try Vinted login endpoint
        user = None
        last_error = None

        # Attempt 1: /api/v2/users/login
        try:
            data = await client.post("/users/login", json={
                "login": email,
                "password": password,
                "remember_me": True,
            })
            user = data.get("user") or data.get("data", {}).get("user")
        except VintedAuthError:
            last_error = "Email ou mot de passe incorrect"
        except Exception as e:
            last_error = str(e)

        # Attempt 2: /api/v2/auth/sign_in
        if not user:
            try:
                data = await client.post("/auth/sign_in", json={
                    "user": {"login": email, "password": password}
                })
                user = data.get("user") or data.get("data", {}).get("user")
            except VintedAuthError:
                last_error = "Email ou mot de passe incorrect"
            except Exception as e:
                last_error = str(e)

        if not user or not user.get("id"):
            return {
                "success": False,
                "error": last_error or "Connexion échouée. Essayez d'entrer vos cookies manuellement.",
            }

        cookies_dict = {}
        if client._session:
            cookies_dict = dict(client._session.cookies)

        return {
            "success": True,
            "cookies": json.dumps(cookies_dict),
            "csrf_token": client._csrf_token or "",
            "user_id": str(user["id"]),
            "username": user.get("login") or user.get("username") or email,
            "error": None,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        await client.__aexit__(None, None, None)
