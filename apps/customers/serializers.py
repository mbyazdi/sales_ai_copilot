from rest_framework import serializers

from apps.customers.models import Customer
from apps.recommendations.models import CustomerRecommendation


class Customer360Serializer(serializers.Serializer):

    def to_representation(self, customer):

        snapshot = getattr(customer, "customer_360", None)

        grade = customer.grade

        recommendations = (
            CustomerRecommendation.objects
            .filter(
                customer=customer,
                is_active=True,
            )
            .select_related(
                "product",
                "product__category",
            )
            .order_by("rank")
        )

        recommendation_data = []

        for recommendation in recommendations:

            product = recommendation.product

            recommendation_data.append({
                "rank": recommendation.rank,
                "product_code": product.product_code,
                "product_name": product.name,
                "category": (
                    str(product.category)
                    if product.category
                    else None
                ),
                "score": recommendation.score,
                "recommendation_type": (
                    recommendation.recommendation_type
                ),
                "reason": recommendation.reason,
            })

        return {
            "customer": {
                "code": customer.customer_code,
                "name": customer.name,
                "type": customer.customer_type,
                "city": customer.city,
                "address": customer.address,
                "phone": customer.phone,
                "grade": {
                    "code": grade.code if grade else None,
                    "name": grade.name if grade else None,
                    "priority": (
                        grade.priority
                        if grade
                        else None
                    ),
                },
            },

            "metrics": {
                "total_orders": (
                    snapshot.total_orders
                    if snapshot
                    else 0
                ),
                "total_items": (
                    snapshot.total_items
                    if snapshot
                    else 0
                ),
                "total_sales_amount": (
                    snapshot.total_sales_amount
                    if snapshot
                    else 0
                ),
                "average_order_value": (
                    snapshot.average_order_value
                    if snapshot
                    else 0
                ),
                "first_purchase_date": (
                    snapshot.first_purchase_date
                    if snapshot
                    else None
                ),
                "last_purchase_date": (
                    snapshot.last_purchase_date
                    if snapshot
                    else None
                ),
                "days_since_last_purchase": (
                    snapshot.days_since_last_purchase
                    if snapshot
                    else 0
                ),
            },

            "rfm": {
                "recency_score": (
                    snapshot.recency_score
                    if snapshot
                    else 0
                ),
                "frequency_score": (
                    snapshot.frequency_score
                    if snapshot
                    else 0
                ),
                "monetary_score": (
                    snapshot.monetary_score
                    if snapshot
                    else 0
                ),
                "rfm_score": (
                    snapshot.rfm_score
                    if snapshot
                    else 0
                ),
                "segment": (
                    snapshot.segment
                    if snapshot
                    else None
                ),
            },

            "sales_trend": {
                "sales_30d": (
                    snapshot.sales_30d
                    if snapshot
                    else 0
                ),
                "sales_90d": (
                    snapshot.sales_90d
                    if snapshot
                    else 0
                ),
                "sales_30d_change_percent": (
                    snapshot.sales_30d_change_percent
                    if snapshot
                    else 0
                ),
                "sales_90d_change_percent": (
                    snapshot.sales_90d_change_percent
                    if snapshot
                    else 0
                ),
            },

            "behavior": {
                "purchase_frequency": (
                    snapshot.purchase_frequency
                    if snapshot
                    else 0
                ),
                "top_category": (
                    snapshot.top_category
                    if snapshot
                    else None
                ),
                "top_product_code": (
                    snapshot.top_product_code
                    if snapshot
                    else None
                ),
            },

            "recommendations": recommendation_data,
        }