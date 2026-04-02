import logging
from typing import Optional
from vinted.client import VintedClient
from vinted.exceptions import VintedAuthError, VintedNetworkError

logger = logging.getLogger("vinted.catalog")


def normalize_item(raw: dict) -> dict:
    """Normalize a raw Vinted API item to our internal schema."""
    photo = None
    photos = raw.get("photos") or raw.get("photo")
    if isinstance(photos, list) and photos:
        photo = photos[0].get("url") or photos[0].get("full_size_url")
    elif isinstance(photos, dict):
        photo = photos.get("url") or photos.get("full_size_url")

    # Price
    price_val = raw.get("price")
    if isinstance(price_val, dict):
        price_val = price_val.get("amount") or price_val.get("cents", 0) / 100
    try:
        price_val = float(price_val) if price_val is not None else None
    except (TypeError, ValueError):
        price_val = None

    item_id = str(raw.get("id", ""))
    url = raw.get("url") or f"https://www.vinted.fr/items/{item_id}"

    # Brand
    brand = raw.get("brand_title") or raw.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("title")

    # Size
    size = raw.get("size_title") or raw.get("size")
    if isinstance(size, dict):
        size = size.get("title")

    # Condition
    condition = raw.get("status") or raw.get("condition")
    if isinstance(condition, dict):
        condition = condition.get("title")

    # Category
    category_id = raw.get("catalog_id") or raw.get("category_id")
    if not category_id:
        cat = raw.get("category")
        if isinstance(cat, dict):
            category_id = cat.get("id")

    return {
        "id": item_id,
        "title": raw.get("title", ""),
        "price": price_val,
        "brand": brand,
        "size": size,
        "condition": condition,
        "category_id": category_id,
        "photo_url": photo,
        "item_url": url,
        "seller_id": str(raw.get("user_id", raw.get("seller_id", ""))),
        "country_code": raw.get("country_code") or raw.get("country", {}).get("iso_code"),
        "published_at": raw.get("created_at_ts") or raw.get("created_at"),
        "currency": raw.get("currency"),
    }


async def fetch_newest_items(
    client: VintedClient,
    per_page: int = 96,
    category_ids: Optional[list[int]] = None,
    brand_ids: Optional[list[int]] = None,
    size_ids: Optional[list[int]] = None,
    price_from: Optional[float] = None,
    price_to: Optional[float] = None,
) -> list[dict]:
    """Fetch the newest items from Vinted catalog."""
    params: dict = {
        "order": "newest_first",
        "per_page": per_page,
    }

    if category_ids:
        params["catalog_ids[]"] = category_ids
    if brand_ids:
        params["brand_ids[]"] = brand_ids
    if size_ids:
        params["size_ids[]"] = size_ids
    if price_from is not None:
        params["price_from"] = price_from
    if price_to is not None:
        params["price_to"] = price_to

    try:
        data = await client.get("/catalog/items", params=params)
    except VintedAuthError:
        logger.warning("Catalog fetch: auth error (403/401) — session may need refresh")
        raise
    except VintedNetworkError as e:
        logger.warning(f"Catalog fetch: network error — {e}")
        raise
    except Exception as e:
        logger.error(f"Catalog fetch: unexpected error — {e}")
        raise

    # Detect Cloudflare/unexpected HTML response
    if "raw" in data:
        raw_text = data["raw"][:200] if data.get("raw") else ""
        logger.error(
            f"Catalog API returned non-JSON (Cloudflare? blocked?). "
            f"Preview: {raw_text!r}. "
            f"Fix: paste valid Vinted cookies in Settings."
        )
        return []

    raw_items = data.get("items") or data.get("catalog_items") or []

    if not raw_items:
        keys = list(data.keys())
        logger.warning(f"Catalog API returned 0 items. Response keys: {keys}")

    return [normalize_item(item) for item in raw_items]


async def search_items(
    client: VintedClient,
    query: str,
    per_page: int = 48,
) -> list[dict]:
    """Search items by keyword."""
    params = {
        "search_text": query,
        "order": "newest_first",
        "per_page": per_page,
    }
    data = await client.get("/catalog/items", params=params)
    raw_items = data.get("items") or data.get("catalog_items") or []
    return [normalize_item(item) for item in raw_items]
