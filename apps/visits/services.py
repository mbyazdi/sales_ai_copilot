from collections import defaultdict

from django.db.models import (
    Count,
    Sum,
    Avg,
    Q,
)

from apps.recommendations.models import (
    CustomerRecommendation,
)

from .models import (
    FollowUpTask,
    SalesOutcome,
)


OUTCOME_PRIORITY = {
    "PURCHASED": 5,
    "INTERESTED": 4,
    "FOLLOW_UP": 3,
    "REJECTED": 2,
    "NOT_PRESENTED": 1,
}

def build_pre_visit_briefs(
    visits,
    salesperson,
):
    """
    Build normalized pre-visit briefs for a batch
    of visits.

    This is intentionally based only on existing,
    authoritative backend data.

    Commercial Target, Promotion and Inventory
    will be added in later V2 stages.
    """

    visits = list(visits)

    if not visits:
        return {}

    customer_ids = {
        visit.customer_id
        for visit in visits
    }

    # =====================================================
    # PRIMARY RECOMMENDATIONS
    # =====================================================

    primary_recommendations = {}

    recommendations = (
        CustomerRecommendation.objects
        .filter(
            customer_id__in=customer_ids,
            is_active=True,
        )
        .select_related(
            "product",
        )
        .order_by(
            "customer_id",
            "rank",
            "-score",
            "id",
        )
    )

    for recommendation in recommendations:

        if (
            recommendation.customer_id
            not in primary_recommendations
        ):
            primary_recommendations[
                recommendation.customer_id
            ] = recommendation

    # =====================================================
    # OPEN FOLLOW-UPS
    # =====================================================

    followups_by_customer = defaultdict(
        list
    )

    followups = (
        FollowUpTask.objects
        .filter(
            salesperson=salesperson,
            customer_id__in=customer_ids,
            status=FollowUpTask.Status.OPEN,
        )
        .order_by(
            "customer_id",
            "due_date",
            "id",
        )
    )

    for followup in followups:

        followups_by_customer[
            followup.customer_id
        ].append(
            followup
        )

    # =====================================================
    # BUILD BRIEFS
    # =====================================================

    briefs = {}

    for visit in visits:

        customer = visit.customer

        customer_360 = getattr(
            customer,
            "customer_360",
            None,
        )

        primary = primary_recommendations.get(
            customer.id
        )

        customer_followups = (
            followups_by_customer.get(
                customer.id,
                [],
            )
        )

        next_followup = (
            customer_followups[0]
            if customer_followups
            else None
        )

        priority_score = 0
        priority_reasons = []

        if primary:

            recommendation_score = float(
                primary.score or 0
            )

            confidence_score = float(
                primary.confidence_score or 0
            )

            if recommendation_score >= 80:
                priority_score += 3
                priority_reasons.append(
                    "Strong recommendation score"
                )

            elif recommendation_score >= 50:
                priority_score += 2
                priority_reasons.append(
                    "Good recommendation score"
                )

            elif recommendation_score > 0:
                priority_score += 1
                priority_reasons.append(
                    "Active recommendation"
                )

            if confidence_score >= 80:
                priority_score += 2
                priority_reasons.append(
                    "High recommendation confidence"
                )

            elif confidence_score >= 60:
                priority_score += 1
                priority_reasons.append(
                    "Moderate recommendation confidence"
                )

        if customer_360:

            if (
                customer_360.segment
                == "HIGH_VALUE"
            ):
                priority_score += 2
                priority_reasons.append(
                    "High-value customer"
                )

            elif (
                customer_360.segment
                == "GROWTH"
            ):
                priority_score += 1
                priority_reasons.append(
                    "Growth customer"
                )

        if customer_followups:
            priority_score += 2
            priority_reasons.append(
                "Open follow-up exists"
            )

        if priority_score >= 6:
            priority_level = "HIGH"

        elif priority_score >= 3:
            priority_level = "MEDIUM"

        else:
            priority_level = "NORMAL"

        briefs[visit.id] = {
            "visit_id": visit.id,
            "priority_score":
                priority_score,

            "priority_level":
                priority_level,

            "priority_reasons":
                priority_reasons,
            "customer": {
                "customer_code":
                    customer.customer_code,

                "name":
                    customer.name,

                "grade": (
                    customer.grade.code
                    if customer.grade
                    else None
                ),

                "segment": (
                    customer_360.segment
                    if customer_360
                    else None
                ),

                "days_since_last_purchase": (
                    customer_360
                    .days_since_last_purchase
                    if customer_360
                    else None
                ),

                "top_category": (
                    customer_360.top_category
                    if customer_360
                    else None
                ),
            },

            "primary_recommendation": (
                {
                    "id":
                        primary.id,

                    "product_code":
                        primary.product.product_code,

                    "product_name":
                        primary.product.name,

                    "recommendation_type":
                        primary.recommendation_type,

                    "score":
                        primary.score,

                    "confidence_score":
                        primary.confidence_score,

                    "evidence_quality":
                        primary.evidence_quality,

                    "reason":
                        primary.reason,
                }
                if primary
                else None
            ),

            "open_follow_up_count": (
                len(
                    customer_followups
                )
            ),

            "next_follow_up": (
                {
                    "id":
                        next_followup.id,

                    "due_date":
                        next_followup.due_date,

                    "notes":
                        next_followup.notes,
                }
                if next_followup
                else None
            ),
        }

    return briefs

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
    """
    Calculate recommendation performance using
    resolved final outcomes per Visit + Recommendation.
    """

    from collections import defaultdict

    from apps.visits.models import SalesOutcome

    queryset = (
        SalesOutcome.objects
        .filter(
            recommendation__isnull=False,
        )
        .select_related(
            "visit",
            "recommendation",
        )
    )

    if customer is not None:
        queryset = queryset.filter(
            visit__customer=customer
        )

    pairs = (
        queryset
        .order_by()
        .values(
            "visit_id",
            "recommendation_id",
            "recommendation__recommendation_type",
        )
        .distinct()
    )

    performance = defaultdict(
        lambda: {
            "recommendation_type": None,
            "presented": 0,
            "purchased": 0,
            "interested": 0,
            "rejected": 0,
            "follow_up": 0,
            "not_presented": 0,
            "revenue": 0.0,
            "purchase_revenues": [],
        }
    )

    for pair in pairs:

        visit_id = pair["visit_id"]
        recommendation_id = pair["recommendation_id"]

        resolved = resolve_recommendation_outcome(
            visit_id=visit_id,
            recommendation_id=recommendation_id,
        )

        if not resolved:
            continue

        recommendation_type = (
            pair[
                "recommendation__recommendation_type"
            ]
        )

        if not recommendation_type:
            continue

        item = performance[
            recommendation_type
        ]

        item["recommendation_type"] = (
            recommendation_type
        )

        item["presented"] += 1

        outcome_name = resolved["outcome"]

        if outcome_name == "PURCHASED":

            item["purchased"] += 1

            revenue = float(
                resolved["sales_amount"] or 0
            )

            item["revenue"] += revenue

            if revenue > 0:
                item[
                    "purchase_revenues"
                ].append(
                    revenue
                )

        elif outcome_name == "INTERESTED":

            item["interested"] += 1

        elif outcome_name == "REJECTED":

            item["rejected"] += 1

        elif outcome_name == "FOLLOW_UP":

            item["follow_up"] += 1

        elif outcome_name == "NOT_PRESENTED":

            item["not_presented"] += 1

    result = []

    for item in performance.values():

        presented = item["presented"]
        purchased = item["purchased"]
        interested = item["interested"]
        rejected = item["rejected"]
        follow_up = item["follow_up"]
        not_presented = item["not_presented"]
        revenue = item["revenue"]

        purchase_revenues = (
            item["purchase_revenues"]
        )

        average_revenue = (
            sum(purchase_revenues)
            / len(purchase_revenues)
            if purchase_revenues
            else 0
        )

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

        if presented < 3:
            data_quality = "INSUFFICIENT_DATA"

        elif presented < 10:
            data_quality = "LIMITED_DATA"

        else:
            data_quality = "SUFFICIENT_DATA"

        if presented < 3:
            performance_level = "UNKNOWN"

        elif conversion_rate >= 40:
            performance_level = "HIGH"

        elif conversion_rate >= 20:
            performance_level = "MEDIUM"

        else:
            performance_level = "LOW"

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

        result.append({
            "recommendation_type": (
                item["recommendation_type"]
            ),
            "presented": presented,
            "purchased": purchased,
            "interested": interested,
            "rejected": rejected,
            "follow_up": follow_up,
            "not_presented": not_presented,
            "revenue": round(
                revenue,
                2,
            ),
            "average_revenue": round(
                average_revenue,
                2,
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

    result.sort(
        key=lambda item: (
            item["recommendation_type"]
            or ""
        )
    )

    return result