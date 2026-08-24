from .models import Inventory


def get_product_inventory_context(
    product,
):
    """
    Return normalized inventory context
    for one product.

    Missing inventory is represented explicitly
    rather than being treated as zero stock.
    """

    try:
        inventory = product.inventory

    except Inventory.DoesNotExist:

        return {
            "has_record": False,

            "available_quantity": None,
            "reserved_quantity": None,
            "sellable_quantity": None,
            "minimum_stock": None,

            "is_in_stock": None,
            "is_low_stock": None,

            "last_updated": None,
        }

    sellable_quantity = (
        inventory.sellable_quantity
    )

    return {
        "has_record": True,

        "available_quantity": (
            inventory.available_quantity
        ),

        "reserved_quantity": (
            inventory.reserved_quantity
        ),

        "sellable_quantity": (
            sellable_quantity
        ),

        "minimum_stock": (
            inventory.minimum_stock
        ),

        "is_in_stock": (
            sellable_quantity > 0
        ),

        "is_low_stock": (
            sellable_quantity > 0
            and sellable_quantity
            <= inventory.minimum_stock
        ),

        "last_updated": (
            inventory.last_updated
        ),
    }