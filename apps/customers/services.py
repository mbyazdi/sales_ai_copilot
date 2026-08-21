from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum, Count, Max, Min
from django.utils import timezone

from .models import Customer, Customer360
from apps.sales.models import Sale, SaleItem


def get_customer_by_code(customer_code):
    """
    Get an active customer by customer code.
    """

    return (
        Customer.objects
        .select_related(
            "grade",
            "customer_360",
        )
        .get(
            customer_code=customer_code,
            is_active=True,
        )
    )


def get_customer_360(customer_code):
    """
    Return customer, Customer360 snapshot,
    salesperson assignment and latest visit.
    """

    from apps.visits.models import (
        CustomerAssignment,
        Visit,
    )

    customer = get_customer_by_code(customer_code)

    customer_360 = getattr(
        customer,
        "customer_360",
        None,
    )

    # -------------------------------------------------
    # Active salesperson assignment
    # -------------------------------------------------

    assignment = (
        CustomerAssignment.objects
        .filter(
            customer=customer,
            is_active=True,
        )
        .select_related("salesperson")
        .order_by("-start_date", "-id")
        .first()
    )

    # -------------------------------------------------
    # Latest visit
    # -------------------------------------------------

    latest_visit = (
        Visit.objects
        .filter(
            customer=customer,
        )
        .select_related("salesperson")
        .order_by("-visit_date", "-id")
        .first()
    )

    return {
        "customer": customer,
        "customer_360": customer_360,
        "assignment": assignment,
        "latest_visit": latest_visit,
    }


def build_customer_360(customer):
    """
    Build or refresh Customer360 for a customer.

    All metrics are calculated from Sale and SaleItem.
    """

    today = timezone.localdate()

    # -------------------------------------------------
    # Customer sales
    # -------------------------------------------------

    sales = Sale.objects.filter(
        customer=customer
    )

    # -------------------------------------------------
    # Basic order metrics
    # -------------------------------------------------

    order_stats = sales.aggregate(
        total_orders=Count("id"),
        total_sales_amount=Sum("total_amount"),
        last_purchase_date=Max("sale_date"),
        first_purchase_date=Min("sale_date"),
    )

    total_orders = order_stats["total_orders"] or 0

    total_sales_amount = (
        order_stats["total_sales_amount"]
        or Decimal("0")
    )

    last_purchase_date = order_stats[
        "last_purchase_date"
    ]

    first_purchase_date = order_stats[
        "first_purchase_date"
    ]

    # -------------------------------------------------
    # Sale items
    # -------------------------------------------------

    item_stats = SaleItem.objects.filter(
        sale__customer=customer
    ).aggregate(
        total_items=Sum("quantity")
    )

    total_items = item_stats["total_items"] or 0

    # -------------------------------------------------
    # Average order value
    # -------------------------------------------------

    if total_orders > 0:
        average_order_value = (
            total_sales_amount
            / Decimal(total_orders)
        )
    else:
        average_order_value = Decimal("0")

    # -------------------------------------------------
    # Days since last purchase
    # -------------------------------------------------

    if last_purchase_date:
        days_since_last_purchase = (
            today - last_purchase_date
        ).days
    else:
        days_since_last_purchase = 0

    # -------------------------------------------------
    # Purchase frequency
    #
    # Orders / number of months since first purchase
    # -------------------------------------------------

    if (
        total_orders > 0
        and first_purchase_date
        and last_purchase_date
    ):
        days_active = (
            last_purchase_date
            - first_purchase_date
        ).days

        months_active = max(
            days_active / 30,
            1,
        )

        purchase_frequency = (
            Decimal(total_orders)
            / Decimal(str(months_active))
        )
    else:
        purchase_frequency = Decimal("0")

    # -------------------------------------------------
    # RFM scores
    # -------------------------------------------------

    # Recency
    if total_orders == 0:
        recency_score = 0
    elif days_since_last_purchase <= 30:
        recency_score = 5
    elif days_since_last_purchase <= 60:
        recency_score = 4
    elif days_since_last_purchase <= 90:
        recency_score = 3
    elif days_since_last_purchase <= 180:
        recency_score = 2
    else:
        recency_score = 1

    # Frequency
    if total_orders == 0:
        frequency_score = 0
    elif total_orders >= 20:
        frequency_score = 5
    elif total_orders >= 10:
        frequency_score = 4
    elif total_orders >= 5:
        frequency_score = 3
    elif total_orders >= 2:
        frequency_score = 2
    else:
        frequency_score = 1

    # Monetary
    if total_sales_amount >= Decimal("10000"):
        monetary_score = 5
    elif total_sales_amount >= Decimal("5000"):
        monetary_score = 4
    elif total_sales_amount >= Decimal("2000"):
        monetary_score = 3
    elif total_sales_amount >= Decimal("500"):
        monetary_score = 2
    elif total_sales_amount > 0:
        monetary_score = 1
    else:
        monetary_score = 0

    rfm_score = (
        recency_score * 100
        + frequency_score * 10
        + monetary_score
    )

    # -------------------------------------------------
    # Customer segment
    # -------------------------------------------------

    if total_orders == 0:
        segment = Customer360.Segment.NEW

    elif days_since_last_purchase > 180:
        segment = Customer360.Segment.INACTIVE

    elif (
        recency_score >= 4
        and frequency_score >= 4
        and monetary_score >= 4
    ):
        segment = Customer360.Segment.HIGH_VALUE

    elif (
        recency_score >= 4
        and frequency_score >= 3
    ):
        segment = Customer360.Segment.GROWTH

    elif days_since_last_purchase > 90:
        segment = Customer360.Segment.AT_RISK

    else:
        segment = Customer360.Segment.STABLE

    # -------------------------------------------------
    # Top product
    # -------------------------------------------------

    top_product = (
        SaleItem.objects
        .filter(
            sale__customer=customer
        )
        .values(
            "product__product_code",
            "product__category__name",
        )
        .annotate(
            quantity=Sum("quantity")
        )
        .order_by("-quantity")
        .first()
    )

    if top_product:
        top_product_code = (
            top_product["product__product_code"]
            or ""
        )

        top_category = (
            top_product["product__category__name"]
            or ""
        )
    else:
        top_product_code = ""
        top_category = ""

    # -------------------------------------------------
    # Sales trends
    # -------------------------------------------------

    date_30d = today - timedelta(days=30)
    date_90d = today - timedelta(days=90)

    sales_30d = (
        sales.filter(
            sale_date__gte=date_30d
        ).aggregate(
            total=Sum("total_amount")
        )["total"]
        or Decimal("0")
    )

    sales_90d = (
        sales.filter(
            sale_date__gte=date_90d
        ).aggregate(
            total=Sum("total_amount")
        )["total"]
        or Decimal("0")
    )

    # -------------------------------------------------
    # Create / update Customer360
    # -------------------------------------------------

    customer_360, created = (
        Customer360.objects.get_or_create(
            customer=customer
        )
    )

    customer_360.total_orders = total_orders
    customer_360.total_items = total_items
    customer_360.total_sales_amount = (
        total_sales_amount
    )
    customer_360.average_order_value = (
        average_order_value
    )

    customer_360.last_purchase_date = (
        last_purchase_date
    )
    customer_360.first_purchase_date = (
        first_purchase_date
    )

    customer_360.purchase_frequency = (
        purchase_frequency
    )

    customer_360.days_since_last_purchase = (
        days_since_last_purchase
    )

    customer_360.recency_score = recency_score
    customer_360.frequency_score = frequency_score
    customer_360.monetary_score = monetary_score
    customer_360.rfm_score = rfm_score

    customer_360.segment = segment

    customer_360.top_category = top_category
    customer_360.top_product_code = (
        top_product_code
    )

    customer_360.sales_30d = sales_30d
    customer_360.sales_90d = sales_90d

    customer_360.sales_30d_change_percent = (
        Decimal("0")
    )

    customer_360.sales_90d_change_percent = (
        Decimal("0")
    )

    customer_360.save()

    return customer_360


def build_all_customer_360():
    """
    Build or refresh Customer360 for all active customers.

    Returns:
        int: number of processed customers
    """

    customers = Customer.objects.filter(
        is_active=True
    )

    count = 0

    for customer in customers:
        build_customer_360(customer)
        count += 1

    return count

def build_sales_ai_context(
    customer,
    customer_360,
    current_visit=None,
    sales_session=None,
    recommendations=None,
):
    """
    Build a normalized sales context for AI Copilot.

    Important:
    Recommendation decisions are already made
    by the Rule-Based Recommendation Engine.

    This context is only used to explain,
    summarize, and assist the salesperson.
    """

    recommendations = (
        recommendations or []
    )

    # =====================================================
    # CUSTOMER
    # =====================================================

    customer_data = {
        "customer_code": (
            customer.customer_code
        ),
        "name": (
            customer.name
        ),
        "customer_type": (
            customer.customer_type
        ),
        "city": (
            customer.city
        ),
        "grade": (
            customer.grade.code
            if customer.grade
            else None
        ),
    }

    # =====================================================
    # CUSTOMER 360
    # =====================================================

    customer_360_data = None

    if customer_360:

        customer_360_data = {
            "segment": (
                customer_360.segment
            ),
            "total_orders": (
                customer_360.total_orders
            ),
            "total_sales_amount": (
                customer_360.total_sales_amount
            ),
            "average_order_value": (
                customer_360.average_order_value
            ),
            "last_purchase_date": (
                customer_360.last_purchase_date
            ),
            "days_since_last_purchase": (
                customer_360.days_since_last_purchase
            ),
            "top_category": (
                customer_360.top_category
            ),
            "top_product_code": (
                customer_360.top_product_code
            ),
            "rfm_score": (
                customer_360.rfm_score
            ),
        }

    # =====================================================
    # CURRENT VISIT
    # =====================================================

    current_visit_data = None

    if current_visit:

        current_visit_data = {
            "visit_id": (
                current_visit.id
            ),
            "visit_date": (
                current_visit.visit_date
            ),
            "status": (
                current_visit.status
            ),
            "salesperson": {
                "employee_code": (
                    current_visit
                    .salesperson
                    .employee_code
                ),
                "full_name": (
                    current_visit
                    .salesperson
                    .full_name
                ),
            },
        }

    # =====================================================
    # RECOMMENDATIONS
    # =====================================================

    recommendation_data = []

    for recommendation in recommendations:

        recommendation_data.append({
            "id": (
                recommendation.id
            ),
            "rank": (
                recommendation.rank
            ),
            "product_code": (
                recommendation
                .product
                .product_code
            ),
            "product_name": (
                recommendation
                .product
                .name
            ),
            "recommendation_type": (
                recommendation
                .recommendation_type
            ),
            "score": (
                recommendation.score
            ),
            "reason": (
                recommendation.reason
            ),
            "authoritative_explanation": (
                recommendation.reason
            ),
        })

    # =====================================================
    # FINAL CONTEXT
    # =====================================================

    return {
        "customer": customer_data,

        "customer_360": (
            customer_360_data
        ),

        "current_visit": (
            current_visit_data
        ),

        "sales_session": (
            sales_session or {}
        ),

        "recommendations": (
            recommendation_data
        ),
    }