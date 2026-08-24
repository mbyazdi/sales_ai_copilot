from django.db.models import Q
from django.utils import timezone

from .models import Promotion


def get_eligible_product_promotions(
    product,
    customer=None,
    as_of_date=None,
):
    """
    Return active, date-valid promotions
    associated with one product.

    If customer grade restrictions exist,
    customer eligibility is also enforced.
    """

    if as_of_date is None:
        as_of_date = timezone.localdate()

    promotions = (
        Promotion.objects
        .filter(
            is_active=True,

            start_date__lte=as_of_date,
            end_date__gte=as_of_date,

            promotion_products__product=product,
        )
        .prefetch_related(
            "customer_grades",
        )
        .distinct()
        .order_by(
            "-start_date",
            "code",
        )
    )

    result = []

    for promotion in promotions:

        allowed_grade_ids = {
            grade.id
            for grade
            in promotion.customer_grades.all()
        }

        # No grade restriction means
        # the promotion is open to all grades.
        if not allowed_grade_ids:

            customer_eligible = True

        elif (
            customer is not None
            and customer.grade_id
            in allowed_grade_ids
        ):

            customer_eligible = True

        else:

            customer_eligible = False

        if not customer_eligible:
            continue

        result.append({
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
        })

    return result