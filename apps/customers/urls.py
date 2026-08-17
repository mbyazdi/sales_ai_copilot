from django.urls import path

from .views import (
    customer_search,
    Customer360APIView,
)


urlpatterns = [

    path(
        "",
        customer_search,
        name="customer-search",
    ),

    path(
        "v1/customer-360/<str:customer_code>/",
        Customer360APIView.as_view(),
        name="customer-360-api",
    ),

]