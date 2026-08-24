from django.utils import timezone

from apps.inventory.models import Inventory
from apps.promotions.models import PromotionProduct


def _empty_inventory_context():
    """
    Explicitly represent missing inventory data.
    """

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


def _serialize_inventory(
    inventory,
):
    """
    Serialize one Inventory object without
    performing additional database queries.
    """

    if inventory is None:
        return _empty_inventory_context()

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


def _serialize_promotion(
    promotion,
):
    """
    Serialize one promotion after eligibility
    has already been established.
    """

    return {
        "id": promotion.id,

        "code": promotion.code,
        "name": promotion.name,

        "promotion_type": (
            promotion.promotion_type
        ),

        "start_date": (
            promotion.start_date
        ),

        "end_date": (
            promotion.end_date
        ),

        "discount_percent": (
            promotion.discount_percent
        ),

        "discount_amount": (
            promotion.discount_amount
        ),

        "minimum_quantity": (
            promotion.minimum_quantity
        ),

        "maximum_quantity": (
            promotion.maximum_quantity
        ),

        "description": (
            promotion.description
        ),

        "customer_eligible": True,
    }


def _customer_is_eligible(
    promotion,
    customer,
):
    """
    Evaluate customer-grade eligibility using
    prefetched promotion customer grades.
    """

    allowed_grade_ids = {
        grade.id
        for grade
        in promotion.customer_grades.all()
    }

    if not allowed_grade_ids:
        return True

    if customer is None:
        return False

    return (
        customer.grade_id
        in allowed_grade_ids
    )


def build_product_commercial_contexts(
    product_customer_pairs,
    as_of_date=None,
):
    """
    Build commercial contexts for multiple
    Product + Customer pairs in batches.

    Returns:
        {
            (product_id, customer_id): {...}
        }

    This avoids per-visit Inventory and
    Promotion queries.
    """

    if as_of_date is None:
        as_of_date = timezone.localdate()

    pairs = list(
        product_customer_pairs
    )

    if not pairs:
        return {}

    unique_pairs = {}

    for product, customer in pairs:

        customer_id = (
            customer.id
            if customer is not None
            else None
        )

        unique_pairs[
            (
                product.id,
                customer_id,
            )
        ] = (
            product,
            customer,
        )

    product_ids = {
        product.id
        for product, _
        in unique_pairs.values()
    }

    # ==========================================
    # INVENTORY — ONE QUERY
    # ==========================================

    inventory_by_product = {
        inventory.product_id: inventory
        for inventory
        in Inventory.objects.filter(
            product_id__in=product_ids,
        )
    }

    # ==========================================
    # PROMOTIONS — BATCH QUERY
    # ==========================================

    promotion_links = (
        PromotionProduct.objects
        .filter(
            product_id__in=product_ids,

            promotion__is_active=True,

            promotion__start_date__lte=(
                as_of_date
            ),

            promotion__end_date__gte=(
                as_of_date
            ),
        )
        .select_related(
            "promotion",
        )
        .prefetch_related(
            "promotion__customer_grades",
        )
        .order_by(
            "product_id",
            "-promotion__start_date",
            "promotion__code",
        )
    )

    promotions_by_product = {}

    for link in promotion_links:

        promotions_by_product.setdefault(
            link.product_id,
            [],
        ).append(
            link.promotion
        )

    # ==========================================
    # BUILD CONTEXTS — NO MORE QUERIES
    # ==========================================

    contexts = {}

    for key, (
        product,
        customer,
    ) in unique_pairs.items():

        inventory = (
            inventory_by_product.get(
                product.id
            )
        )

        eligible_promotions = []

        for promotion in (
            promotions_by_product.get(
                product.id,
                [],
            )
        ):

            if not _customer_is_eligible(
                promotion=promotion,
                customer=customer,
            ):
                continue

            eligible_promotions.append(
                _serialize_promotion(
                    promotion
                )
            )

        contexts[key] = {
            "product_code": (
                product.product_code
            ),

            "product_name": (
                product.name
            ),

            "inventory": (
                _serialize_inventory(
                    inventory
                )
            ),

            "promotions": (
                eligible_promotions
            ),

            "has_eligible_promotion": (
                bool(
                    eligible_promotions
                )
            ),
        }

    return contexts


def build_product_commercial_context(
    product,
    customer=None,
    as_of_date=None,
):
    """
    Convenience wrapper for one product/customer.

    Batch callers should use
    build_product_commercial_contexts().
    """

    contexts = (
        build_product_commercial_contexts(
            product_customer_pairs=[
                (
                    product,
                    customer,
                )
            ],
            as_of_date=as_of_date,
        )
    )

    customer_id = (
        customer.id
        if customer is not None
        else None
    )

    return contexts[
        (
            product.id,
            customer_id,
        )
    ]