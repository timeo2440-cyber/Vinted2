"""
Proxy endpoints for Vinted brand and category metadata.
Used by the frontend to populate brand/category selectors in the filter form.
"""
from fastapi import APIRouter, Request, Query
from vinted.exceptions import VintedAuthError, VintedNetworkError

router = APIRouter(prefix="/api/vinted", tags=["vinted-meta"])


@router.get("/brands")
async def search_brands(request: Request, q: str = Query(default="", min_length=0)):
    """Search Vinted brands by name. Returns list of {id, title}."""
    client = request.app.state.vinted_client
    if not q.strip():
        return {"brands": []}
    try:
        data = await client.get("/brands", params={"name": q.strip(), "per_page": 20})
        brands = data.get("brands") or []
        return {"brands": [{"id": b["id"], "title": b["title"]} for b in brands if b.get("id") and b.get("title")]}
    except (VintedAuthError, VintedNetworkError):
        return {"brands": []}
    except Exception:
        return {"brands": []}


def _flatten(cats: list, parent: str = "") -> list:
    result = []
    for c in (cats or []):
        if not isinstance(c, dict):
            continue
        cid = c.get("id")
        title = c.get("title") or c.get("name") or ""
        if not (cid and title):
            continue
        full = f"{parent} > {title}" if parent else title
        result.append({"id": cid, "title": title, "full_title": full})
        children = c.get("children") or c.get("subcategories") or []
        result.extend(_flatten(children, full))
    return result


@router.get("/categories")
async def get_categories(request: Request):
    """Return Vinted catalog categories (flattened tree)."""
    client = request.app.state.vinted_client
    try:
        data = await client.get("/catalog/categories")
        cats = (data.get("catalogs") or data.get("catalog_categories")
                or data.get("categories") or [])
        return {"categories": _flatten(cats)}
    except (VintedAuthError, VintedNetworkError):
        return {"categories": []}
    except Exception:
        return {"categories": []}
