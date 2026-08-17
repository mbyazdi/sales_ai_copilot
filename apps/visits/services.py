from django.db.models import (
    Count,
    Sum,
    Avg,
    Q,
)

from .models import SalesOutcome


OUTCOME_PRIORITY = {
    "PURCHASED": 5,
    "INTERESTED": 4,
    "FOLLOW_UP": 3,
    "REJECTED": 2,
    "NOT_PRESENTED": 1,
}


def resolve_recommendation_outcome(
    visit_id,
    recommendation_id,
):
    """
    Resolve all raw SalesOutcome records belonging to
    one Visit + one Recommendation into one final outcome.

    Raw outcome records are NOT modified or deleted.
    """

    outcomes = list(
        SalesOutcome.objects
        .filter(
            visit_id=visit_id,
            recommendation_id=recommendation_id,
        )
        .order_by("-created_at", "-id")
    )

    if not outcomes:
        return None

    final_outcome = max(
        outcomes,
        key=lambda item: OUTCOME_PRIORITY.get(
            item.outcome,
            0,
        ),
    )

    quantity = 0
    sales_amount = 0

    if final_outcome.outcome == "PURCHASED":

        purchase_records = [
            item
            for item in outcomes
            if item.outcome == "PURCHASED"
        ]

        purchase_with_value = next(
            (
                item
                for item in purchase_records
                if (
                    (item.quantity or 0) > 0
                    or (item.sales_amount or 0) > 0
                )
            ),
            None,
        )

        if purchase_with_value:
            quantity = purchase_with_value.quantity or 0
            sales_amount = (
                purchase_with_value.sales_amount or 0
            )

    return {
        "visit_id": visit_id,
        "recommendation_id": recommendation_id,
        "outcome": final_outcome.outcome,
        "quantity": quantity,
        "sales_amount": sales_amount,
        "events_count": len(outcomes),
        "last_event_id": outcomes[0].id,
        "last_event_at": outcomes[0].created_at,
    }
def get_recommendation_performance(customer=None):
    from django.db.models import Avg, Count, Q, Sum
    from apps.visits.models import SalesOutcome

    queryset = SalesOutcome.objects.all()

    if customer is not None:
        queryset = queryset.filter(
            visit__customer=customer
        )

    performance = (
        queryset
        .values(
            "recommendation__recommendation_type"
        )
        .annotate(
            presented=Count("id"),

            purchased=Count(
                "id",
                filter=Q(
                    outcome="PURCHASED"
                ),
            ),

            interested=Count(
                "id",
                filter=Q(
                    outcome="INTERESTED"
                ),
            ),

            rejected=Count(
                "id",
                filter=Q(
                    outcome="REJECTED"
                ),
            ),

            follow_up=Count(
                "id",
                filter=Q(
                    outcome="FOLLOW_UP"
                ),
            ),

            not_presented=Count(
                "id",
                filter=Q(
                    outcome="NOT_PRESENTED"
                ),
            ),

            revenue=Sum(
                "sales_amount"
            ),

            average_revenue=Avg(
                "sales_amount",
                filter=Q(
                    outcome="PURCHASED"
                ),
            ),
        )
        .order_by(
            "recommendation__recommendation_type"
        )
    )

    result = []

    for item in performance:

        presented = item["presented"] or 0
        purchased = item["purchased"] or 0
        interested = item["interested"] or 0
        rejected = item["rejected"] or 0
        follow_up = item["follow_up"] or 0
        not_presented = item["not_presented"] or 0

        conversion_rate = (
            (purchased / presented) * 100
            if presented
            else 0
        )

        interest_rate = (
            (interested / presented) * 100
            if presented
            else 0
        )

        # =====================================================
        # DATA SUFFICIENCY
        # =====================================================

        if presented < 3:
            data_quality = "INSUFFICIENT_DATA"

        elif presented < 10:
            data_quality = "LIMITED_DATA"

        else:
            data_quality = "SUFFICIENT_DATA"

        # =====================================================
        # PERFORMANCE LEVEL
        # =====================================================

        if presented < 3:

            performance_level = "UNKNOWN"

        elif conversion_rate >= 40:

            performance_level = "HIGH"

        elif conversion_rate >= 20:

            performance_level = "MEDIUM"

        else:

            performance_level = "LOW"

        # =====================================================
        # LEARNING SIGNAL
        # =====================================================

        if presented < 3:

            learning_signal = "INSUFFICIENT_DATA"

        elif conversion_rate >= 40:

            learning_signal = "POSITIVE"

        elif (
            conversion_rate < 20
            and interest_rate >= 40
        ):

            learning_signal = "PROMISING"

        elif (
            conversion_rate < 20
            and interest_rate < 40
        ):

            learning_signal = "WEAK"

        else:

            learning_signal = "NEUTRAL"

        # =====================================================
        # RECOMMENDATION EFFECTIVENESS
        # =====================================================

        engagement_rate = (
            (
                purchased
                + interested
                + follow_up
            )
            / presented
            * 100
            if presented
            else 0
        )

        # =====================================================
        # RESULT
        # =====================================================

        result.append({

            "recommendation_type": (
                item[
                    "recommendation__recommendation_type"
                ]
            ),

            "presented": presented,

            "purchased": purchased,

            "interested": interested,

            "rejected": rejected,

            "follow_up": follow_up,

            "not_presented": not_presented,

            "revenue": float(
                item["revenue"] or 0
            ),

            "average_revenue": float(
                item["average_revenue"] or 0
            ),

            "conversion_rate": round(
                conversion_rate,
                2,
            ),

            "interest_rate": round(
                interest_rate,
                2,
            ),

            "engagement_rate": round(
                engagement_rate,
                2,
            ),

            "performance_level": (
                performance_level
            ),

            "learning_signal": (
                learning_signal
            ),

            "data_quality": (
                data_quality
            ),
        })

    return result