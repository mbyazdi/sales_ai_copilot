from decimal import Decimal

from django.utils import timezone

from .models import SalesTarget


def serialize_sales_target(target):
    """
    Convert one SalesTarget into a normalized
    target-progress contract.
    """

    return {
        "id": target.id,

        "salesperson": {
            "id": target.salesperson_id,
            "employee_code": (
                target.salesperson.employee_code
            ),
            "full_name": (
                target.salesperson.full_name
            ),
        },

        "period": {
            "start": target.period_start,
            "end": target.period_end,
        },

        "scope": {
            "type": target.scope_type,
            "code": target.scope_code,

            "name": (
                target.product.name
                if target.scope_type
                == SalesTarget.ScopeType.PRODUCT
                and target.product
                else (
                    target.category.name
                    if target.scope_type
                    == SalesTarget.ScopeType.CATEGORY
                    and target.category
                    else (
                        target.get_product_group_display()
                        if target.scope_type
                        == SalesTarget.ScopeType.PRODUCT_GROUP
                        else ""
                    )
                )
            ),
        },

        "target_unit": target.target_unit,

        "target_value": target.target_value,

        "actual_value": target.actual_value,

        "remaining_value": (
            target.remaining_value
        ),

        "achievement_percent": (
            target.achievement_percent
        ),

        "is_active": target.is_active,
    }


def get_salesperson_target_progress(
    salesperson,
    as_of_date=None,
):
    """
    Return all active targets for a salesperson
    that are valid on the requested date.

    Actual values are currently treated as
    imported/snapshot values.
    """

    if as_of_date is None:
        as_of_date = timezone.localdate()

    targets = (
        SalesTarget.objects
        .filter(
            salesperson=salesperson,
            is_active=True,
            period_start__lte=as_of_date,
            period_end__gte=as_of_date,
        )
        .select_related(
            "salesperson",
            "product",
            "category",
        )
        .order_by(
            "scope_type",
            "id",
        )
    )

    return [
        serialize_sales_target(target)
        for target in targets
    ]


def build_target_summary(
    target_progress,
):
    """
    Build a lightweight summary for sales-rep
    and manager-facing experiences.
    """

    target_progress = list(
        target_progress
    )

    if not target_progress:
        return {
            "total_targets": 0,
            "average_achievement_percent":
                Decimal("0"),

            "completed_targets": 0,
            "at_risk_targets": 0,
        }

    completed_targets = sum(
        1
        for item in target_progress
        if (
            item["achievement_percent"]
            >= Decimal("100")
        )
    )

    at_risk_targets = sum(
        1
        for item in target_progress
        if (
            item["achievement_percent"]
            < Decimal("70")
        )
    )

    average_achievement_percent = (
        sum(
            item["achievement_percent"]
            for item in target_progress
        )
        / Decimal(
            len(target_progress)
        )
    )

    return {
        "total_targets":
            len(target_progress),

        "average_achievement_percent":
            average_achievement_percent,

        "completed_targets":
            completed_targets,

        "at_risk_targets":
            at_risk_targets,
    }