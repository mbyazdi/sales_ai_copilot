from django.urls import path

from .views import (
    CustomerRecommendationAPIView,
    CustomerRecommendationPerformanceAPIView,
    RecommendationTuningSuggestionListAPIView,
    RecommendationTuningSuggestionStatusAPIView,
    RecommendationTuningSuggestionApplyAPIView,
    RecommendationTuningSuggestionRollbackAPIView,
    RecommendationDiagnosticsAPIView,
)


urlpatterns = [

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

]