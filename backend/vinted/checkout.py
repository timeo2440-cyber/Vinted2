import asyncio
import logging
from dataclasses import dataclass
from typing import Optional
from vinted.client import VintedClient
from vinted.cart import add_to_cart
from vinted.exceptions import VintedCheckoutError, VintedItemUnavailable

logger = logging.getLogger("vinted.checkout")


@dataclass
class PurchaseResult:
    success: bool
    item_id: str
    transaction_id: Optional[str] = None
    price_paid: Optional[float] = None
    error: Optional[str] = None


# Keywords that identify relay/pickup shipping options
_RELAY_KEYWORDS = ["relais", "relay", "pickup", "point", "mondial", "dpd", "locker", "retrait", "chronopost"]


async def get_shipping_options(client: VintedClient, transaction_id: str) -> list[dict]:
    """Get available shipping options for a transaction."""
    try:
        data = await client.get(f"/transactions/{transaction_id}/shipping_options")
        return data.get("shipping_options") or data.get("options") or []
    except Exception as e:
        raise VintedCheckoutError(f"Failed to get shipping options: {e}") from e


async def select_shipping(client: VintedClient, transaction_id: str, option_id: str) -> dict:
    """Select a shipping option for a transaction."""
    try:
        return await client.patch(
            f"/transactions/{transaction_id}",
            json={"transaction": {"shipping_option_id": option_id}},
        )
    except Exception as e:
        raise VintedCheckoutError(f"Failed to select shipping: {e}") from e


async def get_payment_methods(client: VintedClient, transaction_id: str) -> list[dict]:
    """Get available payment methods for a transaction."""
    try:
        data = await client.get(f"/transactions/{transaction_id}/payment_methods")
        return data.get("payment_methods") or []
    except Exception as e:
        raise VintedCheckoutError(f"Failed to get payment methods: {e}") from e


async def get_pickup_points(
    client: VintedClient,
    transaction_id: str,
    postal_code: str = "",
    country: str = "FR",
) -> list[dict]:
    """Get relay/pickup points near a postal code for a transaction."""
    params: dict = {}
    if postal_code:
        params["postal_code"] = postal_code
    if country:
        params["country_code"] = country.upper()

    # Try multiple possible Vinted endpoints for pickup points
    endpoints = [
        f"/transactions/{transaction_id}/pickup_points",
        f"/transactions/{transaction_id}/shipping_options/pickup_points",
        f"/pickup_points",
    ]
    for endpoint in endpoints:
        try:
            data = await client.get(endpoint, params=params)
            points = data.get("pickup_points") or data.get("locations") or data.get("points") or []
            if points:
                return points
        except Exception:
            continue
    return []


async def _select_shipping_with_relay(
    client: VintedClient,
    transaction_id: str,
    account_info: Optional[dict],
) -> None:
    """
    Select shipping option, preferring a relay point if the account has an address.
    Falls back to cheapest option if relay selection fails.
    """
    try:
        options = await get_shipping_options(client, transaction_id)
    except Exception:
        return

    if not options:
        return

    address = (account_info or {}).get("default_address") or {}
    postal_code = str(address.get("postal_code") or address.get("zip") or "").strip()
    country = str(address.get("country") or address.get("country_code") or "FR").upper()

    # If account has an address, try to find a relay point option
    if postal_code:
        relay_option = None
        for opt in options:
            name = (
                opt.get("title") or opt.get("name") or
                opt.get("type") or opt.get("carrier") or ""
            ).lower()
            if any(kw in name for kw in _RELAY_KEYWORDS):
                relay_option = opt
                break

        if relay_option:
            try:
                relay_id = str(relay_option.get("id", ""))
                await select_shipping(client, transaction_id, relay_id)
                logger.info(f"Relay shipping selected: {relay_option.get('title', relay_id)}")
                await asyncio.sleep(0.3)

                # Try to select a specific pickup point near the address
                pickup_points = await get_pickup_points(
                    client, transaction_id,
                    postal_code=postal_code,
                    country=country,
                )
                if pickup_points:
                    nearest = pickup_points[0]
                    point_id = nearest.get("id") or nearest.get("code") or nearest.get("external_id")
                    if point_id:
                        try:
                            await client.patch(
                                f"/transactions/{transaction_id}",
                                json={"transaction": {"pickup_point_id": str(point_id)}},
                            )
                            logger.info(
                                f"Pickup point selected: {nearest.get('name', point_id)} "
                                f"({nearest.get('address', '')})"
                            )
                        except Exception as e:
                            logger.warning(f"Could not select pickup point: {e}")
                else:
                    logger.info("No pickup points found near address — relay option kept without specific point")
                return
            except Exception as e:
                logger.warning(f"Relay shipping selection failed: {e}, falling back to cheapest")

    # Default: cheapest option
    try:
        def _price(o):
            p = o.get("price")
            if isinstance(p, dict):
                return float(p.get("amount", 999) or 999)
            return float(p or 999)

        cheapest = min(options, key=_price)
        await select_shipping(client, transaction_id, str(cheapest.get("id", "")))
        logger.info(f"Cheapest shipping selected: {cheapest.get('title', '')} ({_price(cheapest)}€)")
    except Exception as e:
        logger.warning(f"Could not select cheapest shipping: {e}")


def _find_best_payment_method(
    methods: list[dict],
    payment_card: Optional[dict],
) -> Optional[str]:
    """
    Find the best payment method ID from the list.
    Priority:
    1. Card matching the stored payment_card (by last 4 digits)
    2. Any card-type method
    3. Wallet / balance
    4. First available
    """
    if not methods:
        return None

    stored_last4 = ""
    if payment_card and payment_card.get("number"):
        stored_last4 = str(payment_card["number"]).replace(" ", "")[-4:]

    # 1. Exact card match by last 4 digits
    if stored_last4:
        for m in methods:
            last4 = str(m.get("last4") or m.get("last_four") or "")
            if last4 == stored_last4:
                logger.info(f"Matched stored card (last4={stored_last4}): {m.get('id')}")
                return str(m.get("id", ""))

    # 2. Any card-type method
    for m in methods:
        mtype = (m.get("type") or m.get("kind") or "").lower()
        if any(k in mtype for k in ("card", "credit", "debit", "carte")):
            logger.info(f"Using card method: {m.get('id')} ({m.get('type')})")
            return str(m.get("id", ""))

    # 3. Wallet / balance
    for m in methods:
        mtype = (m.get("type") or m.get("kind") or "").lower()
        if any(k in mtype for k in ("wallet", "balance", "solde", "portefeuille")):
            logger.info(f"Using wallet method: {m.get('id')}")
            return str(m.get("id", ""))

    # 4. First available
    logger.info(f"Using first payment method: {methods[0].get('id')}")
    return str(methods[0].get("id", ""))


async def full_purchase_flow(
    client: VintedClient,
    item_id: str,
    account_info: Optional[dict] = None,
) -> PurchaseResult:
    """
    Complete purchase flow:
    1. Add to cart
    2. Select shipping (relay point near address if available, else cheapest)
    3. Select payment (stored card if available, else best available)
    4. Finalize purchase
    """
    # Step 1: Add to cart / initiate transaction
    try:
        transaction = await add_to_cart(client, item_id)
    except VintedItemUnavailable as e:
        return PurchaseResult(success=False, item_id=item_id, error=str(e))
    except Exception as e:
        return PurchaseResult(success=False, item_id=item_id, error=f"Cart error: {e}")

    transaction_id = str(transaction.get("id", ""))
    if not transaction_id:
        return PurchaseResult(success=False, item_id=item_id, error="No transaction ID returned")

    await asyncio.sleep(0.3)

    # Step 2: Select shipping (relay point if account has address, else cheapest)
    await _select_shipping_with_relay(client, transaction_id, account_info)

    await asyncio.sleep(0.2)

    # Step 3: Get and select payment method
    payment_method_id = None
    try:
        methods = await get_payment_methods(client, transaction_id)
        payment_card = (account_info or {}).get("payment_card")
        payment_method_id = _find_best_payment_method(methods, payment_card)
    except Exception as e:
        logger.warning(f"Could not get payment methods: {e}")

    await asyncio.sleep(0.2)

    # Step 4: Finalize
    try:
        payload: dict = {}
        if payment_method_id:
            payload["payment_method_id"] = payment_method_id

        result = await client.post(f"/transactions/{transaction_id}/finalize", json=payload)

        price_paid = None
        tx = result.get("transaction") or result
        if isinstance(tx, dict):
            p = tx.get("total_price") or tx.get("price")
            if isinstance(p, dict):
                price_paid = float(p.get("amount", 0))
            elif p:
                price_paid = float(p)

        return PurchaseResult(
            success=True,
            item_id=item_id,
            transaction_id=transaction_id,
            price_paid=price_paid,
        )
    except Exception as e:
        return PurchaseResult(
            success=False,
            item_id=item_id,
            transaction_id=transaction_id,
            error=f"Finalize error: {e}",
        )
