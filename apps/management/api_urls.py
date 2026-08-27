from django.urls import path

from .api_views import (
    ManagementDashboardAPIView,
)


app_name = "management_api"


urlpatterns = [
    path(
        "v1/dashboard/",
        ManagementDashboardAPIView.as_view(),
        name="dashboard",
    ),
]