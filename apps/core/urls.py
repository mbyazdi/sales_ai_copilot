from django.urls import path

from .views import (
    ProductCommercialContextAPIView,
    role_home,
)


urlpatterns = [
    path(
        "",
        role_home,
        name="role-home",
    ),
        path(
        (
            "api/v1/customers/"
            "<str:customer_code>/"
            "products/"
            "<str:product_code>/"
            "commercial-context/"
        ),
        ProductCommercialContextAPIView.as_view(),
        name="product-commercial-context",
    ),
]