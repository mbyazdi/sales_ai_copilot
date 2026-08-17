from apps.customers.services import (
    get_customer_by_code,
)

from .engine import RecommendationEngine


def generate_customer_recommendations(
    customer_code
):

    customer = get_customer_by_code(
        customer_code
    )

    if not customer:

        return None

    engine = RecommendationEngine(
        customer
    )

    recommendations = (
        engine.generate()
    )

    return {
        "customer": customer,

        "recommendations": recommendations,
    }

def get_recommendation_performance(customer=None):
    """
    Calculate recommendation performance based on
    SalesOutcome records.

    Metrics:
        - presented
        - purchased
        - interested
        - rejected
        - follow_up
        - not_presented
        - revenue
        - average_revenue
        - conversion_rate
        - interest_rate
    """

    from apps.visits.models import SalesOutcome

    queryset = (
        SalesOutcome.objects
        .filter(
            visit__customer=customer,
            recommendation__isnull=False,
        )
        .select_related(
            "recommendation",
        )
    )

    performance = {}

    for outcome in queryset:

        recommendation_type = (
            outcome.recommendation.recommendation_type
        )

        if recommendation_type not in performance:
            performance[recommendation_type] = {
                "recommendation_type": recommendation_type,
                "presented": 0,
                "purchased": 0,
                "interested": 0,
                "rejected": 0,
                "follow_up": 0,
                "not_presented": 0,
                "revenue": 0.0,
            }

        item = performance[recommendation_type]

        item["presented"] += 1

        outcome_name = outcome.outcome

        if outcome_name == "PURCHASED":
            item["purchased"] += 1

        elif outcome_name == "INTERESTED":
            item["interested"] += 1

        elif outcome_name == "REJECTED":
            item["rejected"] += 1

        elif outcome_name == "FOLLOW_UP":
            item["follow_up"] += 1

        elif outcome_name == "NOT_PRESENTED":
            item["not_presented"] += 1

        if outcome.sales_amount:
            item["revenue"] += float(
                outcome.sales_amount
            )

    result = []

    for item in performance.values():

        presented = item["presented"]

        purchased = item["purchased"]

        interested = item["interested"]

        revenue = item["revenue"]

        item["average_revenue"] = (
            round(
                revenue / purchased,
                2,
            )
            if purchased
            else 0.0
        )

        item["conversion_rate"] = (
            round(
                purchased / presented * 100,
                2,
            )
            if presented
            else 0.0
        )

        item["interest_rate"] = (
            round(
                interested / presented * 100,
                2,
            )
            if presented
            else 0.0
        )

        result.append(item)

    result.sort(
        key=lambda x: x["recommendation_type"]
    )

    return result