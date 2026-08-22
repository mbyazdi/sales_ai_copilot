from django.urls import path

from .views import salesperson_dashboard

from .views import (
    SalesOutcomeCreateAPIView,
    CustomerSalesOutcomeHistoryAPIView,
    RecommendationPerformanceAPIView,
    VisitCompleteAPIView,
    VisitStartAPIView,
    FollowUpTaskListAPIView,
    FollowUpTaskStatusAPIView,
    follow_up_dashboard,
)


urlpatterns = [
    path(
        "",
        salesperson_dashboard,
        name="salesperson-dashboard",
    ),
    path(
        "v1/outcomes/",
        SalesOutcomeCreateAPIView.as_view(),
        name="sales-outcome-create",
    ),
    path(
        "v1/customers/<str:customer_code>/sales-outcomes/",
        CustomerSalesOutcomeHistoryAPIView.as_view(),
        name="customer-sales-outcome-history",
    ),
    path(
        "v1/customers/<str:customer_code>/recommendation-performance/",
        RecommendationPerformanceAPIView.as_view(),
        name="recommendation-performance",
    ),
    path(
        "v1/recommendations/performance/",
        RecommendationPerformanceAPIView.as_view(),
        name="recommendation-performance-all",
    ),
    path(
        "v1/visits/<int:visit_id>/complete/",
        VisitCompleteAPIView.as_view(),
        name="visit-complete",
    ),
    path(
        "v1/visits/<int:visit_id>/start/",
        VisitStartAPIView.as_view(),
        name="visit-start",
    ),
    path(
        "v1/follow-ups/",
        FollowUpTaskListAPIView.as_view(),
        name="follow-up-task-list",
    ),
    path(
        "v1/follow-ups/<int:task_id>/status/",
        FollowUpTaskStatusAPIView.as_view(),
        name="follow-up-task-status",
    ),
    path(
        "follow-ups/",
        follow_up_dashboard,
        name="follow-up-dashboard",
    ),

]