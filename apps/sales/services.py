from collections import defaultdict

from django.db.models import Sum, Count, Avg
from django.shortcuts import get_object_or_404

from apps.customers.models import Customer

from .models import Sale, SaleItem


def get_customer_sales_history(
    customer_code,
    limit=None,
):
    """
    Return purchase history and sales summary
    for one customer.
    """

    customer = get_object_or_404(
        Customer.objects.only(
            "id",
            "customer_code",
            "name",
        ),
        customer_code=customer_code,
        is_active=True,
    )

    sales_queryset = (
        Sale.objects
        .filter(
            customer=customer,
        )
        .prefetch_related(
            "items__product",
            "items__product__category",
        )
        .order_by(
            "-sale_date",
            "-id",
        )
    )

    summary = sales_queryset.aggregate(
        total_orders=Count("id"),

        total_sales_amount=Sum(
            "total_amount"
        ),

        average_order_value=Avg(
            "total_amount"
        ),
    )

    total_items = 0

    for sale in sales_queryset:

        for item in sale.items.all():
            total_items += item.quantity

    sales = sales_queryset

    if limit:
        sales = sales[:limit]

    sales_data = []

    for sale in sales:

        items_data = []

        for item in sale.items.all():

            product = item.product

            items_data.append({

                "product_code": (
                    product.product_code
                ),

                "product_name": (
                    product.name
                ),

                "category": (
                    str(product.category)
                    if product.category
                    else None
                ),

                "quantity": (
                    item.quantity
                ),

                "unit_price": (
                    item.unit_price
                ),

                "discount_amount": (
                    item.discount_amount
                ),

                "total_amount": (
                    item.total_amount
                ),
            })

        sales_data.append({

            "id": sale.id,

            "invoice_number": (
                sale.invoice_number
            ),

            "sale_date": (
                sale.sale_date
            ),

            "total_amount": (
                sale.total_amount
            ),

            "description": (
                sale.description
            ),

            "items": items_data,

        })

    return {

        "customer": customer,

        "summary": {

            "total_orders": (
                summary["total_orders"]
                or 0
            ),

            "total_items": (
                total_items
            ),

            "total_sales_amount": (
                summary["total_sales_amount"]
                or 0
            ),

            "average_order_value": (
                summary["average_order_value"]
                or 0
            ),

        },

        "sales": sales_data,

    }


def get_customer_purchase_pattern(customer_code):
    """
    Analyze purchase behavior for one customer.

    Returns:
        - summary
        - top_products
        - top_categories
        - repeat_purchase_candidates
    """

    customer = get_object_or_404(
        Customer.objects.only(
            "id",
            "customer_code",
            "name",
        ),
        customer_code=customer_code,
        is_active=True,
    )

    items = (
        SaleItem.objects
        .filter(
            sale__customer=customer,
        )
        .select_related(
            "product",
            "product__category",
            "sale",
        )
        .order_by(
            "-sale__sale_date",
            "-sale__id",
        )
    )

    # =====================================================
    # SUMMARY
    # =====================================================

    total_products = 0
    unique_products = set()
    unique_categories = set()

    for item in items:

        total_products += item.quantity

        unique_products.add(
            item.product_id
        )

        if item.product.category:
            unique_categories.add(
                item.product.category_id
            )

    # =====================================================
    # PRODUCT AGGREGATION
    # =====================================================

    product_stats = defaultdict(
        lambda: {
            "product": None,
            "quantity": 0,
            "sales_amount": 0,
            "purchase_count": 0,
            "last_purchase_date": None,
        }
    )

    for item in items:

        product = item.product
        product_id = product.id

        stats = product_stats[product_id]

        stats["product"] = product

        stats["quantity"] += item.quantity

        stats["sales_amount"] += (
            item.total_amount
        )

        stats["purchase_count"] += 1

        if (
            stats["last_purchase_date"] is None
            or item.sale.sale_date
            > stats["last_purchase_date"]
        ):
            stats["last_purchase_date"] = (
                item.sale.sale_date
            )

    # =====================================================
    # TOP PRODUCTS
    # =====================================================

    top_products = sorted(
        product_stats.values(),
        key=lambda item: (
            item["quantity"],
            item["sales_amount"],
        ),
        reverse=True,
    )

    top_products_data = []

    for item in top_products:

        product = item["product"]

        top_products_data.append({

            "product_code": (
                product.product_code
            ),

            "product_name": (
                product.name
            ),

            "category": (
                str(product.category)
                if product.category
                else None
            ),

            "quantity": (
                item["quantity"]
            ),

            "sales_amount": float(
                item["sales_amount"]
            ),

            "purchase_count": (
                item["purchase_count"]
            ),

            "last_purchase_date": (
                item["last_purchase_date"]
            ),

        })

    # =====================================================
    # CATEGORY AGGREGATION
    # =====================================================

    category_stats = defaultdict(
        lambda: {
            "category": None,
            "quantity": 0,
            "sales_amount": 0,
            "purchase_count": 0,
        }
    )

    for item in items:

        category = item.product.category

        if category is None:
            continue

        category_id = category.id

        stats = category_stats[category_id]

        stats["category"] = category

        stats["quantity"] += item.quantity

        stats["sales_amount"] += (
            item.total_amount
        )

        stats["purchase_count"] += 1

    # =====================================================
    # TOP CATEGORIES
    # =====================================================

    top_categories = sorted(
        category_stats.values(),
        key=lambda item: (
            item["quantity"],
            item["sales_amount"],
        ),
        reverse=True,
    )

    top_categories_data = []

    for item in top_categories:

        category = item["category"]

        top_categories_data.append({

            "category": str(category),

            "quantity": (
                item["quantity"]
            ),

            "sales_amount": float(
                item["sales_amount"]
            ),

            "purchase_count": (
                item["purchase_count"]
            ),

        })

    # =====================================================
    # REPEAT PURCHASE CANDIDATES
    # =====================================================

    repeat_candidates = []

    for item in top_products:

        if item["purchase_count"] < 2:
            continue

        product = item["product"]

        repeat_candidates.append({

            "product_code": (
                product.product_code
            ),

            "product_name": (
                product.name
            ),

            "last_purchase_date": (
                item["last_purchase_date"]
            ),

            "purchase_count": (
                item["purchase_count"]
            ),

            "total_quantity": (
                item["quantity"]
            ),

        })

    # =====================================================
    # RESULT
    # =====================================================

    return {

        "customer": customer,

        "summary": {

            "total_products": (
                total_products
            ),

            "unique_products": (
                len(unique_products)
            ),

            "unique_categories": (
                len(unique_categories)
            ),

        },

        "top_products": (
            top_products_data
        ),

        "top_categories": (
            top_categories_data
        ),

        "repeat_purchase_candidates": (
            repeat_candidates
        ),

    }