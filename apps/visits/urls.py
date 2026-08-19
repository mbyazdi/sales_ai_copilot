from django.urls import path

from .views import salesperson_dashboard

from .views import SalesOutcomeCreateAPIView

from .views import (
    CustomerSalesOutcomeHistoryAPIView,
)

from .views import (
    RecommendationPerformanceAPIView,
)
from .views import VisitCompleteAPIView
from .views import VisitStartAPIView

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
]