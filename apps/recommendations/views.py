from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers.models import Customer
from apps.visits.services import (
    get_recommendation_performance,
)
from .models import (
    CustomerRecommendation,
    RecommendationTuningSuggestion,
)
from rest_framework.permissions import IsAdminUser
from .services import (
    update_tuning_suggestion_status,
)
from .services import (
    update_tuning_suggestion_status,
    rollback_tuning_suggestion,
)

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

        performance = (
            get_recommendation_performance(
                customer=customer
            )
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

        follow_up = sum(
            item["follow_up"]
            for item in performance
        )

        rejected = sum(
            item["rejected"]
            for item in performance
        )

        not_presented = sum(
            item["not_presented"]
            for item in performance
        )

        revenue = sum(
            item["revenue"]
            for item in performance
        )

        average_sales_amount = (
            round(
                revenue / purchased,
                2,
            )
            if purchased
            else 0
        )

        conversion_rate = (
            round(
                purchased / presented * 100,
                2,
            )
            if presented
            else 0
        )

        interest_rate = (
            round(
                interested / presented * 100,
                2,
            )
            if presented
            else 0
        )

        follow_up_rate = (
            round(
                follow_up / presented * 100,
                2,
            )
            if presented
            else 0
        )

        rejection_rate = (
            round(
                rejected / presented * 100,
                2,
            )
            if presented
            else 0
        )

        engagement_rate = (
            round(
                (
                    purchased
                    + interested
                    + follow_up
                )
                / presented
                * 100,
                2,
            )
            if presented
            else 0
        )

        return Response(
            {
                "customer": {
                    "code": (
                        customer.customer_code
                    ),
                    "name": (
                        customer.name
                    ),
                },

                "summary": {
                    "presented": (
                        presented
                    ),

                    "purchased": (
                        purchased
                    ),

                    "interested": (
                        interested
                    ),

                    "follow_up": (
                        follow_up
                    ),

                    "rejected": (
                        rejected
                    ),

                    "not_presented": (
                        not_presented
                    ),

                    "revenue": (
                        round(
                            revenue,
                            2,
                        )
                    ),

                    "average_sales_amount": (
                        average_sales_amount
                    ),

                    "conversion_rate": (
                        conversion_rate
                    ),

                    "interest_rate": (
                        interest_rate
                    ),

                    "follow_up_rate": (
                        follow_up_rate
                    ),

                    "rejection_rate": (
                        rejection_rate
                    ),

                    "engagement_rate": (
                        engagement_rate
                    ),
                },

                "performance": (
                    performance
                ),
            },
            status=status.HTTP_200_OK,
        )

class RecommendationTuningSuggestionListAPIView(APIView):
    permission_classes = [
        IsAdminUser,
    ]

    def get(self, request):

        suggestions = (
            RecommendationTuningSuggestion.objects
            .order_by(
                "-created_at",
            )
        )

        data = []

        for item in suggestions:

            data.append({

                "id": item.id,

                "recommendation_type": (
                    item.recommendation_type
                ),

                "metric": item.metric,

                "current_value": (
                    item.current_value
                ),

                "suggested_value": (
                    item.suggested_value
                ),

                "applied_previous_value": (
                    item.applied_previous_value
                ),

                "status": item.status,

                "reason": item.reason,

                "performance_snapshot": (
                    item.performance_snapshot
                ),

                "created_at": (
                    item.created_at
                ),

                "reviewed_at": (
                    item.reviewed_at
                ),

                "applied_at": (
                    item.applied_at
                ),

                "rolled_back_at": (
                    item.rolled_back_at
                ),

            })

        return Response(
            {
                "count": len(data),

                "results": data,
            }
        )

class RecommendationTuningSuggestionStatusAPIView(APIView):

    permission_classes = [
        IsAdminUser,
    ]

    def post(self, request, suggestion_id):

        suggestion = get_object_or_404(
            RecommendationTuningSuggestion,
            id=suggestion_id,
        )

        new_status = request.data.get(
            "status"
        )

        allowed_statuses = {
            RecommendationTuningSuggestion.Status.APPROVED,
            RecommendationTuningSuggestion.Status.REJECTED,
        }

        if new_status not in allowed_statuses:

            return Response(
                {
                    "detail": (
                        "status must be APPROVED "
                        "or REJECTED."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            suggestion = (
                update_tuning_suggestion_status(
                    suggestion=suggestion,
                    new_status=new_status,
                )
            )

        except ValueError as error:

            return Response(
                {
                    "detail": str(error)
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "success": True,

                "suggestion": {
                    "id": suggestion.id,
                    "status": suggestion.status,
                    "reviewed_at": (
                        suggestion.reviewed_at
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )

class RecommendationTuningSuggestionApplyAPIView(APIView):

    permission_classes = [
        IsAdminUser,
    ]

    def post(self, request, suggestion_id):

        suggestion = get_object_or_404(
            RecommendationTuningSuggestion,
            id=suggestion_id,
        )

        try:

            suggestion = (
                update_tuning_suggestion_status(
                    suggestion=suggestion,
                    new_status=(
                        RecommendationTuningSuggestion
                        .Status
                        .APPLIED
                    ),
                )
            )

        except ValueError as error:

            return Response(
                {
                    "detail": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "success": True,

                "suggestion": {
                    "id": suggestion.id,

                    "recommendation_type": (
                        suggestion.recommendation_type
                    ),

                    "metric": (
                        suggestion.metric
                    ),

                    "previous_value": (
                        suggestion.current_value
                    ),

                    "applied_value": (
                        suggestion.suggested_value
                    ),

                    "status": (
                        suggestion.status
                    ),

                    "applied_at": (
                        suggestion.applied_at
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )

class RecommendationTuningSuggestionRollbackAPIView(APIView):

    permission_classes = [
        IsAdminUser,
    ]

    def post(self, request, suggestion_id):

        suggestion = get_object_or_404(
            RecommendationTuningSuggestion,
            id=suggestion_id,
        )

        try:

            suggestion = rollback_tuning_suggestion(
                suggestion=suggestion
            )

        except ValueError as error:

            return Response(
                {
                    "detail": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "success": True,

                "suggestion": {
                    "id": suggestion.id,

                    "recommendation_type": (
                        suggestion.recommendation_type
                    ),

                    "metric": (
                        suggestion.metric
                    ),

                    "restored_value": (
                        suggestion.applied_previous_value
                    ),

                    "status": (
                        suggestion.status
                    ),

                    "rolled_back_at": (
                        suggestion.rolled_back_at
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )