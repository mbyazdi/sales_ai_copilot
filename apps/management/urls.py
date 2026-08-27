from django.urls import path

from .views import (
    management_dashboard,
    recommendation_performance_dashboard,
)


urlpatterns = [

    path(
        "",
        management_dashboard,
        name="management-dashboard",
    ),

    path(
        "recommendations/performance/",
        recommendation_performance_dashboard,
        name="recommendation-performance-dashboard",
    ),

]