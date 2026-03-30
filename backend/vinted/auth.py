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
    Returns {"authenticated": bool, "username": str|None, "user_id": str|None}
    """
    try:
        data = await client.get("/users/current_user")
        user = data.get("user", {})
        return {
            "authenticated": True,
            "username": user.get("login") or user.get("username"),
            "user_id": str(user.get("id", "")),
        }
    except VintedAuthError:
        return {"authenticated": False, "username": None, "user_id": None}
    except Exception:
        return {"authenticated": False, "username": None, "user_id": None}


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
