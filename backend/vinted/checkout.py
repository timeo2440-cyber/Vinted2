import asyncio
from dataclasses import dataclass
from typing import Optional
from vinted.client import VintedClient
from vinted.cart import add_to_cart
from vinted.exceptions import VintedCheckoutError, VintedItemUnavailable


@dataclass
class PurchaseResult:
    success: bool
    item_id: str
    transaction_id: Optional[str] = None
    price_paid: Optional[float] = None
    error: Optional[str] = None


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


async def finalize_purchase(
    client: VintedClient,
    transaction_id: str,
    payment_method_id: Optional[str] = None,
) -> dict:
    """Execute the final purchase."""
    payload: dict = {}
    if payment_method_id:
        payload["payment_method_id"] = payment_method_id

    try:
        return await client.post(f"/transactions/{transaction_id}/finalize", json=payload)
    except Exception as e:
        raise VintedCheckoutError(f"Failed to finalize purchase: {e}") from e


async def full_purchase_flow(
    client: VintedClient,
    item_id: str,
    preferred_shipping: str = "cheapest",
) -> PurchaseResult:
    """
    Complete purchase flow:
    add_to_cart → select cheapest shipping → finalize purchase
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

    # Step 2: Select shipping
    try:
        options = await get_shipping_options(client, transaction_id)
        if options:
            # Pick cheapest option
            cheapest = min(options, key=lambda o: float(o.get("price", {}).get("amount", 999) if isinstance(o.get("price"), dict) else o.get("price", 999) or 999))
            await select_shipping(client, transaction_id, str(cheapest.get("id", "")))
    except Exception as e:
        # Non-fatal: proceed without explicit shipping selection
        pass

    await asyncio.sleep(0.2)

    # Step 3: Get payment methods
    payment_method_id = None
    try:
        methods = await get_payment_methods(client, transaction_id)
        if methods:
            # Prefer Vinted wallet / balance
            for m in methods:
                mtype = m.get("type") or m.get("kind") or ""
                if "wallet" in mtype.lower() or "balance" in mtype.lower():
                    payment_method_id = str(m.get("id", ""))
                    break
            if not payment_method_id:
                payment_method_id = str(methods[0].get("id", ""))
    except Exception:
        pass

    await asyncio.sleep(0.2)

    # Step 4: Finalize
    try:
        result = await finalize_purchase(client, transaction_id, payment_method_id)
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
