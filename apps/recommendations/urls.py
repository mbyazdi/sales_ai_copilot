from django.urls import path
from .feedback_views import RecommendationFeedbackAPIView

from .views import (
    CustomerRecommendationAPIView,
    CustomerRecommendationPerformanceAPIView,
    RecommendationTuningSuggestionListAPIView,
    RecommendationTuningSuggestionStatusAPIView,
    RecommendationTuningSuggestionApplyAPIView,
    RecommendationTuningSuggestionRollbackAPIView,
    RecommendationDiagnosticsAPIView,
    RecommendationDiagnosticsSummaryAPIView,
    RecommendationDiagnosticsDetailAPIView,
)


urlpatterns = [
    path("v1/visits/<int:visit_id>/feedback/", RecommendationFeedbackAPIView.as_view(), name="recommendation-feedback-v1"),

    path(
        "v1/recommendations/<str:customer_code>/",
        CustomerRecommendationAPIView.as_view(),
        name="customer-recommendations",
    ),

    path(
        "v1/customers/<str:customer_code>/performance/",
        CustomerRecommendationPerformanceAPIView.as_view(),
        name="customer-recommendation-performance",
    ),
    path(
        "v1/tuning-suggestions/",
        RecommendationTuningSuggestionListAPIView.as_view(),
        name="recommendation-tuning-suggestions",
    ),
    path(
        "v1/tuning-suggestions/<int:suggestion_id>/status/",
        RecommendationTuningSuggestionStatusAPIView.as_view(),
        name="recommendation-tuning-suggestion-status",
    ),
    path(
        "v1/tuning-suggestions/<int:suggestion_id>/apply/",
        RecommendationTuningSuggestionApplyAPIView.as_view(),
        name="recommendation-tuning-suggestion-apply",
    ),
    path(
        "v1/tuning-suggestions/<int:suggestion_id>/rollback/",
        RecommendationTuningSuggestionRollbackAPIView.as_view(),
        name="recommendation-tuning-suggestion-rollback",
    ),
    path(
        "v1/diagnostics/",
        RecommendationDiagnosticsAPIView.as_view(),
        name="recommendation-diagnostics",
    ),
    path(
        "v1/diagnostics/summary/",
        RecommendationDiagnosticsSummaryAPIView.as_view(),
        name="recommendation-diagnostics-summary",
    ),
    path(
        "v1/diagnostics/<int:recommendation_id>/",
        RecommendationDiagnosticsDetailAPIView.as_view(),
        name="recommendation-diagnostics-detail",
    ),

]
