from django.urls import path

from .views import SalesCopilotAPIView


app_name = "ai"


urlpatterns = [

    path(
        "v1/sales-copilot/",
        SalesCopilotAPIView.as_view(),
        name="sales-copilot",
    ),

]