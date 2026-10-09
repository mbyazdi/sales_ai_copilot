"""Authorized candidate quotes; pricing arithmetic remains in Pricing Core."""
import json

from django.core.exceptions import ValidationError
from django.http import Http404

from apps.visits.models import Visit

from .catalog import positive_id
from .catalog_access import catalog_access
from .eligibility import catalog_candidates, product_eligibility
from .pricing import CURRENCY, DemoPriceProvider, PriceState


MAX_QUOTE_ITEMS = 50
MAX_ITEMS_JSON_LENGTH = 10000
# Match the existing PositiveIntegerField request-line quantity representation.
MAX_QUANTITY = 2147483647


def _quantities(raw):
    if not isinstance(raw, str) or len(raw) > MAX_ITEMS_JSON_LENGTH:
        raise ValidationError({"items": "فهرست محصولات معتبر نیست یا بیش از حد بزرگ است."})
    try:
        items = json.loads(raw)
    except (ValueError, RecursionError) as error:
        raise ValidationError({"items": "فهرست محصولات باید JSON معتبر باشد."}) from error
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_QUOTE_ITEMS:
        raise ValidationError({"items": "بین ۱ تا ۵۰ محصول را مشخص کنید."})
    quantities = {}
    for item in items:
        if not isinstance(item, dict) or set(item) != {"product_id", "quantity"}:
            raise ValidationError({"items": "برای هر محصول فقط شناسه و تعداد لازم است."})
        product_id, quantity = item["product_id"], item["quantity"]
        if type(product_id) is not int or not 1 <= product_id <= 999999999999999999:
            raise ValidationError({"items": "شناسه محصول معتبر نیست."})
        if type(quantity) is not int or not 1 <= quantity <= MAX_QUANTITY:
            raise ValidationError({"items": "تعداد باید عدد صحیح مثبت و در محدوده مجاز باشد."})
        if product_id in quantities:
            raise ValidationError({"items": "هر محصول را فقط یک بار مشخص کنید."})
        quantities[product_id] = quantity
    return quantities


def candidate_quote(user, customer_code, visit_id, raw_items, *, provider=None):
    """Zero-write boundary: authorize before product, inventory or price reads.

    A quote is not a selection, stock reservation, request or realized sale.
    PLANNED allows preparation; actual Add remains a future IN_PROGRESS mutation.
    """
    access = catalog_access(user, customer_code, positive_id(visit_id, "visit_id"))
    quantities = _quantities(raw_items)
    products = list(catalog_candidates().filter(pk__in=quantities).select_related("inventory").order_by("pk"))
    if len(products) != len(quantities):
        raise Http404
    prices = (provider if provider is not None else DemoPriceProvider()).quote_many(access.customer.pk, quantities)
    items = []
    for product in products:
        inventory = product_eligibility(product)
        price = prices[product.pk]
        reason = inventory["non_addable_reason"]
        if reason is None and quantities[product.pk] > inventory["available_quantity"]:
            reason = "INSUFFICIENT_STOCK"
        if reason is None and price.state != PriceState.AVAILABLE:
            reason = "PRICE_UNAVAILABLE" if price.state == PriceState.UNAVAILABLE else "PRICE_CONFIGURATION_ERROR"
        if reason is None and access.visit.status != Visit.VisitStatus.IN_PROGRESS:
            reason = "VISIT_NOT_ACTIVE"
        items.append({
            "product_id": product.pk, "product_code": product.product_code,
            "name": product.name, "unit": product.unit, "quantity": quantities[product.pk],
            "pricing": {
                "state": str(price.state), "reason_code": price.reason_code,
                "quote": price.quote.as_dict() if price.quote is not None else None,
            },
            "inventory": {
                "state": inventory["inventory_state"],
                "sellable_quantity": inventory["available_quantity"],
                "can_add": inventory["can_add"],
                "reason_code": inventory["non_addable_reason"],
            },
            "can_add": reason is None, "non_addable_reason": reason,
        })
    return {
        "version": 1, "currency": CURRENCY,
        "customer": {"id": access.customer.pk, "code": access.customer.customer_code},
        "visit": {"id": access.visit.pk, "status": access.visit.status},
        "items": items,
    }
