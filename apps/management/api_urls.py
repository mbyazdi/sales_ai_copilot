from django.urls import include, path

from .api_views import (
    ManagementDashboardAPIView,
)


app_name = "management_api"


urlpatterns = [
    path("v1/strategy/", include("apps.management.strategy_api_urls")),
    path(
        "v1/dashboard/",
        ManagementDashboardAPIView.as_view(),
        name="dashboard",
    ),
]
