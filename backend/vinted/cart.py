import logging
from vinted.client import VintedClient
from vinted.exceptions import VintedItemUnavailable, VintedCheckoutError, VintedAuthError, VintedNetworkError

logger = logging.getLogger("vinted.cart")


async def add_to_cart(client: VintedClient, item_id: str) -> dict:
    """
    Initiate a transaction for an item (equivalent to 'Buy' on Vinted).
    Returns transaction data including transaction_id.
    """
    try:
        data = await client.post(f"/items/{item_id}/buy")
    except VintedAuthError:
        # Account session expired — raise as-is so buy_engine can handle it
        raise
    except VintedNetworkError as e:
        error_msg = str(e).lower()
        # HTTP 404 = item no longer exists on Vinted
        if "404" in error_msg:
            raise VintedItemUnavailable(f"Article {item_id} introuvable (vendu ou supprimé)")
        raise VintedCheckoutError(f"Erreur réseau lors de l'ajout au panier: {e}") from e
    except Exception as e:
        error_msg = str(e).lower()
        if "sold" in error_msg or "reserved" in error_msg:
            raise VintedItemUnavailable(f"Article {item_id} déjà vendu ou réservé")
        raise VintedCheckoutError(f"Erreur lors de l'ajout au panier: {e}") from e

    # Check for error in response body
    if isinstance(data, dict):
        error = data.get("error") or data.get("message") or ""
        if isinstance(error, str):
            el = error.lower()
            if "sold" in el or "reserved" in el or "unavailable" in el or "vendu" in el:
                raise VintedItemUnavailable(f"Article {item_id} non disponible: {error}")

    transaction = data.get("transaction") or data
    if not transaction:
        raise VintedCheckoutError(f"Réponse inattendue lors de l'achat de l'article {item_id}")

    return transaction


async def get_open_transactions(client: VintedClient) -> list[dict]:
    """Get all open (pending) transactions."""
    try:
        data = await client.get("/transactions")
        return data.get("transactions") or []
    except Exception:
        return []
