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
                "score_breakdown": (
                    recommendation.score_breakdown
                ),

                "confidence_score": (
                    recommendation.confidence_score
                ),

                "evidence_quality": (
                    recommendation.evidence_quality
                ),

                "explanation_snapshot": (
                    recommendation.explanation_snapshot
                ),
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
class RecommendationDiagnosticsAPIView(APIView):

    permission_classes = [
        IsAdminUser,
    ]

    def get(self, request):

        recommendations = (
            CustomerRecommendation.objects
            .filter(
                is_active=True,
            )
            .select_related(
                "customer",
                "product",
            )
            .order_by(
                "customer_id",
                "rank",
            )
        )

        data = []

        for recommendation in recommendations:

            snapshot = (
                recommendation.explanation_snapshot
                or {}
            )

            breakdown = (
                recommendation.score_breakdown
                or {}
            )

            data.append({
                "id": recommendation.id,

                "customer_code": (
                    recommendation.customer.customer_code
                ),

                "rank": recommendation.rank,

                "product_code": (
                    recommendation.product.product_code
                ),

                "product_name": (
                    recommendation.product.name
                ),

                "recommendation_type": (
                    recommendation.recommendation_type
                ),

                "score": recommendation.score,

                "confidence_score": (
                    recommendation.confidence_score
                ),

                "evidence_quality": (
                    recommendation.evidence_quality
                ),

                "active_signal_count": (
                    snapshot.get(
                        "active_signal_count",
                        0,
                    )
                ),

                "rule_score": (
                    breakdown.get(
                        "rule_score",
                        0,
                    )
                ),

                "feedback_score": (
                    breakdown.get(
                        "feedback_score",
                        0,
                    )
                ),

                "score_breakdown": breakdown,

                "explanation_snapshot": snapshot,
            })

        return Response(
            {
                "count": len(data),
                "results": data,
            },
            status=status.HTTP_200_OK,
        )

class RecommendationDiagnosticsSummaryAPIView(APIView):

    permission_classes = [
        IsAdminUser,
    ]

    LOW_CONFIDENCE_THRESHOLD = 50

    def get(self, request):

        recommendations = CustomerRecommendation.objects.filter(
            is_active=True,
        )

        total_recommendations = recommendations.count()

        if total_recommendations == 0:
            return Response(
                {
                    "total_recommendations": 0,
                    "average_confidence": 0.0,
                    "evidence": {
                        "high": 0,
                        "medium": 0,
                        "low": 0,
                    },
                    "quality_flags": {
                        "low_confidence": 0,
                        "negative_feedback": 0,
                        "single_signal": 0,
                    },
                }
            )

        confidence_values = [
            float(item.confidence_score or 0)
            for item in recommendations
        ]

        average_confidence = (
            sum(confidence_values)
            / total_recommendations
        )

        high_evidence_count = recommendations.filter(
            evidence_quality="HIGH",
        ).count()

        medium_evidence_count = recommendations.filter(
            evidence_quality="MEDIUM",
        ).count()

        low_evidence_count = recommendations.filter(
            evidence_quality="LOW",
        ).count()

        low_confidence_count = recommendations.filter(
            confidence_score__lt=self.LOW_CONFIDENCE_THRESHOLD,
        ).count()

        negative_feedback_count = 0
        single_signal_count = 0

        for recommendation in recommendations:

            snapshot = (
                recommendation.explanation_snapshot
                or {}
            )

            feedback_score = snapshot.get(
                "feedback_score",
                0,
            )

            active_signal_count = snapshot.get(
                "active_signal_count",
                0,
            )

            try:
                feedback_score = float(
                    feedback_score or 0
                )
            except (
                TypeError,
                ValueError,
            ):
                feedback_score = 0.0

            try:
                active_signal_count = int(
                    active_signal_count or 0
                )
            except (
                TypeError,
                ValueError,
            ):
                active_signal_count = 0

            if feedback_score < 0:
                negative_feedback_count += 1

            if active_signal_count <= 1:
                single_signal_count += 1

        return Response(
            {
                "total_recommendations": (
                    total_recommendations
                ),
                "average_confidence": round(
                    average_confidence,
                    2,
                ),
                "evidence": {
                    "high": high_evidence_count,
                    "medium": medium_evidence_count,
                    "low": low_evidence_count,
                },
                "quality_flags": {
                    "low_confidence": (
                        low_confidence_count
                    ),
                    "negative_feedback": (
                        negative_feedback_count
                    ),
                    "single_signal": (
                        single_signal_count
                    ),
                },
            }
        )

class RecommendationDiagnosticsDetailAPIView(APIView):

    permission_classes = [
        IsAdminUser,
    ]

    def get(
        self,
        request,
        recommendation_id,
    ):

        recommendation = (
            CustomerRecommendation.objects
            .select_related(
                "customer",
                "product",
            )
            .filter(
                id=recommendation_id,
                is_active=True,
            )
            .first()
        )

        if recommendation is None:
            return Response(
                {
                    "detail":
                        "Recommendation not found."
                },
                status=404,
            )

        snapshot = (
            recommendation.explanation_snapshot
            or {}
        )

        score_breakdown = (
            recommendation.score_breakdown
            or {}
        )

        active_signal_count = (
            snapshot.get(
                "active_signal_count",
                0,
            )
        )

        rule_score = snapshot.get(
            "rule_score",
            score_breakdown.get(
                "rule_score",
                0,
            ),
        )

        feedback_score = snapshot.get(
            "feedback_score",
            score_breakdown.get(
                "feedback_score",
                0,
            ),
        )

        return Response(
            {
                "id":
                    recommendation.id,

                "customer_code":
                    recommendation.customer.customer_code,

                "rank":
                    recommendation.rank,

                "product": {
                    "code":
                        recommendation.product.product_code,

                    "name":
                        recommendation.product.name,
                },

                "recommendation_type":
                    recommendation.recommendation_type,

                "score":
                    float(
                        recommendation.score
                        or 0
                    ),

                "confidence_score":
                    float(
                        recommendation.confidence_score
                        or 0
                    ),

                "evidence_quality":
                    recommendation.evidence_quality,

                "reason":
                    recommendation.reason
                    or "",

                "active_signal_count":
                    active_signal_count,

                "rule_score":
                    float(
                        rule_score
                        or 0
                    ),

                "feedback_score":
                    float(
                        feedback_score
                        or 0
                    ),

                "score_breakdown":
                    score_breakdown,

                "explanation_snapshot":
                    snapshot,
            }
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