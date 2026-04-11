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


_RELAY_KEYWORDS = ["relais", "relay", "pickup", "point", "mondial", "dpd", "locker", "retrait", "chronopost", "bpost", "inpost"]


async def full_purchase_flow(
    client: VintedClient,
    item_id: str,
    account_info: Optional[dict] = None,
) -> PurchaseResult:
    """
    Complete purchase flow:
    1. Add to cart → get transaction
    2. Select shipping (relay point if address available, else cheapest)
    3. Select payment (stored card or best available)
    4. Finalize
    """

    # ── Step 1: Add to cart ────────────────────────────────────────────────────
    try:
        transaction = await add_to_cart(client, item_id)
    except VintedItemUnavailable as e:
        return PurchaseResult(success=False, item_id=item_id, error=str(e))
    except Exception as e:
        return PurchaseResult(success=False, item_id=item_id, error=f"Erreur panier: {e}")

    transaction_id = str(transaction.get("id", ""))
    if not transaction_id:
        return PurchaseResult(success=False, item_id=item_id, error="Pas d'ID de transaction")

    logger.info(f"Transaction créée: {transaction_id} pour article {item_id}")
    logger.debug(f"Transaction data keys: {list(transaction.keys())}")

    await asyncio.sleep(0.5)

    # ── Step 2: Get shipping options (from transaction or dedicated endpoint) ──
    address = (account_info or {}).get("default_address") or {}
    postal_code = str(address.get("postal_code") or address.get("zip") or "").strip()
    country = str(address.get("country") or address.get("country_code") or "FR").upper()

    # Shipping options may be embedded in the transaction response
    shipping_options = (
        transaction.get("shipping_options") or
        transaction.get("available_shipping_options") or
        []
    )

    if not shipping_options:
        # Try dedicated endpoint
        for endpoint in [
            f"/transactions/{transaction_id}/shipping_options",
            f"/transactions/{transaction_id}",
        ]:
            try:
                data = await client.get(endpoint)
                shipping_options = (
                    data.get("shipping_options") or
                    data.get("available_shipping_options") or
                    (data.get("transaction") or {}).get("shipping_options") or
                    []
                )
                if shipping_options:
                    logger.info(f"Shipping options trouvées via {endpoint}: {len(shipping_options)}")
                    break
            except Exception as e:
                logger.debug(f"Shipping endpoint {endpoint}: {e}")

    logger.info(f"Shipping options disponibles: {len(shipping_options)}")
    for opt in shipping_options:
        logger.info(f"  - [{opt.get('id')}] {opt.get('title') or opt.get('name')} — {opt.get('price')}")

    # ── Step 3: Select shipping ────────────────────────────────────────────────
    selected_shipping_id = None

    if shipping_options:
        relay_option = None
        cheapest_option = None

        # Find relay option if user has an address
        if postal_code:
            for opt in shipping_options:
                name = (opt.get("title") or opt.get("name") or opt.get("type") or "").lower()
                if any(kw in name for kw in _RELAY_KEYWORDS):
                    relay_option = opt
                    logger.info(f"Option relais trouvée: {opt.get('title')} (id={opt.get('id')})")
                    break

        # Find cheapest option as fallback
        def _price(o):
            p = o.get("price")
            if isinstance(p, dict):
                return float(p.get("amount", 999) or 999)
            return float(p or 999)

        try:
            cheapest_option = min(shipping_options, key=_price)
        except Exception:
            cheapest_option = shipping_options[0]

        chosen = relay_option or cheapest_option
        selected_shipping_id = str(chosen.get("id", ""))
        logger.info(f"Shipping choisi: {chosen.get('title')} (id={selected_shipping_id})")

        try:
            await client.patch(
                f"/transactions/{transaction_id}",
                json={"transaction": {"shipping_option_id": selected_shipping_id}},
            )
            logger.info("Shipping sélectionné ✓")
        except Exception as e:
            logger.warning(f"Erreur sélection shipping: {e}")

        await asyncio.sleep(0.3)

        # ── Step 3b: Select pickup point if relay ──────────────────────────────
        if relay_option and postal_code:
            pickup_points = []
            for endpoint in [
                f"/transactions/{transaction_id}/pickup_points",
                f"/transactions/{transaction_id}/shipping_options/{selected_shipping_id}/pickup_points",
                f"/pickup_points",
            ]:
                try:
                    params = {"postal_code": postal_code, "country_code": country}
                    data = await client.get(endpoint, params=params)
                    pickup_points = (
                        data.get("pickup_points") or
                        data.get("locations") or
                        data.get("points") or []
                    )
                    if pickup_points:
                        logger.info(f"Points relais trouvés via {endpoint}: {len(pickup_points)}")
                        break
                except Exception as e:
                    logger.debug(f"Pickup endpoint {endpoint}: {e}")

            if pickup_points:
                nearest = pickup_points[0]
                point_id = nearest.get("id") or nearest.get("code") or nearest.get("external_id")
                logger.info(f"Point relais sélectionné: {nearest.get('name')} — {nearest.get('address')} (id={point_id})")
                if point_id:
                    try:
                        await client.patch(
                            f"/transactions/{transaction_id}",
                            json={"transaction": {"pickup_point_id": str(point_id)}},
                        )
                        logger.info("Point relais appliqué ✓")
                    except Exception as e:
                        logger.warning(f"Erreur sélection point relais: {e}")
            else:
                logger.info("Aucun point relais trouvé pour ce code postal — livraison relais sans point spécifique")

    # ── Step 4: Get payment methods ────────────────────────────────────────────
    await asyncio.sleep(0.3)
    payment_method_id = None
    payment_card = (account_info or {}).get("payment_card")

    # Payment methods may be in the transaction
    payment_methods = (
        transaction.get("payment_methods") or
        transaction.get("available_payment_methods") or
        []
    )

    if not payment_methods:
        for endpoint in [
            f"/transactions/{transaction_id}/payment_methods",
            f"/transactions/{transaction_id}",
        ]:
            try:
                data = await client.get(endpoint)
                payment_methods = (
                    data.get("payment_methods") or
                    data.get("available_payment_methods") or
                    (data.get("transaction") or {}).get("payment_methods") or
                    []
                )
                if payment_methods:
                    logger.info(f"Payment methods via {endpoint}: {len(payment_methods)}")
                    break
            except Exception as e:
                logger.debug(f"Payment endpoint {endpoint}: {e}")

    logger.info(f"Méthodes de paiement disponibles: {len(payment_methods)}")
    for m in payment_methods:
        logger.info(f"  - [{m.get('id')}] type={m.get('type')} last4={m.get('last4')} brand={m.get('brand')}")

    if payment_methods:
        stored_last4 = ""
        if payment_card and payment_card.get("number"):
            stored_last4 = str(payment_card["number"]).replace(" ", "")[-4:]

        # 1. Match by card last 4 digits
        if stored_last4:
            for m in payment_methods:
                last4 = str(m.get("last4") or m.get("last_four") or "")
                if last4 == stored_last4:
                    payment_method_id = str(m.get("id", ""))
                    logger.info(f"Carte correspondante trouvée (****{stored_last4}): {payment_method_id}")
                    break

        # 2. Any card type
        if not payment_method_id:
            for m in payment_methods:
                mtype = (m.get("type") or m.get("kind") or "").lower()
                if any(k in mtype for k in ("card", "credit", "debit", "carte")):
                    payment_method_id = str(m.get("id", ""))
                    logger.info(f"Carte disponible utilisée: {payment_method_id} ({m.get('type')})")
                    break

        # 3. Wallet
        if not payment_method_id:
            for m in payment_methods:
                mtype = (m.get("type") or m.get("kind") or "").lower()
                if any(k in mtype for k in ("wallet", "balance", "solde")):
                    payment_method_id = str(m.get("id", ""))
                    logger.info(f"Wallet utilisé: {payment_method_id}")
                    break

        # 4. First available
        if not payment_method_id and payment_methods:
            payment_method_id = str(payment_methods[0].get("id", ""))
            logger.info(f"Première méthode utilisée: {payment_method_id}")

    # ── Step 5: Finalize ───────────────────────────────────────────────────────
    await asyncio.sleep(0.2)

    finalize_endpoints = [
        f"/transactions/{transaction_id}/finalize",
        f"/transactions/{transaction_id}/confirm",
        f"/transactions/{transaction_id}/buy",
    ]

    payload: dict = {}
    if payment_method_id:
        payload["payment_method_id"] = payment_method_id

    for endpoint in finalize_endpoints:
        try:
            result = await client.post(endpoint, json=payload)
            logger.info(f"Finalisation via {endpoint}: OK — keys={list(result.keys())}")

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
            logger.warning(f"Finalisation {endpoint} échouée: {e}")
            continue

    return PurchaseResult(
        success=False,
        item_id=item_id,
        transaction_id=transaction_id,
        error="Finalisation impossible — tous les endpoints ont échoué",
    )
