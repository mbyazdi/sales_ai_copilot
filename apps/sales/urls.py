from django.urls import path

from .views import (
    CustomerSalesHistoryAPIView,
)


urlpatterns = [

    path(
        "v1/customers/<str:customer_code>/history/",
        CustomerSalesHistoryAPIView.as_view(),
        name="customer-sales-history",
    ),

]