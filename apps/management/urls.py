from django.urls import path

from .views import (
    recommendation_performance_dashboard,
)


urlpatterns = [
    path(
        "recommendations/performance/",
        recommendation_performance_dashboard,
        name="recommendation-performance-dashboard",
    ),
]