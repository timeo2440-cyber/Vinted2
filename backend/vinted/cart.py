from vinted.client import VintedClient
from vinted.exceptions import VintedItemUnavailable, VintedCheckoutError


async def add_to_cart(client: VintedClient, item_id: str) -> dict:
    """
    Initiate a transaction for an item (equivalent to 'Buy' on Vinted).
    Returns transaction data including transaction_id.
    """
    try:
        data = await client.post(f"/items/{item_id}/buy")
    except Exception as e:
        error_msg = str(e).lower()
        if "sold" in error_msg or "reserved" in error_msg or "404" in error_msg:
            raise VintedItemUnavailable(f"Item {item_id} is no longer available")
        raise VintedCheckoutError(f"Failed to add item {item_id} to cart: {e}") from e

    transaction = data.get("transaction") or data
    if not transaction:
        raise VintedCheckoutError(f"Unexpected response when buying item {item_id}")

    return transaction


async def get_open_transactions(client: VintedClient) -> list[dict]:
    """Get all open (pending) transactions."""
    try:
        data = await client.get("/transactions")
        return data.get("transactions") or []
    except Exception:
        return []
