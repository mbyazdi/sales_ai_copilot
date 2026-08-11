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