"""Catalog visibility and current stock eligibility; never recommendation candidates."""
from apps.inventory.services import get_product_inventory_context

from .models import Product


def catalog_candidates():
    # Brand/category flags and customer grade are not product sale restrictions.
    return Product.objects.filter(is_active=True)


def product_eligibility(product):
    """Use canonical sellable stock. Quote validation remains a separate boundary."""
    inventory = get_product_inventory_context(product)
    quantity = inventory["sellable_quantity"]
    state = "UNKNOWN" if quantity is None else ("AVAILABLE" if quantity > 0 else "UNAVAILABLE")
    reason = None
    if not product.is_active:
        reason = "INACTIVE_PRODUCT"
    elif state == "UNKNOWN":
        reason = "INVENTORY_UNKNOWN"
    elif state == "UNAVAILABLE":
        reason = "OUT_OF_STOCK"
    return {
        "catalog_visible": product.is_active,
        "inventory_state": state,
        "available_quantity": quantity,
        "can_add": reason is None,
        "non_addable_reason": reason,
    }
