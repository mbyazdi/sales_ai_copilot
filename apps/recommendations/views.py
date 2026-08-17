from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers.models import Customer
from .models import CustomerRecommendation
from .services import get_recommendation_performance

class CustomerRecommendationAPIView(APIView):

    ENGINE_VERSION = "1.0"

    def get(self, request, customer_code):

        customer = get_object_or_404(
            Customer,
            customer_code=customer_code,
            is_active=True,
        )

        recommendations = (
            CustomerRecommendation.objects
            .filter(
                customer_id=customer.id,
                is_active=True,
            )
            .select_related(
                "product",
                "product__category",
            )
            .order_by("rank")
        )

        data = []

        for recommendation in recommendations:

            product = recommendation.product

            data.append({
                "rank": recommendation.rank,
                "product_code": product.product_code,
                "product_name": product.name,
                "category": product.category.name,
                "score": recommendation.score,
                "recommendation_type": recommendation.recommendation_type,
                "reason": recommendation.reason,
            })

        return Response(
            {
                "customer_code": customer.customer_code,
                "count": len(data),
                "engine_version": self.ENGINE_VERSION,
                "recommendations": data,
            },
            status=status.HTTP_200_OK,
        )

class CustomerRecommendationPerformanceAPIView(APIView):

    def get(self, request, customer_code):

        customer = get_object_or_404(
            Customer,
            customer_code=customer_code,
            is_active=True,
        )

        performance = get_recommendation_performance(
            customer=customer
        )

        presented = sum(
            item["presented"]
            for item in performance
        )

        purchased = sum(
            item["purchased"]
            for item in performance
        )

        interested = sum(
            item["interested"]
            for item in performance
        )

        revenue = sum(
            item["revenue"]
            for item in performance
        )

        conversion_rate = (
            round(
                purchased / presented * 100,
                2
            )
            if presented
            else 0
        )

        interest_rate = (
            round(
                interested / presented * 100,
                2
            )
            if presented
            else 0
        )

        return Response(
            {
                "customer": {
                    "code": customer.customer_code,
                    "name": customer.name,
                },

                "summary": {
                    "presented": presented,
                    "purchased": purchased,
                    "interested": interested,
                    "revenue": float(revenue),
                    "conversion_rate": conversion_rate,
                    "interest_rate": interest_rate,
                },

                "performance": performance,
            },

            status=status.HTTP_200_OK,
        )